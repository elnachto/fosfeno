import ctypes
import importlib.util
import json
import os
import random
import subprocess
import sys
import threading
import time
import winsound
from ctypes import wintypes

import numpy as np
import requests
import sounddevice as sd

import acciones
import agente
import marcas
import memoria
import voz

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
kernel32.GetConsoleWindow.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
ID_SENALAR = 1
ID_ACTUAR = 2
SEGUNDOS_SENAL = 6
VUELO_ESPERA = 0.8
CUENTA_ATRAS = 1.0
MAX_PASOS = 24
CONFIRMAR_SEGUNDOS = 20
MIN_CARACTERES = 3
OFERTA_SEGUNDOS = 10
ESTADO = {"ultimo": None, "pendiente": None}
CONFIG = {}
SOCIAL = {
    "GRACIAS": ("enamorado", ["¡De nada!", "¡Para eso estoy!", "¡Un placer ayudarte!"], 2.6),
    "CARINO": ("enamorado", ["Aww, qué lindo. ¡Seguimos!", "¡Gracias! Me alegra ayudarte"], 3.0),
    "SALUDO": ("guiño", ["¡Hola! ¿Qué hacemos?", "¡Hey! Aquí estoy", "¡Hola! Dime qué necesitas"], 2.6),
    "ELOGIO": ("feliz", ["¡Gracias! Me esfuerzo", "¡Seguimos así!", "Jeje, gracias"], 2.6),
    "DESPEDIDA": ("feliz", ["¡Hasta luego!", "¡Nos vemos!"], 2.6),
    "NOCHES": ("dormido", ["Buenas noches, que descanses"], 4.0),
    "DISCULPA": ("feliz", ["Tranquilo, no pasa nada", "Sin problema"], 2.6),
    "QUEJA": ("triste", ["Ups, perdón. Dime «no, era…» y lo corrijo", "Lo siento. Dime qué hice mal y lo anoto"], 4.0),
    "ASOMBRO": ("sorprendido", ["¡Sí! ¿Verdad?", "¡Wow!"], 2.6),
    "ESTADO": ("feliz", ["¡Muy bien! Listo para ayudar", "Todo en orden. ¿Qué hacemos?"], 2.8),
    "IDENTIDAD": ("feliz", ["Soy Fosfeno, tu asistente local. Veo tu pantalla y te ayudo a usarla"], 4.5),
    "ENTENDIDO": ("guiño", ["¡Dale!", "¡Listo!"], 2.0),
}
LETRAS = {"senalar": "J", "actuar": "K"}
COLOR = "#22d3ee"
FONDO = "#0f172a"


def servidor_listo():
    try:
        urls = [marcas.URL]
        if marcas.PERFIL.get("agente_estado") and marcas.PERFIL.get("planificador_url"):
            urls.append(marcas.PERFIL["planificador_url"])
        return all(requests.get(url.rsplit("/v1/", 1)[0] + "/health", timeout=3).status_code == 200 for url in urls)
    except Exception:
        return False


def registrar_tecla(ident, letra):
    return bool(user32.RegisterHotKey(None, ident, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(letra.upper())))


def esperar_tecla():
    msg = wintypes.MSG()
    while True:
        if user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1):
            return int(msg.wParam)
        time.sleep(0.03)


class Grabador:
    def __init__(self, idx):
        self.idx = idx
        self.trozos = []
        self.flujo = None

    def iniciar(self):
        self.trozos = []

        def callback(datos, frames, tiempo, estado):
            self.trozos.append(datos.copy())

        self.flujo = sd.InputStream(samplerate=voz.RATE, channels=1, dtype="float32", device=self.idx, callback=callback)
        self.flujo.start()

    def detener(self):
        if self.flujo is not None:
            self.flujo.stop()
            self.flujo.close()
            self.flujo = None
        if not self.trozos:
            return np.zeros(0, dtype="float32")
        return np.concatenate(self.trozos, axis=0).flatten()


def transcribir_en_hilo(modelo, audio, resultado):
    def tarea():
        try:
            resultado["texto"] = voz.transcribir(modelo, audio, voz.cargar_vocabulario())
        except Exception as e:
            resultado["error"] = str(e)

    hilo = threading.Thread(target=tarea)
    hilo.start()
    return hilo


class Capa:
    def __init__(self):
        self.proc = None

    def iniciar(self, buddy):
        if importlib.util.find_spec("PySide6") is None:
            print("PySide6 no está instalado: uso la señal sencilla. Para la animada: python -m pip install PySide6")
            return False
        ruta = os.path.join(marcas.BASE, "overlay.py")
        entorno = dict(os.environ)
        entorno["JARVIS_BUDDY"] = "1" if buddy else "0"
        try:
            self.proc = subprocess.Popen(
                [sys.executable, ruta],
                stdin=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=entorno,
            )
        except Exception as e:
            print("No pude arrancar la capa animada:", e)
            self.proc = None
            return False
        time.sleep(1.5)
        if self.proc.poll() is not None:
            print("La capa animada se cerró al arrancar; uso la señal sencilla.")
            self.proc = None
            return False
        return True

    def activa(self):
        return self.proc is not None and self.proc.poll() is None

    def enviar(self, **datos):
        if not self.activa():
            return False
        try:
            self.proc.stdin.write(json.dumps(datos) + "\n")
            self.proc.stdin.flush()
            return True
        except Exception:
            return False

    def cerrar(self):
        if self.proc is not None and self.proc.poll() is None:
            self.enviar(cmd="salir")
            try:
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()


