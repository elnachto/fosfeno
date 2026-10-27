import json
import os
import re
import sys
import time

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

RATE = 16000
BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config.json")
VOCAB = os.path.join(BASE, "vocabulario.txt")
CORR = os.path.join(BASE, "correcciones.txt")
HILOS = 6
MODELOS = ["small", "medium", "large-v3-turbo", "large-v3"]
MODELO_DEFECTO = "small"


def leer_config():
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def guardar_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def cargar_vocabulario():
    if not os.path.exists(VOCAB):
        return None
    with open(VOCAB, "r", encoding="utf-8") as f:
        terminos = [linea.strip() for linea in f if linea.strip()]
    if not terminos:
        return None
    return "Conversación en español con un asistente. Términos que pueden aparecer: " + ", ".join(terminos) + "."


def aplicar_correcciones(texto):
    if not os.path.exists(CORR):
        return texto
    with open(CORR, "r", encoding="utf-8") as f:
        for linea in f:
            if "=" not in linea:
                continue
            mal, bien = linea.split("=", 1)
            mal = mal.strip()
            bien = bien.strip()
            if not mal:
                continue
            texto = re.sub(r"\b" + re.escape(mal) + r"\b", lambda m, b=bien: b, texto, flags=re.IGNORECASE)
    return texto


def refrescar_dispositivos():
    try:
        sd._terminate()
        sd._initialize()
    except Exception as e:
        print("No pude refrescar la lista:", e)


def microfonos():
    apis = sd.query_hostapis()
    dispositivos = sd.query_devices()
    lista = []
    vistos = set()
    for i, d in enumerate(dispositivos):
        if d["max_input_channels"] < 1:
            continue
        if "MME" not in apis[d["hostapi"]]["name"]:
            continue
        if d["name"] in vistos:
            continue
        vistos.add(d["name"])
        lista.append((i, d["name"], d["max_input_channels"]))
    if lista:
        return lista
    for i, d in enumerate(dispositivos):
        if d["max_input_channels"] >= 1 and d["name"] not in vistos:
            vistos.add(d["name"])
            lista.append((i, d["name"], d["max_input_channels"]))
    return lista


def probar(idx):
    print("Di algo durante 2 segundos...")
    try:
        datos = sd.rec(int(2 * RATE), samplerate=RATE, channels=1, dtype="float32", device=idx)
        sd.wait()
    except Exception as e:
        print("No se pudo abrir ese micrófono:", e)
        return False
    pico = float(np.max(np.abs(datos))) if datos.size else 0.0
    print("Nivel máximo:", round(pico, 3))
    if pico < 0.01:
        print("AVISO: casi no se oye nada; puede estar mudo o ser un micrófono virtual sin señal")
        return False
    return True


def elegir_microfono(cfg):
    guardado = cfg.get("mic")
    while True:
        lista = microfonos()
        por_defecto = None
        print("Micrófonos disponibles:")
        for n, (idx, nombre, canales) in enumerate(lista, start=1):
            marca = ""
            if guardado and nombre == guardado:
                marca = "  (el último que usaste)"
                por_defecto = n
            print(" ", n, "-", nombre, "[" + str(canales) + " canal(es)]" + marca)
        if not lista:
            print("  (no hay ningún micrófono conectado)")
        if guardado and por_defecto is None:
            print("AVISO: no aparece «" + guardado + "». Si son tus audífonos Bluetooth, conéctalos y escribe r.")
        pregunta = "Número, r = buscar de nuevo"
        if por_defecto:
            pregunta += ", Enter = " + str(por_defecto)
        entrada = input(pregunta + ": ").strip().lower()
        if entrada in ("r", "recargar", "refrescar"):
            refrescar_dispositivos()
            continue
        if not entrada and por_defecto:
            n = por_defecto
        elif entrada.isdigit() and 1 <= int(entrada) <= len(lista):
            n = int(entrada)
        else:
            print("Número no válido")
            continue
        idx, nombre, canales = lista[n - 1]
        ok = probar(idx)
        if not ok:
            otra = input("¿Usar este micrófono de todos modos? (s/n, r = elegir otro): ").strip().lower()
            if otra == "r":
                refrescar_dispositivos()
                continue
            if otra != "s":
                continue
        cfg["mic"] = nombre
        guardar_config(cfg)
        return idx, nombre


