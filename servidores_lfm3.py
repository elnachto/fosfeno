"""Arranca los servidores locales de planificación y visión, sin operar la PC."""

import json
import argparse
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

BASE = Path(__file__).resolve().parent
RAIZ = BASE.parent
RUNTIME = RAIZ / "llama-lfm3-b11946"
MODELOS = RAIZ / "lfm3"
SERVIDORES = [
    {"nombre": "Nemotron", "puerto": 8095, "alias": "fosfeno-nemotron", "archivo": "../bolt/NVIDIA-Nemotron-3.5-Bolt-E4B-UD-Q4_K_XL.gguf", "vision": "../bolt/mmproj-F16.gguf"},
    {"nombre": "visión", "puerto": 8096, "alias": "fosfeno-lfm3", "archivo": "LFM3-VL-2B-Q8_0.gguf", "vision": "mmproj-LFM3-VL-2B-F16.gguf"},
]


def estado(servidor):
    base = "http://127.0.0.1:" + str(servidor["puerto"])
    try:
        with urllib.request.urlopen(base + "/health", timeout=2) as respuesta:
            listo = json.load(respuesta).get("status") == "ok"
        if listo:
            with urllib.request.urlopen(base + "/props", timeout=2) as respuesta:
                props = json.load(respuesta)
            if props.get("model_alias") != servidor["alias"]:
                if Path(props.get("model_path", "")).name != Path(servidor["archivo"]).name:
                    raise RuntimeError("El puerto " + str(servidor["puerto"]) + " pertenece a otro modelo")
            if servidor.get("vision") and not props.get("modalities", {}).get("vision"):
                raise RuntimeError("El servidor " + str(servidor["puerto"]) + " está activo sin visión. Ciérralo y vuelve a iniciar este acceso.")
        return listo
    except (urllib.error.URLError, TimeoutError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--motor", choices=("lfm3", "nemotron", "hibrido"), default="lfm3")
    args = parser.parse_args()
    servidores = [s for s in SERVIDORES if args.motor == "hibrido" or (s["puerto"] == 8095) == (args.motor == "nemotron")]
    procesos = []
    archivos = []
    try:
        for servidor in servidores:
            if estado(servidor):
                print("Reutilizando servidor de " + servidor["nombre"], flush=True)
                continue
            modelo = MODELOS / servidor["archivo"]
            exe = RUNTIME / "llama-server.exe"
            for ruta in (modelo, exe):
                if not ruta.is_file():
                    raise FileNotFoundError("Falta " + str(ruta))
            comando = [str(exe), "-m", str(modelo), "--alias", servidor["alias"], "-ngl", "99",
                       "-c", "16384", "-np", "1", "-fa", "on", "--jinja", "--host", "127.0.0.1",
                       "--port", str(servidor["puerto"]), "--temp", "0.1", "--top-p", "1", "--top-k", "50",
                       "--min-p", "0", "--repeat-penalty", "1.1", "--no-reasoning-preserve"]
            if servidor.get("vision"):
                vision = MODELOS / servidor["vision"]
                if not vision.is_file():
                    raise FileNotFoundError(vision)
                comando.extend(["--mmproj", str(vision)])
            carpeta = BASE / "salidas"
            carpeta.mkdir(exist_ok=True)
            log = (carpeta / ("servidor-" + str(servidor["puerto"]) + ".log")).open("ab")
            archivos.append(log)
            entorno = dict(os.environ, CUDA_VISIBLE_DEVICES="0")
            proc = subprocess.Popen(comando, cwd=RUNTIME, env=entorno, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            procesos.append(proc)
            inicio = time.monotonic()
            while not estado(servidor):
                if proc.poll() is not None:
                    raise RuntimeError("El servidor se cerró. Revisa " + str(log.name))
                if time.monotonic() - inicio > 120:
                    raise TimeoutError("El servidor tarda demasiado. Revisa " + str(log.name))
                time.sleep(0.5)
            print("Listo: " + servidor["nombre"] + " en " + str(servidor["puerto"]), flush=True)
        print("Motor " + args.motor + " preparado. Abre fosfeno-" + args.motor + ".bat. Ctrl+C cierra los servidores iniciados aquí.", flush=True)
        while True:
            for proc in procesos:
                if proc.poll() is not None:
                    raise RuntimeError("Uno de los servidores se cerró; revisa salidas/servidor-*.log")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Cerrando los servidores iniciados en esta ventana.")
    finally:
        for proc in procesos:
            if proc.poll() is None:
                proc.terminate()
        for proc in procesos:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        for archivo in archivos:
            archivo.close()


if __name__ == "__main__":
    main()