capa = Capa()


def rectangulo_redondeado(lienzo, x0, y0, x1, y1, r, **kw):
    puntos = [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]
    return lienzo.create_polygon(puntos, smooth=True, **kw)


def etiqueta(elemento):
    nombre = elemento[1]
    if not nombre:
        return "Aquí"
    corto = nombre.split(" - ")[0]
    if len(corto) > 32:
        corto = corto[:31].rstrip() + "…"
    return corto


def mostrar_senal(rect, punto, segundos, texto):
    try:
        import tkinter as tk
        import tkinter.font as tkfont
    except Exception:
        return False
    try:
        ancho = user32.GetSystemMetrics(0)
        alto = user32.GetSystemMetrics(1)
        raiz = tk.Tk()
        raiz.overrideredirect(True)
        raiz.attributes("-topmost", True)
        raiz.attributes("-transparentcolor", "black")
        raiz.geometry(str(ancho) + "x" + str(alto) + "+0+0")
        lienzo = tk.Canvas(raiz, width=ancho, height=alto, bg="black", highlightthickness=0)
        lienzo.pack()
        x0, y0, x1, y1 = rect
        cx, cy = punto
        margen = 6
        rectangulo_redondeado(lienzo, x0 - margen, y0 - margen, x1 + margen, y1 + margen, 12, outline=COLOR, fill="", width=4)
        fuente = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        caja_w = fuente.measure(texto) + 28
        caja_h = fuente.metrics("linespace") + 16
        hueco = 16
        arriba = y0 - margen - hueco - caja_h > 8
        if arriba:
            base_y = y0 - margen - hueco
            caja_y0 = base_y - caja_h
            caja_y1 = base_y
            punta_y = y0 - margen - 2
        else:
            base_y = y1 + margen + hueco
            caja_y0 = base_y
            caja_y1 = base_y + caja_h
            punta_y = y1 + margen + 2
        caja_x0 = int(min(max(cx - caja_w / 2, 8), ancho - caja_w - 8))
        caja_x1 = caja_x0 + caja_w
        lienzo.create_polygon(cx - 9, base_y, cx + 9, base_y, cx, punta_y, fill=COLOR, outline=COLOR)
        rectangulo_redondeado(lienzo, caja_x0, caja_y0, caja_x1, caja_y1, 12, fill=FONDO, outline=COLOR, width=3)
        lienzo.create_text((caja_x0 + caja_x1) / 2, (caja_y0 + caja_y1) / 2, text=texto, fill="white", font=fuente)
        anillos = [
            lienzo.create_oval(cx, cy, cx, cy, outline=COLOR, width=3),
            lienzo.create_oval(cx, cy, cx, cy, outline=COLOR, width=3),
        ]
        raiz.update_idletasks()
        raiz.update()
        hwnd = user32.GetParent(raiz.winfo_id()) or raiz.winfo_id()
        estilo = user32.GetWindowLongW(hwnd, -20)
        user32.SetWindowLongW(hwnd, -20, estilo | 0x00080000 | 0x00000020 | 0x08000000 | 0x00000080)
        inicio = time.time()

        def paso():
            t = time.time() - inicio
            if t >= segundos:
                raiz.destroy()
                return
            for k, anillo in enumerate(anillos):
                fase = (t + k * 0.5) % 1.0
                radio = 14 + 34 * fase
                grosor = max(1, int(5 * (1 - fase)))
                lienzo.coords(anillo, cx - radio, cy - radio, cx + radio, cy + radio)
                lienzo.itemconfigure(anillo, width=grosor)
            raiz.after(33, paso)

        paso()
        raiz.mainloop()
        return True
    except Exception as e:
        print("No se pudo dibujar la señal en pantalla:", e)
        return False


