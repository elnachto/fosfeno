import argparse
import copy
from contextlib import ExitStack
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import agente
import evaluacion
import marcas
import rendimiento
from entornos_evaluacion import sin_entrada_nativa


VERIFICACION = ContextVar('traza_verificacion', default=None)


def guardar(ruta, dato):
    ruta.write_text(json.dumps(dato, ensure_ascii=False, indent=2), encoding='utf-8')


def ejecutar(carpeta, casos, semillas, continuar_falsos=False):
    carpeta = carpeta.resolve()
    carpeta.mkdir(parents=True, exist_ok=False)
    os.environ['FOSFENO_TIEMPOS_LOG'] = str(carpeta / 'pasos.jsonl')
    os.environ['FOSFENO_TIEMPOS_CRUDO'] = '0'
    os.environ['FOSFENO_GBNF_EXPERIMENTAL'] = '0'
    hashes = {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in BASE.glob('*.py')}
    hashes[str(Path(__file__).relative_to(BASE))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    guardar(carpeta / 'manifiesto.json', {'casos': [c['id'] for c in casos], 'semillas': semillas,
        'instruccion_sha256': hashlib.sha256(agente.INSTRUCCION.encode()).hexdigest(), 'fuentes': hashes})
    verificar = agente.verificar
    consultar = marcas.preguntar_json
    post = marcas.requests.post
    resultados = []
    contexto_caso = {}
    app_caso = None
    clase_escritorio = evaluacion.EscritorioSimulado
    clase_original = evaluacion.AplicacionSimulada
    def crear(clase, *args, **kwargs):
        nonlocal app_caso
        app_caso = clase(*args, **kwargs)
        return app_caso
    def escribir(nombre, dato):
        with (carpeta / nombre).open('a', encoding='utf-8') as archivo:
            archivo.write(json.dumps(dato, ensure_ascii=False) + '\n')
    def verificar_trazado(objetivo, elementos, estado, historial, consulta, imagen=None):
        registro = {**contexto_caso, 'paso': (rendimiento.ACTUAL.get() or {}).get('paso'),
                    'objetivo_verificado': objetivo, 'elementos': copy.deepcopy(elementos),
                    'estado': copy.deepcopy(estado), 'historial': list(historial), 'consultas': []}
        if app_caso is not None:
            registro['oraculo_objetivo_total'] = app_caso.cumplida()
            registro['estado_privado'] = copy.deepcopy(app_caso.diagnostico() if hasattr(app_caso, 'diagnostico')
                else {'enviado': app_caso.enviado, 'valores': app_caso.valores})
        token = VERIFICACION.set(registro)
        try:
            registro['resultado_final'] = verificar(objetivo, elementos, estado, historial, consulta, imagen)
            registro['final_confirmado'] = agente.final_confirmado(registro['resultado_final'])
            return registro['resultado_final']
        finally:
            escribir('verificador.jsonl', registro)
            VERIFICACION.reset(token)
    def consultar_trazado(instruccion, texto, esquema, img=None):
        respuesta = consultar(instruccion, texto, esquema, img)
        registro = VERIFICACION.get()
        if registro is not None:
            registro['consultas'].append({'instruccion': instruccion, 'prompt': texto,
                                          'esquema': esquema, 'imagen': img is not None,
                                          'respuesta_modelo': copy.deepcopy(respuesta)})
        return respuesta
    def post_trazado(url, **kwargs):
        if not url.startswith(('http://127.0.0.1:', 'http://localhost:')):
            raise AssertionError('Solo servidor local')
        reloj = time.monotonic()
        respuesta = post(url, **kwargs)
        if url.endswith('/v1/chat/completions'):
            escribir('consultas-crudas.jsonl', {**contexto_caso,
                'paso': (rendimiento.ACTUAL.get() or {}).get('paso'),
                'verificacion': VERIFICACION.get() is not None, 'peticion': kwargs.get('json'),
                'segundos': time.monotonic() - reloj, 'respuesta': respuesta.json()})
        return respuesta
    with sin_entrada_nativa(), ExitStack() as pila:
        pila.enter_context(patch.object(agente, 'verificar', side_effect=verificar_trazado))
        pila.enter_context(patch.object(marcas, 'preguntar_json', side_effect=consultar_trazado))
        pila.enter_context(patch.object(marcas.requests, 'post', side_effect=post_trazado))
        pila.enter_context(patch.object(evaluacion, 'EscritorioSimulado', side_effect=lambda *a, **k: crear(clase_escritorio, *a, **k)))
        pila.enter_context(patch.object(evaluacion, 'AplicacionSimulada', side_effect=lambda *a, **k: crear(clase_original, *a, **k)))
        for semilla in semillas:
            for caso in casos:
                contexto_caso.clear()
                contexto_caso.update(caso=caso['id'], semilla=semilla)
                app_caso = None
                guardar(carpeta / 'estado.json', contexto_caso)
                resultado = evaluacion.ejecutar_caso(caso, 'nemotron', semilla)
                resultados.append(resultado)
                guardar(carpeta / 'resultados.json', resultados)
                print(json.dumps({k: resultado[k] for k in ('caso', 'semilla', 'correcto', 'motivo',
                    'pasos', 'consultas', 'tokens_por_consulta', 'segundos', 'objetivo_logrado', 'falso_exito_aceptado')}, ensure_ascii=True), flush=True)
                if resultado['falso_exito_aceptado']:
                    alerta = carpeta / f"ALERTA-FALSO-EXITO-{caso['id']}-{semilla}.json"
                    with alerta.open('x', encoding='utf-8') as archivo:
                        json.dump(resultado, archivo, ensure_ascii=False, indent=2)
                    escribir('ALERTA-FALSO-EXITO.jsonl', {**contexto_caso, 'evidencia': alerta.name})
                    if not continuar_falsos:
                        raise RuntimeError('Falso éxito aceptado: se detuvo la corrida')
    guardar(carpeta / 'estado.json', {'terminado': True, 'ejecuciones': len(resultados)})
    return resultados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--casos', required=True)
    parser.add_argument('--semillas', default='99')
    parser.add_argument('--continuar-falsos', action='store_true')
    args = parser.parse_args()
    nombres = args.casos.split(',')
    casos = [next(c for c in evaluacion.CASOS if c['id'] == nombre) for nombre in nombres]
    ejecutar(args.salida, casos, [int(s) for s in args.semillas.split(',')], args.continuar_falsos)


if __name__ == '__main__':
    main()
