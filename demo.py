import ctypes
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))


class Punto(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def cursor():
    p = Punto()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    proc = subprocess.Popen([sys.executable, os.path.join(BASE, "overlay.py")], stdin=subprocess.PIPE, text=True, encoding="utf-8")

    def enviar(**d):
        proc.stdin.write(json.dumps(d) + "\n")
        proc.stdin.flush()

    def esperar(s):
        time.sleep(s)

    print("Demo del overlay (sin voz ni modelo). Mueve el mouse para que te siga. Ctrl+C para salir.")
    esperar(2.0)
    try:
        while True:
            print("Escuchando...")
            enviar(cmd="estado", valor="escuchando")
            esperar(3.0)
            print("Pensando...")
            enviar(cmd="estado", valor="pensando")
            esperar(2.5)
            x, y = cursor()
            objetivos = [(x + 120, y - 160), (x + 320, y - 40), (x + 140, y + 120)]
            enviar(cmd="estado", valor="idle")
            for i, (ox, oy) in enumerate(objetivos):
                print("Paso", i + 1)
                enviar(cmd="estado", valor="pensando")
                enviar(cmd="plan", hechos=i, activo=True)
                esperar(1.3)
                enviar(cmd="senalar", rect=[ox, oy, ox + 120, oy + 32], texto="Clic: botón " + str(i + 1), duracion=2.4)
                esperar(0.8)
                enviar(cmd="cuenta", segundos=1.0)
                esperar(1.2)
                enviar(cmd="limpiar")
            enviar(cmd="plan", hechos=3, activo=False)
            enviar(cmd="estado", valor="idle")
            print("Feliz")
            enviar(cmd="expresion", valor="feliz", duracion=2.5)
            enviar(cmd="mensaje", texto="Listo.", duracion=2.5)
            esperar(1.0)
            enviar(cmd="plan_fin")
            esperar(2.5)
            print("Confundido")
            enviar(cmd="expresion", valor="confundido", duracion=2.5)
            enviar(cmd="mensaje", texto="No veo cómo hacerlo desde aquí", duracion=2.5)
            esperar(3.5)
            for ex in ("sorprendido", "enamorado", "guiño", "concentrado", "triste", "mareado"):
                print("Expresión:", ex)
                enviar(cmd="expresion", valor=ex, duracion=2.5)
                esperar(3.2)
            print("Respuesta corta")
            enviar(cmd="mensaje", texto="Hola Nachus, aquí estoy", duracion=2.5)
            esperar(4.0)
            print("Otra vuelta en 3 s (deja el mouse quieto 1 min para verlo dormir)")
            esperar(3.0)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            enviar(cmd="salir")
        except Exception:
            pass
        proc.wait(timeout=3)


if __name__ == "__main__":
    main()