def frase(elemento):
    tipo, nombre, x0, y0, x1, y1 = elemento
    ancho = marcas.MONITOR["width"] or user32.GetSystemMetrics(0)
    alto = marcas.MONITOR["height"] or user32.GetSystemMetrics(1)
    cx, cy = marcas.a_local((x0 + x1) // 2, (y0 + y1) // 2)
    z = marcas.zona(cx, cy, ancho, alto).replace("-", ", ")
    if tipo.startswith("BarraDeTareas:"):
        return "En la barra de tareas, pulsa «" + etiqueta(elemento) + "» (" + z + ")."
    return "Pulsa «" + etiqueta(elemento) + "» (" + z + ")."


def es_mi_consola(titulo):
    try:
        h = kernel32.GetConsoleWindow()
        if h and h == user32.GetForegroundWindow():
            return True
    except Exception:
        pass
    return "jarvis.py" in (titulo or "").lower()


def control(modo):
    capa.enviar(cmd="control", activo=True, modo=modo, ocultar=bool(CONFIG.get("ocultar_cursor", True)))


def avisar(texto, duracion=3.5, expresion=None):
    print(texto)
    if expresion:
        capa.enviar(cmd="expresion", valor=expresion, duracion=duracion)
    capa.enviar(cmd="mensaje", texto=texto, duracion=duracion)


def escanear():
    capa.enviar(cmd="ocultar")
    if capa.activa():
        time.sleep(0.15)
    img = marcas.grab()
    capa.enviar(cmd="mostrar_capa")
    ancho, alto = img.size
    titulo, elementos, truncado = marcas.reunir(ancho, alto)
    return img, titulo, elementos


def mostrar_elemento(elemento, punto, rect, duracion, texto):
    if capa.enviar(cmd="senalar", rect=list(rect), texto=texto, duracion=duracion):
        return True
    return mostrar_senal(rect, punto, duracion, texto)


def esperar_cancelacion(segundos):
    fin = time.time() + segundos
    while time.time() < fin:
        if acciones.esc_presionado():
            return True
        time.sleep(0.02)
    return False


def guardar_exito(app, objetivo, pasos):
    def tarea():
        try:
            limpios = marcas.depurar_pasos(objetivo, pasos)
        except Exception:
            limpios = pasos
        memoria.guardar_receta(app, objetivo, limpios, "exito", crudos=pasos)

    threading.Thread(target=tarea, daemon=True).start()


def ejecutar(objetivo, escaneo, sello):
    img, titulo, elementos = escaneo
    historial = []
    anterior = None
    traza = []
    feedback = ""
    verificaciones_fallidas = 0
    estado_anterior = None
    pendiente = None
    ruta_log = os.path.join(marcas.OUT, "log_actuar_" + sello + ".txt")
    app_inicial = memoria.app_de(titulo)
    control("pensar")
    partes = marcas.partir_objetivo(objetivo)
    compuesto = len(partes) > 1
    ejemplos = "" if compuesto else memoria.texto_recetas(memoria.buscar_recetas(objetivo, app_inicial))
    with open(ruta_log, "w", encoding="utf-8") as log:
        log.write("MOTOR: " + marcas.PERFIL["nombre"] + "\n")
        log.write("OBJETIVO: " + objetivo + "\n")
        if compuesto:
            print("Partes:", " | ".join(partes))
            log.write("PARTES:\n" + "\n".join(str(i) + ") " + p for i, p in enumerate(partes, start=1)) + "\n")
        if ejemplos:
            print("Uso recetas aprendidas:\n" + ejemplos)
            log.write("RECETAS:\n" + ejemplos + "\n")
        for paso in range(1, MAX_PASOS + 1):
            capa.enviar(cmd="estado", valor="pensando")
            capa.enviar(cmd="plan", hechos=len(historial), activo=True)
            control("pensar")
            if paso > 1:
                time.sleep(0.45)
                img, titulo, elementos = escanear()
            estado_actual = dict(marcas.ESTADO_UI)
            if traza and estado_anterior is not None:
                cambio = agente.huella(estado_anterior, traza[-1].pop("_elementos", elementos)) != agente.huella(estado_actual, elementos)
                traza[-1]["resultado"] = {"cambio_observable": cambio,
                    "ventana": titulo, "foco": estado_actual.get("foco", {})}
                log.write("OBSERVADO: " + json.dumps(traza[-1]["resultado"], ensure_ascii=False) + "\n")
            if es_mi_consola(titulo):
                log.write("\n--- PASO " + str(paso) + " | " + titulo + " ---\nPARADO: la ventana activa es la consola de Jarvis\n")
                avisar("Estoy en mi propia consola, paro aquí", expresion="confundido")
                return
            if not elementos:
                avisar("No puedo ver los botones de esta ventana", expresion="triste")
                return
            continuacion = agente.continuar_pendiente(pendiente, estado_actual, elementos)
            pendiente = None
            if continuacion:
                accion, respuesta, lista, marcada, seg = continuacion, "Continuación de escritura con foco comprobado", marcas.construir_lista(elementos, *img.size), marcas.marcar(img, elementos), 0.0
            else:
                accion, respuesta, lista, marcada, seg = marcas.decidir_accion(objetivo, img, titulo, elementos, historial, ejemplos, partes,
                    estado=estado_actual, traza=traza, feedback=feedback)
            feedback = ""
            try:
                marcada.save(os.path.join(marcas.OUT, "actuar_" + sello + "_p" + str(paso) + ".jpg"), quality=85)
            except Exception:
                pass
            log.write("\n--- PASO " + str(paso) + " | " + titulo + " ---\nELEMENTOS (" + str(len(elementos)) + "):\n" + lista + "\n\nMODELO:\n" + respuesta + "\n")
            log.flush()
            if accion is None:
                print("Respuesta del modelo sin una acción válida:", repr(respuesta[:500]))
                avisar("No entendí qué hacer", expresion="confundido")
                return
            tipo = accion["tipo"]
            print("Paso", paso, "->", tipo, "(modelo:", round(seg, 1), "s)")
            verificacion_previa = None
            if tipo == "nada" and marcas.PERFIL.get("agente_estado"):
                verificacion_previa = agente.verificar(objetivo, elementos, estado_actual, historial, marcas.preguntar_json, img)
                if agente.final_confirmado(verificacion_previa):
                    tipo = "listo"
            if tipo == "listo":
                verificado = False
                if marcas.PERFIL.get("agente_estado"):
                    verificacion = verificacion_previa or agente.verificar(objetivo, elementos, estado_actual, historial, marcas.preguntar_json, img)
                    log.write("VERIFICACION: " + json.dumps(verificacion, ensure_ascii=False) + "\n")
                    verificado = agente.final_confirmado(verificacion)
                    if not verificado:
                        verificaciones_fallidas += 1
                        feedback = "El objetivo NO está cumplido. Falta: " + verificacion.get("pendiente", "evidencia observable")
                        if verificaciones_fallidas >= 3:
                            avisar("No pude comprobar que la tarea esté terminada.", expresion="confundido")
                            return
                        continue
                if historial and not compuesto and verificado:
                    guardar_exito(app_inicial, objetivo, [("dije lo que se veía en pantalla" if h.startswith("dije «") else h) for h in historial])
                capa.enviar(cmd="plan", hechos=len(historial), activo=False)
                capa.enviar(cmd="estado", valor="idle")
                avisar("Listo.", 2.5, expresion="feliz")
                return
            if tipo == "nada":
                avisar("No veo cómo hacerlo desde aquí.", expresion="confundido")
                return
            clave = agente.clave_accion(accion, elementos)
            if agente.repetida_sin_progreso(accion, elementos, traza):
                feedback = "La misma acción ya se ejecutó, aunque su número haya cambiado. Elige un paso diferente."
                if paso == MAX_PASOS:
                    avisar("No pude avanzar después de reintentar.", expresion="confundido")
                    return
                continue
            anterior = clave
            # Si el usuario cambió de ventana mientras el modelo decidía, no actuar allí.
            actual = marcas.capturar_estado(marcas.nombre_ventana(), elementos)
            if estado_actual.get("hwnd") and actual.get("hwnd") != estado_actual["hwnd"]:
                avisar("Cambió la ventana activa. Me detuve para no actuar en otra aplicación.", expresion="confundido")
                return
            estado_anterior = estado_actual
            inicio_historial = len(historial)
            if tipo == "clic":
                elemento = elementos[accion["n"] - 1]
                rect = (elemento[2], elemento[3], elemento[4], elemento[5])
                punto = ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
                texto = "Clic: " + etiqueta(elemento)
                print(texto)
                if capa.activa():
                    capa.enviar(cmd="expresion", valor="concentrado", duracion=3.0)
                    capa.enviar(cmd="senalar", rect=list(rect), texto=texto, duracion=3.0)
                    time.sleep(VUELO_ESPERA)
                    capa.enviar(cmd="cuenta", segundos=CUENTA_ATRAS)
                    cancelado = esperar_cancelacion(CUENTA_ATRAS)
                else:
                    mostrar_senal(rect, punto, 1.4, texto)
                    cancelado = acciones.esc_presionado()
                if cancelado:
                    capa.enviar(cmd="limpiar")
                    avisar("Cancelado.")
                    return
                control("mover")
                if not marcas.validar_destino(elemento, estado_actual.get("hwnd")):
                    feedback = "El control cambió después de observarlo. Identifica de nuevo el destino en la pantalla actual."
                    anterior = None
                    continue
                if not acciones.mover_suave(punto[0], punto[1]):
                    capa.enviar(cmd="limpiar")
                    avisar("Cancelado.")
                    return
                capa.enviar(cmd="toque")
                if not acciones.clic(punto[0], punto[1]):
                    avisar("Cancelado.")
                    return
                capa.enviar(cmd="limpiar")
                historial.append("clic en «" + etiqueta(elemento) + "»")
                log.write("EJECUTADO: " + historial[-1] + "\n")
            elif tipo == "escribir":
                if marcas.PERFIL.get("agente_estado"):
                    foco = actual.get("foco", {})
                    elegido = estado_actual.get("foco", {})
                    if not foco.get("editable") or foco.get("secreto") or foco.get("nombre") != elegido.get("nombre"):
                        feedback = "El foco cambió o no es editable. Observa de nuevo antes de escribir."
                        anterior = None
                        continue
                print("Escribo:", accion["texto"])
                capa.enviar(cmd="mensaje", texto="Escribo: " + accion["texto"][:30], duracion=1.5)
                if esperar_cancelacion(0.6):
                    avisar("Cancelado.")
                    return
                comprobado = marcas.capturar_estado(marcas.nombre_ventana(), elementos)
                if (estado_actual.get("hwnd") and comprobado.get("hwnd") != estado_actual["hwnd"]) or comprobado.get("foco", {}).get("n") != actual.get("foco", {}).get("n"):
                    avisar("Cambió el foco antes de escribir. Me detuve.", expresion="confundido")
                    return
                control("escribir")
                if accion.get("reemplazar") and not acciones.tecla("ctrl+a"):
                    avisar("Cancelado.")
                    return
                if not acciones.escribir(accion["texto"]):
                    avisar("Cancelado durante la escritura.")
                    return
                historial.append("escribí «" + accion["texto"] + "»")
                log.write("EJECUTADO: " + historial[-1] + "\n")
            elif tipo == "decir":
                texto_d = accion["texto"][:300]
                print("Digo:", texto_d)
                capa.enviar(cmd="estado", valor="idle")
                capa.enviar(cmd="expresion", valor="feliz", duracion=2.0)
                capa.enviar(cmd="mensaje", texto=texto_d, duracion=min(14.0, 3.0 + len(texto_d) / 14.0))
                historial.append("dije «" + texto_d + "»")
                log.write("EJECUTADO: " + historial[-1] + "\n")
                if esperar_cancelacion(min(7.0, 1.5 + len(texto_d) / 30.0)):
                    avisar("Cancelado.")
                    return
            elif tipo == "tecla":
                print("Tecla:", accion["tecla"])
                control("escribir")
                if not acciones.tecla(accion["tecla"]):
                    avisar("Cancelado.")
                    return
                historial.append("pulsé la tecla " + accion["tecla"])
                log.write("EJECUTADO: " + historial[-1] + "\n")
            elif tipo == "esperar":
                if esperar_cancelacion(1.0):
                    avisar("Cancelado.")
                    return
                historial.append("esperé a que cargara la interfaz")
                anterior = None
            elif tipo == "desplazar":
                if not acciones.desplazar(accion["direccion"]):
                    avisar("Cancelado.")
                    return
                historial.append("desplacé la vista hacia " + accion["direccion"])
            if len(historial) > inicio_historial:
                pendiente = accion.get("_despues")
                traza.append({"clave": repr(clave), "accion": historial[-1],
                              "objetivo": accion.get("_objetivo", ""), "_elementos": elementos})
            log.flush()
        avisar("Llegué al máximo de pasos.", expresion="triste")


def procesar(modelo, audio, modo_actuar):
    if audio.size < voz.RATE // 2:
        print("Audio muy corto")
        capa.enviar(cmd="estado", valor="idle")
        return
    os.makedirs(marcas.OUT, exist_ok=True)
    sello = str(int(time.time()))
    resultado = {}
    inicio = time.time()
    hilo = transcribir_en_hilo(modelo, audio, resultado)
    escaneo = escanear()
    hilo.join()
    img, titulo, elementos = escaneo
    if "error" in resultado:
        print("Error de voz:", resultado["error"])
        capa.enviar(cmd="estado", valor="idle")
        return
    texto = resultado.get("texto", "").strip()
    if len(texto) < MIN_CARACTERES:
        avisar("No entendí nada", expresion="confundido")
        capa.enviar(cmd="estado", valor="idle")
        return
    continuar(texto, escaneo, sello, inicio, modo_actuar)


def procesar_texto(texto, modo_actuar):
    os.makedirs(marcas.OUT, exist_ok=True)
    sello = str(int(time.time()))
    inicio = time.time()
    escaneo = escanear()
    continuar(texto, escaneo, sello, inicio, modo_actuar)


def continuar(texto, escaneo, sello, inicio, forzar_hacer):
    img, titulo, elementos = escaneo
    print("Dijiste:", texto)
    print("Ventana:", titulo, "| elementos:", len(elementos))
    capa.enviar(cmd="mensaje", texto="«" + (texto if len(texto) <= 70 else texto[:69] + "…") + "»", duracion=1.8)
    tipo = marcas.clasificar(texto, forzar_hacer)
    print("Intención:", tipo)
    app = memoria.app_de(titulo)
    try:
        if tipo == "APRENDER":
            aprender(memoria.objetivo_de_demo(texto), titulo, sello)
        elif tipo == "EXPLORAR":
            explorar(escaneo, app, sello)
        elif tipo == "CORREGIR":
            corregir(texto, app)
        elif tipo == "OLVIDAR":
            olvidar()
        elif tipo == "REPASAR":
            repasar(app)
        elif tipo == "SOCIAL":
            socializar(texto)
        elif tipo == "PREGUNTA":
            ESTADO["ultimo"] = {"app": app, "objetivo": texto}
            responder(texto, escaneo)
        elif tipo == "HACER":
            ESTADO["ultimo"] = {"app": app, "objetivo": texto}
            try:
                ejecutar(texto, escaneo, sello)
            finally:
                capa.enviar(cmd="control", activo=False)
                capa.enviar(cmd="plan_fin")
        else:
            ESTADO["ultimo"] = {"app": app, "objetivo": texto}
            guiar(texto, escaneo, sello, inicio)
    except (marcas.ErrorRespuestaModelo, OSError) as error:
        print("Error de respuesta del modelo:", error)
        avisar("El modelo no devolvió una respuesta final. Revisa el aviso de la consola.", expresion="confundido")
    finally:
        capa.enviar(cmd="estado", valor="idle")


def socializar(texto):
    tipo = marcas.tipo_social(texto)
    expr, frases, dur = SOCIAL.get(tipo, ("feliz", ["¡Aquí estoy!"], 2.5))
    capa.enviar(cmd="estado", valor="idle")
    avisar(random.choice(frases), dur, expresion=expr)


def responder(texto, escaneo):
    img, titulo, elementos = escaneo
    try:
        respuesta = marcas.responder(texto, img, titulo)
    except Exception as e:
        print("Error al responder:", e)
        avisar("No pude pensar una respuesta", expresion="triste")
        return
    if not respuesta:
        avisar("No sé qué responder a eso", expresion="confundido")
        return
    capa.enviar(cmd="estado", valor="idle")
    avisar(respuesta, min(22.0, 4.0 + len(respuesta) / 14.0), expresion="feliz")


def guiar(texto, escaneo, sello, inicio):
    img, titulo, elementos = escaneo
    if not elementos:
        avisar("No puedo ver los botones de esa ventana todavía", expresion="confundido")
        return
    n, respuesta, lista, marcada, seg = marcas.decidir(texto, img, titulo, elementos)
    with open(os.path.join(marcas.OUT, "log_jarvis_" + sello + ".txt"), "w", encoding="utf-8") as f:
        f.write("DIJISTE: " + texto + "\nVENTANA: " + titulo + "\n\n" + lista + "\n\n--- RESPUESTA ---\n" + respuesta + "\n")
    if n is None:
        avisar("No entendí la respuesta del modelo", expresion="confundido")
        return
    if n == 0:
        avisar("No veo nada en esta pantalla que sirva para eso", expresion="confundido")
        return
    elemento = elementos[n - 1]
    final, punto = marcas.dibujar_resultado(img, elemento)
    print(frase(elemento))
    print("Tiempo total:", round(time.time() - inicio, 1), "s (modelo:", round(seg, 1), "s)")
    rect = (elemento[2], elemento[3], elemento[4], elemento[5])
    texto_senal = etiqueta(elemento) + "  ·  ¿lo hago? Ctrl+Alt+" + LETRAS["actuar"]
    if mostrar_elemento(elemento, punto, rect, SEGUNDOS_SENAL, texto_senal):
        ESTADO["pendiente"] = {"texto": texto, "hasta": time.time() + OFERTA_SEGUNDOS}
        print("Si quieres que lo haga yo, pulsa Ctrl+Alt+" + LETRAS["actuar"] + " en los próximos " + str(OFERTA_SEGUNDOS) + " s.")
    else:
        ruta = os.path.join(marcas.OUT, "resultado_jarvis_" + sello + ".png")
        final.save(ruta)
        print("Señal guardada en:", ruta)


def explorar(escaneo, app, sello):
    img, titulo, elementos = escaneo
    if not elementos:
        avisar("No veo elementos en esta ventana para explorar", expresion="confundido")
        return
    capa.enviar(cmd="mensaje", texto="Explorando " + (app or "esta app") + "…", duracion=30)
    try:
        mapa, crudo = marcas.explorar(img, titulo, elementos)
    except Exception as e:
        print("Error al explorar:", e)
        avisar("No pude explorar esta app", expresion="triste")
        return
    with open(os.path.join(marcas.OUT, "log_explorar_" + sello + ".txt"), "w", encoding="utf-8") as f:
        f.write("VENTANA: " + titulo + "\n\n" + crudo + "\n")
    if not mapa:
        avisar("No me salió un mapa útil, prueba otra vez", expresion="confundido")
        return
    ruta = memoria.guardar_mapa(app, mapa)
    print("Mapa guardado en", ruta + ":\n" + mapa)
    capa.enviar(cmd="estado", valor="idle")
    avisar("Listo, ya conozco " + (app or "esta app"), 3.0, expresion="enamorado")


def olvidar():
    quitada = memoria.borrar_ultima_receta()
    if quitada is None:
        avisar("No tengo nada aprendido que olvidar", expresion="confundido")
        return
    print("Olvidé la receta:", quitada.get("objetivo"), "(" + str(quitada.get("app")) + ")")
    capa.enviar(cmd="estado", valor="idle")
    avisar("Olvidé «" + quitada.get("objetivo", "")[:50] + "»", 3.0)


def repasar(app):
    recetas = memoria.recetas_de_app(app)
    if not recetas:
        avisar("Todavía no aprendí nada en " + (app or "esta app"), 3.0)
        return
    vistas = []
    for r in reversed(recetas):
        o = r.get("objetivo", "")
        if o not in vistas:
            vistas.append(o)
        if len(vistas) >= 5:
            break
    texto = "En " + app + " sé: " + "; ".join("«" + (o if len(o) <= 45 else o[:44] + "…") + "»" for o in vistas)
    print(texto)
    capa.enviar(cmd="estado", valor="idle")
    avisar(texto, min(15.0, 4.0 + len(texto) / 15.0))


def esperar_decision(segundos):
    msg = wintypes.MSG()
    fin = time.time() + segundos
    while time.time() < fin:
        if user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1):
            return int(msg.wParam)
        time.sleep(0.05)
    return None


