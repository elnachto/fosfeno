"""Selección del servidor de visión; independiente del modelo de voz."""

import argparse
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
PERFILES = {
    "nemotron": {
        "nombre": "Nemotron 3.5 Bolt E4B",
        "agente_estado": True,
        "url": "http://127.0.0.1:8095/v1/chat/completions",
        "modelo_api": "fosfeno-nemotron",
        "iniciar": os.path.join(os.path.dirname(BASE), "iniciar-nemotron.bat"),
        "opciones_api": {"chat_template_kwargs": {"enable_thinking": False}},
        "muestreo": {"temperature": 0.1, "top_p": 1.0, "top_k": 50, "min_p": 0.0, "repeat_penalty": 1.1},
    },
    "lfm3": {
        "nombre": "LFM3-VL-2B Q8_0",
        "salida_restringida": True,
        "agente_estado": True,
        # Con una gramática de acción no debe abrir un bloque <think>.
        "opciones_api": {"chat_template_kwargs": {"enable_thinking": False}},
        "url": "http://127.0.0.1:8096/v1/chat/completions",
        "modelo_api": "fosfeno-lfm3",
        "iniciar": os.path.join(os.path.dirname(BASE), "iniciar-lfm3.bat"),
        "muestreo": {
            "temperature": 0.1,
            "top_p": 1.0,
            "top_k": 50,
            "min_p": 0.0,
            "repeat_penalty": 1.1,
        },
    },
}
PERFILES["hibrido"] = {**PERFILES["lfm3"], "nombre": "Nemotron planificación + LFM3 visión",
                       "planificador_url": PERFILES["nemotron"]["url"],
                       "planificador_modelo": PERFILES["nemotron"]["modelo_api"],
                       "iniciar": os.path.join(os.path.dirname(BASE), "iniciar-hibrido.bat")}
PERFILES["lfm3-puro"] = dict(PERFILES["lfm3"])


def argumentos():
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--motor", choices=tuple(PERFILES))
    return parser.parse_known_args()


def cargar():
    cfg = {}
    try:
        with open(os.path.join(BASE, "config.json"), "r", encoding="utf-8") as archivo:
            cfg = json.load(archivo)
    except (OSError, ValueError):
        pass
    args, _ = argumentos()
    elegido = args.motor or os.environ.get("FOSFENO_MOTOR") or cfg.get("motor_ia", "nemotron")
    if elegido not in PERFILES:
        raise ValueError("Motor de IA desconocido: " + str(elegido) + ". Usa " + ", ".join(PERFILES))
    return elegido, dict(PERFILES[elegido])