def elegir_modelo(actual):
    print("Modelos de voz:")
    for n, nombre in enumerate(MODELOS, start=1):
        marca = "  (en uso)" if nombre == actual else ""
        print(" ", n, "-", nombre + marca)
    entrada = input("Elige el número (Enter = no cambiar): ").strip()
    if entrada.isdigit() and 1 <= int(entrada) <= len(MODELOS):
        return MODELOS[int(entrada) - 1]
    return None


def cargar_modelo(nombre):
    print("Cargando modelo de voz:", nombre, "(la primera vez descarga el archivo)")
    t0 = time.time()
    try:
        modelo = WhisperModel(nombre, device="cpu", compute_type="int8", cpu_threads=HILOS)
    except Exception as e:
        print("No se pudo cargar ese modelo:", e)
        return None
    print("Modelo listo en", round(time.time() - t0, 1), "s")
    return modelo


def grabar(idx):
    trozos = []

    def callback(datos, frames, tiempo, estado):
        trozos.append(datos.copy())

    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", device=idx, callback=callback):
        input("Grabando. Pulsa Enter para terminar...")
    if not trozos:
        return np.zeros(0, dtype="float32")
    return np.concatenate(trozos, axis=0).flatten()


def transcribir(modelo, audio, prompt):
    t1 = time.time()
    segmentos, info = modelo.transcribe(
        audio,
        language="es",
        vad_filter=True,
        beam_size=5,
        initial_prompt=prompt,
        condition_on_previous_text=False,
        temperature=0.0,
    )
    bruto = " ".join(s.text.strip() for s in segmentos).strip()
    texto = aplicar_correcciones(bruto)
    if texto != bruto:
        print("Original:", bruto)
    print("Texto:", texto)
    print("Audio:", round(audio.size / RATE, 1), "s | transcripción:", round(time.time() - t1, 1), "s")
    return texto


def main():
    cfg = leer_config()
    idx, nombre = elegir_microfono(cfg)
    print("Usando:", nombre)
    nombre_modelo = os.environ.get("WHISPER_MODELO") or cfg.get("modelo") or MODELO_DEFECTO
    modelo = cargar_modelo(nombre_modelo)
    if modelo is None and nombre_modelo != MODELO_DEFECTO:
        nombre_modelo = MODELO_DEFECTO
        modelo = cargar_modelo(nombre_modelo)
    if modelo is None:
        sys.exit(1)
    ultimo = None
    while True:
        orden = input("Enter = grabar | r = repetir el último audio | w = cambiar modelo | m = cambiar micrófono | q = salir: ").strip().lower()
        if orden == "q":
            break
        if orden == "m":
            idx, nombre = elegir_microfono(cfg)
            print("Usando:", nombre)
            continue
        if orden == "w":
            elegido = elegir_modelo(nombre_modelo)
            if elegido and elegido != nombre_modelo:
                nuevo = cargar_modelo(elegido)
                if nuevo is not None:
                    modelo = nuevo
                    nombre_modelo = elegido
                    cfg["modelo"] = elegido
                    guardar_config(cfg)
            continue
        if orden == "r":
            if ultimo is None:
                print("Todavía no hay audio grabado")
                continue
            print("Modelo:", nombre_modelo)
            transcribir(modelo, ultimo, cargar_vocabulario())
            continue
        audio = grabar(idx)
        if audio.size < RATE // 2:
            print("Audio muy corto")
            continue
        ultimo = audio
        print("Modelo:", nombre_modelo)
        transcribir(modelo, audio, cargar_vocabulario())


if __name__ == "__main__":
    main()