def corregir(texto, app):
    ultimo = ESTADO.get("ultimo")
    destino = (ultimo or {}).get("app") or app
    if not destino:
        avisar("No sé a qué app se refiere la corrección", expresion="confundido")
        return
    nota = memoria.limpiar_correccion(texto)
    if ultimo and ultimo.get("objetivo"):
        nota += " (cuando me pediste: «" + ultimo["objetivo"] + "»)"
    ruta = memoria.agregar_nota(destino, nota)
    print("Anotado en", ruta + ":", nota)
    capa.enviar(cmd="estado", valor="idle")
    avisar("Anotado para " + destino, 2.5, expresion="guiño")


def aprender(objetivo, titulo, sello):
    import mirame

    if not objetivo:
        avisar("Dime qué me enseñas, por ejemplo: mírame cómo se abre una pestaña", 4.0, expresion="confundido")
        return
    demo = mirame.Demostracion()
    demo.iniciar()
    capa.enviar(cmd="estado", valor="observando")
    capa.enviar(cmd="plan", hechos=0, activo=True)
    winsound.Beep(660, 90)
    print("Te estoy mirando: haz la tarea «" + objetivo + "» y pulsa Ctrl+Alt+" + LETRAS["senalar"] + " cuando termines.")
    msg = wintypes.MSG()
    vistos = 0
    while True:
        if user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1):
            break
        n = len(demo.pasos)
        if n != vistos:
            for paso in demo.pasos[vistos:n]:
                print("  paso:", paso)
            vistos = n
            capa.enviar(cmd="plan", hechos=n, activo=True)
            capa.enviar(cmd="mensaje", texto=demo.pasos[-1][:60], duracion=1.8)
        time.sleep(0.1)
    pasos, titulo_app = demo.detener()
    winsound.Beep(520, 90)
    capa.enviar(cmd="estado", valor="idle")
    capa.enviar(cmd="plan", hechos=len(pasos), activo=False)
    if not pasos:
        avisar("No vi ningún paso", expresion="confundido")
        capa.enviar(cmd="plan_fin")
        return
    app = memoria.app_de(titulo_app) or memoria.app_de(titulo)
    capa.enviar(cmd="estado", valor="pensando")
    capa.enviar(cmd="mensaje", texto="Repasando lo que hiciste…", duracion=20)
    limpios = memoria.limpiar_pasos(pasos)
    limpios = marcas.depurar_pasos(objetivo, limpios) if limpios else []
    capa.enviar(cmd="estado", valor="idle")
    with open(os.path.join(marcas.OUT, "log_aprender_" + sello + ".txt"), "w", encoding="utf-8") as f:
        f.write("OBJETIVO: " + objetivo + "\nAPP: " + app + "\n\nGRABADO:\n" + "\n".join(pasos) + "\n\nLIMPIO:\n" + "\n".join(limpios) + "\n")
    if not limpios:
        avisar("No quedó ningún paso útil, enséñamelo otra vez", 3.5, expresion="confundido")
        capa.enviar(cmd="plan_fin")
        return
    capa.enviar(cmd="plan", hechos=len(limpios), activo=False)
    print("Grabé", len(pasos), "pasos; me quedo con", len(limpios) + ":")
    for i, paso in enumerate(limpios, start=1):
        print("  " + str(i) + ")", paso)
    resumen = "«" + objetivo + "»: " + " → ".join(limpios) + "   ·   Ctrl+Alt+" + LETRAS["actuar"] + " guarda, Ctrl+Alt+" + LETRAS["senalar"] + " descarta"
    capa.enviar(cmd="mensaje", texto=resumen, duracion=CONFIRMAR_SEGUNDOS)
    print("Ctrl+Alt+" + LETRAS["actuar"] + " = guardar, Ctrl+Alt+" + LETRAS["senalar"] + " = descartar (si no pulsas nada en " + str(CONFIRMAR_SEGUNDOS) + " s, se guarda).")
    decision = esperar_decision(CONFIRMAR_SEGUNDOS)
    capa.enviar(cmd="limpiar")
    if decision == ID_SENALAR:
        avisar("Descartado, enséñamelo otra vez cuando quieras", 3.0)
        capa.enviar(cmd="plan_fin")
        return
    memoria.guardar_receta(app, objetivo, limpios, "demostracion", crudos=pasos)
    avisar("Aprendí «" + objetivo + "» (" + str(len(limpios)) + " pasos)", 3.5, expresion="enamorado")
    time.sleep(0.8)
    capa.enviar(cmd="plan_fin")


