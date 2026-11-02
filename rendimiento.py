from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
import os
from pathlib import Path
import time

import requests


ACTUAL = ContextVar('rendimiento_paso', default=None)
FASES = ContextVar('rendimiento_fases', default=frozenset())
ULTIMOS = {}
CRUDO_CONTADOR = 0
RUTA_CRUDO = Path(__file__).resolve().parent / "salidas" / "rapidez" / "crudo"


def resumir_consultas(peticiones):
    tokens = [p.get('uso', {}).get('completion_tokens') for p in peticiones]
    tiempos = [p.get('timings', {}) for p in peticiones]
    return {
        'consultas': len(peticiones),
        'tokens_generados': sum(tokens) if all(isinstance(t, int) for t in tokens) else None,
        'prompt_servidor_s': sum(t.get('prompt_ms', 0) for t in tiempos) / 1000,
        'generacion_s': sum(t.get('predicted_ms', 0) for t in tiempos) / 1000,
        'consulta_http_s': sum(p.get('segundos', 0) for p in peticiones),
        'tiempos_servidor_disponibles': all('prompt_ms' in t and 'predicted_ms' in t for t in tiempos),
    }


def registrar_consulta(peticion):
    actual = ACTUAL.get()
    if actual is not None:
        actual['peticiones'].append(dict(peticion))


@contextmanager
def fase(nombre):
    activas = FASES.get()
    token = FASES.set(activas | {nombre})
    inicio = time.perf_counter()
    try:
        yield
    finally:
        segundos = time.perf_counter() - inicio
        FASES.reset(token)
        actual = ACTUAL.get()
        if actual is not None and nombre not in activas:
            actual[nombre] = actual.get(nombre, 0.0) + segundos


def medir(nombre):
    def decorar(funcion):
        @wraps(funcion)
        def medida(*args, **kwargs):
            inicio = time.perf_counter()
            try:
                with fase(nombre):
                    return funcion(*args, **kwargs)
            finally:
                ULTIMOS[nombre] = time.perf_counter() - inicio
        return medida
    return decorar


@contextmanager
def paso(numero, origen, identificador='', captura_inicial_s=0.0):
    dato = {'paso': numero, 'origen': origen, 'identificador': identificador,
            'captura_percepcion_s': captura_inicial_s, 'prompt_local_s': 0.0,
            'accion': None, 'peticiones': []}
    token = ACTUAL.set(dato)
    inicio = time.perf_counter()
    try:
        yield dato
    except BaseException as error:
        dato['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        dato['segundos'] = time.perf_counter() - inicio
        dato.update(resumir_consultas(dato['peticiones']))
        ACTUAL.reset(token)
        ruta = Path(os.environ.get('FOSFENO_TIEMPOS_LOG') or
                    Path(__file__).resolve().parent / 'salidas' / 'rapidez' / 'pasos.jsonl')
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with ruta.open('a', encoding='utf-8') as archivo:
                archivo.write(json.dumps(dato, ensure_ascii=False) + '\n')
        except OSError:
            pass


def registrar_crudo(url, payload, esquema, datos):
    global CRUDO_CONTADOR
    if os.environ.get("FOSFENO_TIEMPOS_CRUDO") != "1" or CRUDO_CONTADOR >= 12:
        return
    if "accion" not in esquema.get("properties", {}):
        return
    opcion = (datos.get("choices") or [{}])[0]
    mensaje = opcion.get("message", {})
    base = url.rsplit("/v1/", 1)[0]
    def contar(texto):
        if not texto:
            return 0
        respuesta = requests.post(base + "/tokenize", json={
            "content": texto, "add_special": False, "parse_special": True}, timeout=20)
        respuesta.raise_for_status()
        return len(respuesta.json()["tokens"])
    registro = {"numero": CRUDO_CONTADOR + 1, "respuesta": datos,
                "content_tokens": contar(mensaje.get("content") or ""),
                "reasoning_tokens": contar(mensaje.get("reasoning_content") or ""),
                "completion_tokens": datos.get("usage", {}).get("completion_tokens"),
                "finish_reason": opcion.get("finish_reason"),
                "restriccion": "grammar" if "grammar" in payload else "json_schema"}
    RUTA_CRUDO.mkdir(parents=True, exist_ok=True)
    with (RUTA_CRUDO / ("consultas-" + str(os.getpid()) + ".jsonl")).open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
    CRUDO_CONTADOR += 1