def modo_texto(letra, letra_actuar, actuar_ok):
    print("Modo sin voz.")
    print("  1. Escribe aquí la orden y pulsa Enter.")
    print("  2. Ve a la ventana donde quieres que lo haga.")
    print("  3. Pulsa Ctrl+Alt+" + letra + " para señalar" + (" o Ctrl+Alt+" + letra_actuar + " para actuar." if actuar_ok else "."))
    print("  Escribe 'salir' para terminar.")
    try:
        while True:
            texto = input("\nOrden: ").strip()
            if texto.lower() in ("salir", "exit", "q"):
                break
            if len(texto) < MIN_CARACTERES:
                continue
            print("Ahora ve a la ventana y pulsa el atajo...")
            capa.enviar(cmd="mensaje", texto=texto, duracion=2.5)
            ident = esperar_tecla()
            modo_actuar = ident == ID_ACTUAR
            ESTADO["pendiente"] = None
            winsound.Beep(520, 120)
            capa.enviar(cmd="estado", valor="pensando")
            print("Dijiste:", texto, "(modo acción)" if modo_actuar else "")
            procesar_texto(texto, modo_actuar)
            capa.enviar(cmd="estado", valor="idle")
            print("Listo.")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        user32.UnregisterHotKey(None, ID_SENALAR)
        user32.UnregisterHotKey(None, ID_ACTUAR)
        capa.cerrar()
        print("Hasta luego.")


def main():
    marcas.preparar_dpi()
    print("Motor de IA:", marcas.PERFIL["nombre"], "|", marcas.URL)
    cfg = voz.leer_config()
    CONFIG.update(cfg)
    letra = str(cfg.get("tecla", "J"))[:1].upper()
    letra_actuar = str(cfg.get("tecla_actuar", "K"))[:1].upper()
    LETRAS["senalar"] = letra
    LETRAS["actuar"] = letra_actuar
    if not servidor_listo():
        print("El servidor de " + marcas.PERFIL["nombre"] + " no responde.")
        print("Ejecuta " + marcas.PERFIL["iniciar"] + " y vuelve a intentarlo.")
        return
    sin_voz = "--texto" in sys.argv
    modelo = None
    idx = None
    if not sin_voz:
        idx, nombre = voz.elegir_microfono(cfg)
        print("Usando:", nombre)
        nombre_modelo = os.environ.get("WHISPER_MODELO") or cfg.get("modelo") or voz.MODELO_DEFECTO
        modelo = voz.cargar_modelo(nombre_modelo)
        if modelo is None and nombre_modelo != voz.MODELO_DEFECTO:
            modelo = voz.cargar_modelo(voz.MODELO_DEFECTO)
        if modelo is None:
            return
    if not registrar_tecla(ID_SENALAR, letra):
        print("No pude registrar Ctrl+Alt+" + letra + ": otra aplicación ya usa ese atajo.")
        print("Cambia la letra con \"tecla\" en config.json y vuelve a intentarlo.")
        return
    actuar_ok = registrar_tecla(ID_ACTUAR, letra_actuar)
    if not actuar_ok:
        print("Aviso: no pude registrar Ctrl+Alt+" + letra_actuar + "; el modo de acción queda desactivado.")
    capa.iniciar(bool(cfg.get("buddy", True)))
    if sin_voz:
        modo_texto(letra, letra_actuar, actuar_ok)
        return
    grabador = Grabador(idx)
    print("Listo.")
    print("  Ctrl+Alt+" + letra + "  = señalar (empieza a escuchar; otra vez, termina)")
    if actuar_ok:
        print("  Ctrl+Alt+" + letra_actuar + "  = actuar (hace clic y escribe por ti; Esc cancela antes de cada clic)")
    print("  Ctrl+C aquí para salir.")
    try:
        while True:
            ident = esperar_tecla()
            modo_actuar = ident == ID_ACTUAR
            pendiente = ESTADO.get("pendiente")
            ESTADO["pendiente"] = None
            if modo_actuar and pendiente and time.time() < pendiente["hasta"]:
                winsound.Beep(880, 120)
                capa.enviar(cmd="limpiar")
                capa.enviar(cmd="estado", valor="pensando")
                print("Lo hago yo:", pendiente["texto"])
                procesar_texto(pendiente["texto"], True)
                print("Listo.")
                continue
            winsound.Beep(880, 120)
            capa.enviar(cmd="estado", valor="escuchando")
            grabador.iniciar()
            print("Escuchando..." + (" (modo acción)" if modo_actuar else ""))
            esperar_tecla()
            audio = grabador.detener()
            winsound.Beep(520, 120)
            capa.enviar(cmd="estado", valor="pensando")
            procesar(modelo, audio, modo_actuar)
            print("Listo.")
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnregisterHotKey(None, ID_SENALAR)
        user32.UnregisterHotKey(None, ID_ACTUAR)
        capa.cerrar()
        print("Hasta luego.")


if __name__ == "__main__":
    main()
