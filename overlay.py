import atexit
import json
import math
import os
import sys
import threading
import time

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")

from PySide6.QtCore import QObject, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QRegion,
)
from PySide6.QtWidgets import QApplication, QWidget

try:
    import numpy as np
except Exception:
    np = None

BASE = os.path.dirname(os.path.abspath(__file__))

try:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.CreateCursor.argtypes = [wintypes.HINSTANCE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
    user32.CreateCursor.restype = ctypes.c_void_p
    user32.SetSystemCursor.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    user32.SetSystemCursor.restype = wintypes.BOOL
    user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
    user32.SystemParametersInfoW.restype = wintypes.BOOL
except Exception:
    user32 = None

IDS_CURSOR = (32512, 32513, 32514, 32515, 32516, 32642, 32643, 32644, 32645, 32646, 32648, 32649, 32650, 32651)

TEMAS = {
    "claro": {"relleno": (255, 255, 255), "tinta": (22, 24, 29), "sombra": 0.22, "accion": (124, 92, 255)},
    "oscuro": {"relleno": (22, 24, 29), "tinta": (240, 242, 246), "sombra": 0.35, "accion": (150, 124, 255)},
}
DESENFOQUE = 6.0
CONTRASTE = 18.0
INTERCEPTO = 0.5 - CONTRASTE * (5.0 / 12.0)
ALTO_PILDORA = 30.0
HUECO = 8.0
SUENO = 60.0
RADIO_REPOSO = 15.0
MAX_GOTAS = 6
MAREO_UMBRAL = 9.0
MAREO_TAU = 1.2
MAREO_MUESTRA = 12.0
MAREO_PAUSA = 0.3
ZONA_MUERTA = 6.0
RADIO_CONTROL = 12.0
ANCHO_TARJETA = 340.0


def ocultar_cursor_sistema():
    if user32 is None:
        return False
    try:
        plano_and = (ctypes.c_ubyte * 128)(*([0xFF] * 128))
        plano_xor = (ctypes.c_ubyte * 128)()
        for ident in IDS_CURSOR:
            h = user32.CreateCursor(None, 0, 0, 32, 32, plano_and, plano_xor)
            if h:
                user32.SetSystemCursor(h, ident)
        return True
    except Exception:
        return False


def restaurar_cursor_sistema():
    if user32 is None:
        return
    try:
        user32.SystemParametersInfoW(0x0057, 0, None, 0)
    except Exception:
        pass


def geometria_total():
    total = QRect()
    for pantalla in QGuiApplication.screens():
        total = total.united(pantalla.geometry())
    return total


def lim(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def rebote(t):
    if t <= 0.0:
        return 0.0
    return 1.0 - math.exp(-7.0 * t) * math.cos(11.0 * t)


def out_cubic(t):
    t = lim(t)
    return 1.0 - (1.0 - t) ** 3


def color(c, a=255):
    return QColor(int(c[0]), int(c[1]), int(c[2]), int(max(0, min(255, a))))


def fuente():
    f = QFont("Segoe UI", 10)
    f.setWeight(QFont.Weight.DemiBold)
    return f


def leer_config():
    try:
        with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class Muelle:
    def __init__(self, valor, k=380.0, c=18.0):
        self.x = float(valor)
        self.v = 0.0
        self.meta = float(valor)
        self.k = k
        self.c = c

    def paso(self, dt):
        n = max(1, int(math.ceil(dt / 0.004)))
        h = dt / n
        for _ in range(n):
            a = -self.k * (self.x - self.meta) - self.c * self.v
            self.v += a * h
            self.x += self.v * h


class Muelle2:
    def __init__(self, p, k=380.0, c=18.0):
        self.mx = Muelle(p.x(), k, c)
        self.my = Muelle(p.y(), k, c)

    def apuntar(self, p):
        self.mx.meta = p.x()
        self.my.meta = p.y()

    def paso(self, dt):
        self.mx.paso(dt)
        self.my.paso(dt)

    def pos(self):
        return QPointF(self.mx.x, self.my.x)

    def vel(self):
        return self.mx.v, self.my.v


def caja(a, r, eje):
    n = a.shape[eje]
    pads = [(0, 0), (0, 0)]
    pads[eje] = (r + 1, r)
    c = np.cumsum(np.pad(a, pads), axis=eje, dtype=np.float32)
    if eje == 0:
        return (c[2 * r + 1:2 * r + 1 + n] - c[:n]) / (2 * r + 1)
    return (c[:, 2 * r + 1:2 * r + 1 + n] - c[:, :n]) / (2 * r + 1)


def gauss(a, sigma):
    r = max(1, int(round((math.sqrt(4.0 * sigma * sigma + 1.0) - 1.0) / 2.0)))
    for _ in range(3):
        a = caja(caja(a, r, 0), r, 1)
    return a


def pintar_goo(p, zona, formas, relleno, sombra_alfa, opac=1.0):
    w, h = zona.width(), zona.height()
    if w < 2 or h < 2:
        return
    if np is None:
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(color(relleno)))
        formas(p)
        p.restore()
        return
    m = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    m.fill(0)
    q = QPainter(m)
    q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    q.translate(-zona.x(), -zona.y())
    q.setPen(Qt.PenStyle.NoPen)
    q.setBrush(QBrush(QColor(255, 255, 255)))
    formas(q)
    q.end()
    bpl = m.bytesPerLine()
    crudo = np.frombuffer(m.constBits(), np.uint8, count=bpl * h).reshape(h, bpl // 4, 4)
    a = crudo[:, :w, 3].astype(np.float32) * (1.0 / 255.0)
    al = np.clip(CONTRASTE * gauss(a, DESENFOQUE) + INTERCEPTO, 0.0, 1.0) * opac
    s = np.zeros_like(al)
    s[3:, :] = al[:-3, :]
    s = gauss(s, 4.0) * sombra_alfa
    fuera = al + s * (1.0 - al)
    arr = np.empty((h, w, 4), np.uint8)
    arr[..., 0] = (relleno[2] * al + 0.5).astype(np.uint8)
    arr[..., 1] = (relleno[1] * al + 0.5).astype(np.uint8)
    arr[..., 2] = (relleno[0] * al + 0.5).astype(np.uint8)
    arr[..., 3] = (fuera * 255.0 + 0.5).astype(np.uint8)
    img = QImage(arr.data, w, h, 4 * w, QImage.Format.Format_ARGB32_Premultiplied)
    p.drawImage(zona.topLeft(), img)


def puntos_globo(t):
    pts = []
    giro = t * 0.7
    barrido = (t * 1.6) % (2.0 * math.pi)
    inc = 0.38
    for i in range(9):
        phi = -math.pi / 2.0 + math.pi * (i + 0.5) / 9.0
        n = max(4, int(round(18 * math.cos(phi))))
        for j in range(n):
            th = 2.0 * math.pi * j / n + giro
            X = math.cos(phi) * math.sin(th)
            Y = math.sin(phi)
            Z = math.cos(phi) * math.cos(th)
            Y, Z = Y * math.cos(inc) - Z * math.sin(inc), Y * math.sin(inc) + Z * math.cos(inc)
            d = math.atan2(math.sin(th - barrido), math.cos(th - barrido))
            boost = math.exp(-d * d / 0.18) * max(0.0, Z)
            prof = (Z + 1.0) / 2.0
            pts.append((X, Y, Z, 0.35 + 0.55 * prof + 0.7 * boost, 0.2 + 0.45 * prof + 0.35 * boost))
    return pts


def puntos_onda(t):
    pts = []
    giro = t * 0.45
    inc = 0.55
    for i in range(8):
        phi = -math.pi / 2.0 + math.pi * (i + 0.5) / 8.0
        n = max(4, int(round(18 * math.cos(phi))))
        for j in range(n):
            th = 2.0 * math.pi * j / n
            cresta = math.sin(3.0 * th + t * 5.0 + i * 0.8) * 0.6 + math.sin(5.0 * th - t * 3.2 + i) * 0.4
            rad = 1.0 + 0.11 * cresta
            X = math.cos(phi) * math.sin(th + giro) * rad
            Y = math.sin(phi) * rad
            Z = math.cos(phi) * math.cos(th + giro) * rad
            Y, Z = Y * math.cos(inc) - Z * math.sin(inc), Y * math.sin(inc) + Z * math.cos(inc)
            prof = lim((Z + 1.0) / 2.0)
            pts.append((X, Y, Z, (0.35 + 0.7 * prof) * (1.0 + 0.4 * max(0.0, cresta)), 0.2 + 0.8 * prof))
    return pts


def envolvente(lt, dur):
    return lim(lt / 0.12) * lim((dur - lt) / 0.3)


def pose_expresion(tipo, lt, dur, t):
    dx = dy = rot = 0.0
    sx = sy = 1.0
    if tipo == "feliz":
        h = abs(math.sin(lt * 8.0)) * math.exp(-lt * 1.8)
        dy = -10.0 * h
        d = 0.1 * math.cos(lt * 16.0) * math.exp(-lt * 2.0)
        sx, sy = 1.0 + d, 1.0 - d
    elif tipo == "sorprendido":
        if lt < 0.28:
            dy = -13.0 * math.sin(lt / 0.28 * math.pi)
            sy = 1.0 + 0.1 * math.sin(lt / 0.28 * math.pi)
            sx = 1.0 - 0.05 * math.sin(lt / 0.28 * math.pi)
        else:
            d = 0.07 * math.cos((lt - 0.28) * 18.0) * math.exp(-(lt - 0.28) * 4.0)
            sx, sy = 1.0 + d, 1.0 - d
    elif tipo == "confundido":
        dx = math.sin(lt * 34.0) * 4.0 * math.exp(-lt * 4.0)
        rot = math.sin(lt * 3.0) * 8.0 * math.exp(-lt * 0.5)
    elif tipo == "triste":
        a = lim(lt / 0.5)
        dy = 4.0 * a
        sx, sy = 1.0 + 0.06 * a, 1.0 - 0.08 * a
        dx = math.sin(lt * 26.0) * 0.7
    elif tipo == "enamorado":
        rot = math.sin(lt * 4.0) * 6.0
        d = 0.04 * math.sin(lt * 9.0)
        sx, sy = 1.0 + d, 1.0 + d
        dy = -2.0 * abs(math.sin(lt * 4.0))
    elif tipo == "guiño":
        if 0.12 < lt < 0.7:
            h = math.sin((lt - 0.12) / 0.58 * math.pi)
            dy = -6.0 * h
            rot = 6.0 * h
    elif tipo == "concentrado":
        dx = math.sin(lt * 2.2) * 1.2
        sy = 1.0 - 0.03
    elif tipo == "mareado":
        rot = math.sin(lt * 5.0) * 11.0
        dx = math.sin(lt * 5.0 + 0.6) * 6.0
        dy = math.sin(lt * 10.0) * 1.2
        d = 0.05 * math.sin(lt * 10.0)
        sx, sy = 1.0 + d, 1.0 - d
    elif tipo == "dormido":
        sy = 1.0 + 0.045 * math.sin(t * 1.6)
        sx = 1.0 - 0.025 * math.sin(t * 1.6)
    e = envolvente(lt, dur) if tipo != "dormido" else 1.0
    return dx * e, dy * e, 1.0 + (sx - 1.0) * e, 1.0 + (sy - 1.0) * e, rot * e


def estrella(p, x, y, tam, giro, col_, alfa):
    ruta = QPainterPath()
    for k in range(8):
        ang = giro + k * math.pi / 4.0
        rad = tam if k % 2 == 0 else tam * 0.28
        pt = QPointF(x + rad * math.cos(ang), y + rad * math.sin(ang))
        if k == 0:
            ruta.moveTo(pt)
        else:
            ruta.lineTo(pt)
    ruta.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color(col_, alfa)))
    p.drawPath(ruta)


def corazon(p, x, y, s, col_, alfa=255):
    ruta = QPainterPath()
    ruta.moveTo(x, y + s * 0.9)
    ruta.cubicTo(x - s * 1.4, y - s * 0.1, x - s * 0.6, y - s * 1.0, x, y - s * 0.35)
    ruta.cubicTo(x + s * 0.6, y - s * 1.0, x + s * 1.4, y - s * 0.1, x, y + s * 0.9)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color(col_, alfa)))
    p.drawPath(ruta)


def dibujar_expresion(p, r, tipo, lt, dur, t, mira, tinta, parpadeo):
    p.setPen(Qt.PenStyle.NoPen)
    ex = r * 0.4
    ey = -r * 0.04
    rr = r * 0.2
    mx, my = mira
    grosor = max(1.8, r * 0.11)

    def circulo(lado, k=1.0, dx=0.0, dy=0.0, alto=1.0):
        pos = QPointF(lado * ex + mx * r * 0.1 + dx, ey + my * r * 0.1 + dy)
        p.setBrush(QBrush(color(tinta)))
        p.drawEllipse(pos, rr * k, max(0.6, rr * k * alto))

    def arco(lado, ini, span, dy=0.0, k=1.0):
        pen = QPen(color(tinta), grosor)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        a = rr * 1.05 * k
        p.drawArc(QRectF(lado * ex - a, ey + dy - a, 2 * a, 2 * a), int(ini * 16), int(span * 16))
        p.setPen(Qt.PenStyle.NoPen)

    def linea(x0, y0, x1, y1):
        pen = QPen(color(tinta), max(1.5, r * 0.08))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        p.setPen(Qt.PenStyle.NoPen)

    if tipo == "feliz":
        pulso = 1.0 + 0.1 * math.sin(lt * 14.0)
        arco(-1, 20, 140, k=pulso)
        arco(1, 20, 140, k=pulso)
    elif tipo == "sorprendido":
        k = 1.0 + 0.4 * lim(rebote(lt * 5.0), 0.0, 1.3)
        circulo(-1, k, dy=-r * 0.04)
        circulo(1, k, dy=-r * 0.04)
    elif tipo == "confundido":
        gx = math.sin(lt * 5.0)
        mira2 = (gx * 0.8, 0.0)
        for lado, k, dy in ((-1, 1.0, 0.0), (1, 0.72, -r * 0.08)):
            pos = QPointF(lado * ex + mira2[0] * r * 0.1, ey + dy)
            p.setBrush(QBrush(color(tinta)))
            p.drawEllipse(pos, rr * k, rr * k)
    elif tipo == "triste":
        a = lim(lt / 0.5)
        circulo(-1, 1.0, dy=r * 0.05 * a, alto=1.0 - 0.1 * a)
        circulo(1, 1.0, dy=r * 0.05 * a, alto=1.0 - 0.1 * a)
        linea(-ex - r * 0.17, -r * 0.24 + r * 0.02 * a, -ex + r * 0.15, -r * 0.36 - r * 0.04 * a)
        linea(ex + r * 0.17, -r * 0.24 + r * 0.02 * a, ex - r * 0.15, -r * 0.36 - r * 0.04 * a)
    elif tipo == "enamorado":
        k = 1.0 + 0.16 * math.sin(lt * 9.0)
        corazon(p, -ex, ey, r * 0.2 * k, (236, 72, 102))
        corazon(p, ex, ey, r * 0.2 * k, (236, 72, 102))
    elif tipo == "guiño":
        circulo(-1)
        cierre = lim(math.sin(lt / 0.7 * math.pi) * 1.6) if 0.12 < lt < 0.82 else 0.0
        if cierre > 0.85:
            arco(1, 20, 140)
        else:
            circulo(1, alto=1.0 - cierre)
    elif tipo == "concentrado":
        gx = math.sin(lt * 2.2)
        for lado in (-1, 1):
            pos = QPointF(lado * ex + gx * r * 0.09, ey + r * 0.05)
            p.setBrush(QBrush(color(tinta)))
            p.drawEllipse(pos, rr, rr * 0.55)
        linea(-ex - r * 0.18, -r * 0.3, -ex + r * 0.16, -r * 0.22)
        linea(ex + r * 0.18, -r * 0.3, ex - r * 0.16, -r * 0.22)
    elif tipo == "mareado":
        for lado in (-1, 1):
            pen = QPen(color(tinta), max(1.4, r * 0.075))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            ruta = QPainterPath()
            giro = lt * 9.0 * (1.0 if lado > 0 else -1.0)
            vueltas = 2.0
            pasos = 26
            for i in range(pasos + 1):
                f = i / pasos
                ang = giro + f * vueltas * 2.0 * math.pi
                rad = rr * 1.7 * f
                pt = QPointF(lado * ex + rad * math.cos(ang), ey + rad * math.sin(ang))
                if i == 0:
                    ruta.moveTo(pt)
                else:
                    ruta.lineTo(pt)
            p.drawPath(ruta)
        p.setPen(Qt.PenStyle.NoPen)
    elif tipo == "dormido":
        arco(-1, 200, 140, dy=-r * 0.06)
        arco(1, 200, 140, dy=-r * 0.06)
    else:
        circulo(-1, 1.0, alto=parpadeo)
        circulo(1, 1.0, alto=parpadeo)


def dibujar_extras(p, r, tipo, lt, dur, t, tinta):
    al = lim((dur - lt) / 0.3)
    if tipo == "feliz":
        for k in range(3):
            ph = lim((lt - 0.08 * k) / 0.8)
            if 0.0 < ph < 1.0:
                ang = -2.3 + k * 0.8
                d = r * (1.25 + 0.7 * ph)
                estrella(p, d * math.cos(ang), d * math.sin(ang), r * 0.2 * math.sin(math.pi * ph), ph * 1.6, tinta, 255 * al)
    elif tipo == "enamorado":
        for k in range(4):
            ph = (lt * 0.9 + k * 0.25) % 1.0
            x = r * (0.55 * math.sin(k * 2.3 + lt) + (k - 1.5) * 0.28)
            y = -r * 0.9 - ph * r * 1.5
            corazon(p, x, y, r * 0.13 * (1.0 - 0.3 * ph), (236, 72, 102), 255 * math.sin(math.pi * ph) * al)
    elif tipo == "triste":
        ph = (lt * 0.8) % 1.0
        x = r * 0.62
        y = r * 0.12 + ph * r * 0.95
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(color((110, 185, 255), 235 * (1.0 - ph * ph) * al)))
        p.drawEllipse(QPointF(x, y), r * 0.065, r * 0.095 * (0.6 + 0.6 * min(1.0, ph * 2.0)))
    elif tipo == "mareado":
        for k in range(3):
            ang = lt * 5.5 + k * 2.0 * math.pi / 3.0
            x = r * 0.95 * math.cos(ang)
            y = -r * 1.15 + r * 0.22 * math.sin(ang)
            prof = 0.65 + 0.35 * math.sin(ang)
            estrella(p, x, y, r * 0.26 * prof, lt * 2.0 + k, tinta, 255 * al * (0.55 + 0.45 * prof))
    elif tipo == "dormido":
        p.setFont(fuente())
        for k in range(2):
            ph = (t * 0.5 + k * 0.5) % 1.0
            p.setPen(color(tinta, 150 * (1.0 - ph)))
            p.drawText(QPointF(r + 2.0 + ph * 12.0, -r * 0.6 - ph * 18.0), "z")
        p.setPen(Qt.PenStyle.NoPen)


class Puente(QObject):
    comando = Signal(dict)


class Capa(QWidget):
    def __init__(self, mostrar_buddy):
        super().__init__()
        cfg = leer_config()
        self.tema = TEMAS.get(str(cfg.get("tema", "claro")).lower(), TEMAS["claro"])
        self.mostrar_buddy = mostrar_buddy
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        geo = geometria_total()
        self.origen = QPointF(geo.x(), geo.y())
        self.ancho = geo.width()
        self.alto = geo.height()
        self.cursor_oculto = False
        self.setGeometry(geo.x(), geo.y(), self.ancho, self.alto - 1)
        self.fm = QFontMetricsF(fuente())
        self.t = 0.0
        self.ultimo = time.perf_counter()
        self.cur_ancla = self.cursor()
        inicio = self.destino_cursor()
        self.cuerpo = Muelle2(inicio, 330.0, 27.0)
        self.cola = Muelle2(inicio, 150.0, 15.0)
        self.radio = Muelle(RADIO_REPOSO if mostrar_buddy else 0.0, 320.0, 17.0)
        self.cara = Muelle(1.0, 200.0, 22.0)
        self.lw = Muelle(0.0, 170.0, 11.5)
        self.lh = Muelle(0.0, 260.0, 17.0)
        self.lab = None
        self.lab_prev = None
        self.lab_cambio = -10.0
        self.lado = 1.0
        self.modo_orbe = "onda"
        self.estado = "idle"
        self.senal = None
        self.mensaje = None
        self.cuenta = None
        self.oculto = False
        self.expr = None
        self.plan = None
        self.ultimo_mov = 0.0
        self.cur_prev = self.cursor()
        self.rumbo_prev = None
        self.t_muestra = 0.0
        self.giro_acum = 0.0
        acc = cfg.get("color_accion")
        if isinstance(acc, list) and len(acc) == 3:
            self.accion = tuple(int(v) for v in acc)
        else:
            self.accion = self.tema["accion"]
        self.ctl = Muelle(0.0, 240.0, 20.0)
        self.ctl_modo = "mover"
        self.huella = Muelle2(self.cursor(), 1400.0, 56.0)
        self.huella_cola = Muelle2(self.cursor(), 170.0, 22.0)
        self.toques = []
        self.zona_previa = QRegion()
        self.reloj = QTimer(self)
        self.reloj.setTimerType(Qt.TimerType.PreciseTimer)
        self.reloj.setInterval(16)
        self.reloj.timeout.connect(self.tick)
        self.reloj.start()

    def cursor(self):
        c = QCursor.pos()
        return QPointF(c.x() - self.origen.x(), c.y() - self.origen.y())

    def restaurar(self):
        if self.cursor_oculto:
            restaurar_cursor_sistema()
            self.cursor_oculto = False

    def destino_cursor(self):
        c = self.cur_ancla
        return QPointF(c.x() + 24.0, c.y() + 26.0)

    def clic_a_traves(self):
        if user32 is None:
            return
        hwnd = int(self.winId())
        estilo = user32.GetWindowLongW(hwnd, -20)
        user32.SetWindowLongW(hwnd, -20, estilo | 0x00000020 | 0x00080000 | 0x08000000 | 0x00000080)

    def comando(self, c):
        cmd = c.get("cmd")
        self.ultimo_mov = self.t
        if cmd == "estado":
            self.estado = c.get("valor", "idle")
            if self.estado == "escuchando":
                self.senal = None
                self.mensaje = None
                self.cuenta = None
        elif cmd == "expresion":
            v = str(c.get("valor", "normal"))
            self.expr = None if v == "normal" else {"valor": v, "t0": self.t, "dur": float(c.get("duracion", 2.0))}
        elif cmd == "plan":
            hechos = max(0, int(c.get("hechos", 0)))
            activo = bool(c.get("activo", True))
            if self.plan is None or self.plan.get("fin") is not None:
                self.plan = {"hechos": 0, "activo": False, "nacio": {}, "fin": None}
            self.plan["hechos"] = hechos
            self.plan["activo"] = activo
            total = hechos + (1 if activo else 0)
            for i in range(total):
                self.plan["nacio"].setdefault(i, self.t)
        elif cmd == "plan_fin":
            if self.plan is not None and self.plan.get("fin") is None:
                self.plan["fin"] = self.t
                self.plan["activo"] = False
        elif cmd == "tema":
            self.tema = TEMAS.get(str(c.get("valor", "claro")).lower(), self.tema)
        elif cmd == "control":
            activo = bool(c.get("activo", True))
            self.ctl.meta = 1.0 if activo else 0.0
            self.ctl_modo = str(c.get("modo", "mover"))
            quiere = activo and bool(c.get("ocultar", False))
            if quiere and not self.cursor_oculto:
                self.cursor_oculto = ocultar_cursor_sistema()
            elif not quiere and self.cursor_oculto:
                self.restaurar()
        elif cmd == "toque":
            self.toques.append({"p": self.cursor(), "t0": self.t})
        elif cmd == "senalar":
            self.senalar(c.get("rect", [0, 0, 10, 10]), str(c.get("texto", "")), float(c.get("duracion", 5)))
        elif cmd == "mensaje":
            self.mensaje = {"texto": str(c.get("texto", "")), "t0": self.t, "dur": float(c.get("duracion", 3.5))}
        elif cmd == "cuenta":
            self.cuenta = {"t0": self.t, "dur": float(c.get("segundos", 1.2))}
        elif cmd == "limpiar":
            self.senal = None
            self.mensaje = None
            self.cuenta = None
        elif cmd == "ocultar":
            self.oculto = True
            self.repaint()
        elif cmd == "mostrar_capa":
            self.oculto = False
            self.update()
        elif cmd == "salir":
            self.restaurar()
            QApplication.quit()

    def senalar(self, rect, texto, duracion):
        x0, y0, x1, y1 = rect
        x0, x1 = x0 - self.origen.x(), x1 - self.origen.x()
        y0, y1 = y0 - self.origen.y(), y1 - self.origen.y()
        r = QRectF(x0, y0, max(1, x1 - x0), max(1, y1 - y0))
        destino = QPointF(lim(x1 + 12.0, 24.0, self.ancho - 24.0), lim(y1 + 12.0, 24.0, self.alto - 24.0))
        self.senal = {"rect": r, "texto": texto, "t0": self.t, "dur": duracion, "destino": destino}
        self.estado = "idle"

    def medir(self, texto):
        ancho = self.fm.horizontalAdvance(texto)
        if ancho <= ANCHO_TARJETA:
            return math.ceil(ancho) + 30.0, ALTO_PILDORA
        caja = self.fm.boundingRect(QRectF(0, 0, ANCHO_TARJETA, 4000), int(Qt.TextFlag.TextWordWrap.value), texto)
        return math.ceil(caja.width()) + 32.0, max(ALTO_PILDORA, math.ceil(caja.height()) + 20.0)

    def etiqueta(self):
        if self.cuenta is not None:
            if self.senal is not None:
                return self.senal["texto"] + "  ·  Esc"
            return "Esc cancela"
        if self.mensaje is not None:
            return self.mensaje["texto"]
        if self.senal is not None and self.t - self.senal["t0"] > 0.22:
            return self.senal["texto"]
        if self.estado == "escuchando":
            return "Escuchando…"
        if self.estado == "pensando":
            return "Pensando…"
        if self.estado == "observando":
            return "Te estoy mirando  ·  Ctrl+Alt+J termina"
        return None

    def avanzar(self, dt):
        self.t += dt
        s = self.senal
        if s is not None and self.t > s["t0"] + s["dur"] + 0.35:
            self.senal = None
        if self.mensaje is not None and self.t > self.mensaje["t0"] + self.mensaje["dur"]:
            self.mensaje = None
        if self.cuenta is not None and self.t > self.cuenta["t0"] + self.cuenta["dur"]:
            self.cuenta = None
        if self.expr is not None and self.t > self.expr["t0"] + self.expr["dur"]:
            self.expr = None
        if self.plan is not None and self.plan.get("fin") is not None and self.t > self.plan["fin"] + 0.6:
            self.plan = None
        cur = self.cursor()
        if math.hypot(cur.x() - self.cur_ancla.x(), cur.y() - self.cur_ancla.y()) > ZONA_MUERTA:
            self.cur_ancla = cur
            self.ultimo_mov = self.t
        ddx = cur.x() - self.cur_prev.x()
        ddy = cur.y() - self.cur_prev.y()
        self.giro_acum *= math.exp(-dt / MAREO_TAU)
        if math.hypot(ddx, ddy) >= MAREO_MUESTRA:
            self.ultimo_mov = self.t
            rumbo = math.atan2(ddy, ddx)
            if self.rumbo_prev is not None and self.t - self.t_muestra < MAREO_PAUSA:
                d = rumbo - self.rumbo_prev
                while d > math.pi:
                    d -= 2.0 * math.pi
                while d < -math.pi:
                    d += 2.0 * math.pi
                self.giro_acum += abs(d)
            self.rumbo_prev = rumbo
            self.t_muestra = self.t
            self.cur_prev = cur
        if self.giro_acum > MAREO_UMBRAL and self.estado == "idle" and self.senal is None and self.cuenta is None and self.ctl.meta == 0.0:
            if self.expr is None or self.expr["valor"] != "mareado":
                if self.expr is None:
                    self.expr = {"valor": "mareado", "t0": self.t, "dur": 3.0}
            else:
                self.expr["dur"] = (self.t - self.expr["t0"]) + 1.4
        self.toques = [q for q in self.toques if self.t - q["t0"] < 0.5]
        if self.ctl.meta > 0.0 or self.ctl.x > 0.02:
            self.huella.apuntar(cur)
            self.huella.paso(dt)
            self.huella_cola.apuntar(self.huella.pos())
            self.huella_cola.paso(dt)
        else:
            for m in (self.huella.mx, self.huella_cola.mx):
                m.x, m.v, m.meta = cur.x(), 0.0, cur.x()
            for m in (self.huella.my, self.huella_cola.my):
                m.x, m.v, m.meta = cur.y(), 0.0, cur.y()
        destino = self.senal["destino"] if self.senal is not None else self.destino_cursor()
        self.cuerpo.apuntar(destino)
        self.cuerpo.paso(dt)
        self.cola.apuntar(self.cuerpo.pos())
        self.cola.paso(dt)
        ocupado = self.estado in ("escuchando", "pensando")
        if ocupado:
            self.radio.meta = 17.0
            self.modo_orbe = "onda" if self.estado == "escuchando" else "globo"
        elif self.estado == "observando":
            self.radio.meta = RADIO_REPOSO
        elif self.dormido():
            self.radio.meta = RADIO_REPOSO - 1.0
        elif self.senal is not None or self.mensaje is not None or self.cuenta is not None or self.mostrar_buddy or self.expr is not None or self.plan is not None:
            self.radio.meta = RADIO_REPOSO
        else:
            self.radio.meta = 0.0
        self.cara.meta = 0.0 if ocupado else 1.0
        texto = self.etiqueta()
        if texto is not None:
            w, alto_lab = self.medir(texto)
            if self.lab is None or self.lw.x < 2.0 or texto != self.lab:
                pos = self.cuerpo.mx.meta
                self.lado = 1.0 if pos + 40.0 + w < self.ancho - 8.0 else -1.0
            if texto != self.lab:
                self.lab_prev = self.lab
                self.lab_cambio = self.t
                self.lab = texto
            self.lw.meta = w
            self.lh.meta = alto_lab
        else:
            self.lw.meta = 0.0
            self.lh.meta = 0.0
            if self.lw.x < 1.0 and self.lh.x < 1.0:
                self.lab = None
                self.lab_prev = None
        for m in (self.radio, self.cara, self.lw, self.lh, self.ctl):
            m.paso(dt)

    def tick(self):
        ahora = time.perf_counter()
        dt = max(0.0, min(0.05, ahora - self.ultimo))
        self.ultimo = ahora
        self.avanzar(dt)
        zona = QRegion(self.zona_goo().adjusted(-4, -4, 4, 4))
        zc = self.zona_control()
        if zc is not None:
            zona = zona.united(QRegion(zc))
        if self.senal is not None:
            zona = zona.united(QRegion(self.senal["rect"].adjusted(-70, -70, 70, 70).toAlignedRect()))
        if self.oculto:
            self.zona_previa = zona
            return
        self.update(zona.united(self.zona_previa))
        self.zona_previa = zona

    def dormido(self):
        if self.estado != "idle" or self.senal is not None or self.mensaje is not None or self.cuenta is not None:
            return False
        if self.expr is not None or self.plan is not None:
            return False
        return self.t - self.ultimo_mov > SUENO

    def expresion(self):
        if self.estado in ("escuchando", "pensando"):
            return "normal"
        if self.expr is not None:
            return self.expr["valor"]
        if self.dormido():
            return "dormido"
        return "normal"

    def pose(self):
        tipo = self.expresion()
        if tipo == "normal":
            return 0.0, 0.0, 1.0, 1.0, 0.0
        if self.expr is not None and tipo == self.expr["valor"]:
            return pose_expresion(tipo, self.t - self.expr["t0"], self.expr["dur"], self.t)
        return pose_expresion(tipo, self.t, 1e9, self.t)

    def centro(self):
        c = self.cuerpo.pos()
        dx, dy = self.pose()[:2]
        return QPointF(c.x() + dx, c.y() + dy)

    def radio_visible(self):
        r = max(0.0, self.radio.x)
        if self.estado == "escuchando":
            r += 1.0 * math.sin(self.t * 7.0)
        elif self.dormido():
            r += 0.8 * math.sin(self.t * 1.6)
        return r

    def gotas_plan(self):
        pl = self.plan
        if pl is None:
            return []
        total = pl["hechos"] + (1 if pl["activo"] else 0)
        if total <= 0:
            return []
        inicio = max(0, total - MAX_GOTAS)
        vis = list(range(inicio, total))
        c = self.centro()
        r = self.radio_visible()
        fin = 1.0 if pl.get("fin") is None else lim(1.0 - (self.t - pl["fin"]) / 0.5)
        sep = 21.0
        x0 = c.x() - (len(vis) - 1) * sep / 2.0
        y = c.y() + r + 11.0 * fin
        res = []
        for k, i in enumerate(vis):
            e = lim(rebote(self.t - pl["nacio"].get(i, self.t)), 0.0, 1.3) * fin
            px = c.x() + (x0 + k * sep - c.x()) * min(1.0, e)
            res.append((QPointF(px, y), 8.0 * e, i < pl["hechos"], i))
        return res

    def pildora_rect(self):
        h = max(0.0, self.lh.x)
        if h < 0.5:
            return None
        w = max(min(h, ALTO_PILDORA), self.lw.x)
        c = self.centro()
        r = max(0.0, self.radio.x)
        e = lim(h / ALTO_PILDORA, 0.0, 1.2)
        borde = r * 0.3 + (r * 0.7 + HUECO) * min(e, 1.0)
        cx = c.x() + self.lado * (borde + w / 2.0)
        if h <= ALTO_PILDORA * 1.2:
            return QRectF(cx - w / 2.0, c.y() - h / 2.0, w, h)
        y = c.y() - ALTO_PILDORA / 2.0
        if y + h > self.alto - 10.0:
            y = max(10.0, self.alto - 10.0 - h)
        return QRectF(cx - w / 2.0, y, w, h)

    def gotas(self):
        if self.estado != "pensando":
            return []
        c = self.centro()
        r = max(0.0, self.radio.x)
        g = []
        for k in range(3):
            ang = self.t * 2.6 + k * 2.0 * math.pi / 3.0
            d = r + 4.0 + 5.0 * (0.5 + 0.5 * math.sin(self.t * 3.1 + k * 1.7))
            g.append((QPointF(c.x() + d * math.cos(ang), c.y() + d * math.sin(ang)), 3.4))
        return g

    def zona_goo(self):
        c = self.cuerpo.pos()
        r = max(0.0, self.radio.x) * 1.5 + 12.0
        caja = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        cl = self.cola.pos()
        caja = caja.united(QRectF(cl.x() - r, cl.y() - r, 2 * r, 2 * r))
        pr = self.pildora_rect()
        if pr is not None:
            caja = caja.united(pr)
        if self.plan is not None:
            caja = caja.united(QRectF(c.x() - 80.0, c.y(), 160.0, r + 34.0))
        caja = caja.united(QRectF(c.x() - r, c.y() - r - 30.0, 2 * r + 24.0, 30.0))
        if self.expr is not None:
            caja = caja.united(QRectF(c.x() - r * 2.4, c.y() - r * 3.0, r * 4.8, r * 4.8))
        pad = DESENFOQUE * 3.0 + 12.0
        return caja.adjusted(-pad, -pad, pad, pad).toAlignedRect().intersected(QRect(0, 0, self.ancho, self.alto))

    def zona_control(self):
        if self.ctl.x < 0.02 and self.ctl.meta == 0.0 and not self.toques:
            return None
        r = RADIO_CONTROL * 1.4 + 10.0
        h = self.huella.pos()
        cl = self.huella_cola.pos()
        caja = QRectF(h.x() - r, h.y() - r, 2 * r, 2 * r).united(QRectF(cl.x() - r, cl.y() - r, 2 * r, 2 * r))
        for q in self.toques:
            caja = caja.united(QRectF(q["p"].x() - 46.0, q["p"].y() - 46.0, 92.0, 92.0))
        pad = DESENFOQUE * 3.0 + 12.0
        return caja.adjusted(-pad, -pad, pad, pad).toAlignedRect().intersected(QRect(0, 0, self.ancho, self.alto))

    def formas_control(self, q):
        e = lim(self.ctl.x, 0.0, 1.25)
        if e < 0.02:
            return
        escribiendo = self.ctl_modo == "escribir"
        pensando = self.ctl_modo == "pensar"
        if escribiendo:
            pulso = 0.09 * math.sin(self.t * 16.0)
        elif pensando:
            pulso = 0.12 * math.sin(self.t * 3.2)
        else:
            pulso = 0.05 * math.sin(self.t * 6.0)
        r = RADIO_CONTROL * e * (1.0 + pulso)
        h = self.huella.pos()
        vx, vy = self.huella.vel()
        v = math.hypot(vx, vy)
        est = 1.0 + min(0.4, 0.2 * v / 600.0)
        q.save()
        q.translate(h)
        if v > 1.0:
            ang = math.degrees(math.atan2(vy, vx))
            q.rotate(ang)
            q.scale(est, 1.0 / est)
            q.rotate(-ang)
        q.drawEllipse(QPointF(0, 0), r, r)
        q.restore()
        q.drawEllipse(self.huella_cola.pos(), r * 0.7, r * 0.7)
        vel = 3.0 if escribiendo else (2.4 if pensando else 5.0)
        for k in range(3):
            ang = self.t * vel + k * 2.0 * math.pi / 3.0
            d = r + 3.5 + 2.5 * math.sin(self.t * 3.3 + k * 1.9)
            q.drawEllipse(QPointF(h.x() + d * math.cos(ang), h.y() + d * math.sin(ang)), 3.0 * e, 3.0 * e)

    def pintar_toques(self, p):
        for q in self.toques:
            a = lim((self.t - q["t0"]) / 0.45)
            if a >= 1.0:
                continue
            radio = 8.0 + 32.0 * out_cubic(a)
            pen = QPen(color(self.accion, 210 * (1.0 - a)), 2.2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(q["p"], radio, radio)
        p.setPen(Qt.PenStyle.NoPen)

    def burbuja_expr(self):
        if self.expr is None or self.expr["valor"] not in ("confundido", "sorprendido"):
            return None
        lt = self.t - self.expr["t0"]
        e = lim(rebote(lt - 0.1), 0.0, 1.25) * lim((self.expr["dur"] - lt) / 0.25)
        if e <= 0.02:
            return None
        r = self.radio_visible()
        c = self.centro()
        return QPointF(c.x() + r * 0.95, c.y() - r * 1.2 - 2.0 * math.sin(lt * 5.0)), 8.0 * e, e

    def formas(self, q):
        c = self.centro()
        r = self.radio_visible()
        _, _, sx, sy, rot = self.pose()
        if r > 0.5:
            vx, vy = self.cuerpo.vel()
            v = math.hypot(vx, vy)
            est = 1.0 + min(0.35, 0.18 * v / 500.0)
            q.save()
            q.translate(c)
            if v > 1.0:
                ang = math.degrees(math.atan2(vy, vx))
                q.rotate(ang)
                q.scale(est, 1.0 / est)
                q.rotate(-ang)
            q.rotate(rot)
            q.scale(sx, sy)
            q.drawEllipse(QPointF(0, 0), r, r)
            q.restore()
            cl = self.cola.pos()
            q.drawEllipse(cl, r * 0.62, r * 0.62)
        for p, gr in self.gotas():
            q.drawEllipse(p, gr, gr)
        for p, gr, _, _ in self.gotas_plan():
            if gr > 0.3:
                q.drawEllipse(p, gr, gr)
        b = self.burbuja_expr()
        if b is not None and r > 3.0:
            q.drawEllipse(b[0], b[1], b[1])
        pr = self.pildora_rect()
        if pr is not None:
            rad = min(pr.height() / 2.0, ALTO_PILDORA / 2.0)
            q.drawRoundedRect(pr, rad, rad)

    def paintEvent(self, evento):
        if self.oculto:
            return
        p = QPainter(self)
        self.pintar_todo(p)
        p.end()

    def pintar_todo(self, p):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if self.senal is not None:
            self.pintar_resaltado(p)
        zc = self.zona_control()
        if zc is not None and self.ctl.x > 0.02:
            pintar_goo(p, zc, self.formas_control, self.accion, 0.2, 0.9)
        self.pintar_toques(p)
        zona = self.zona_goo()
        if self.radio.x > 0.5 or self.pildora_rect() is not None:
            pintar_goo(p, zona, self.formas, self.tema["relleno"], self.tema["sombra"])
            self.pintar_cara(p)
            self.pintar_texto(p)

    def pintar_resaltado(self, p):
        s = self.senal
        ta = self.t - s["t0"] - 0.15
        if ta < 0:
            return
        alfa = out_cubic(ta / 0.25) * (1.0 - lim((ta - s["dur"]) / 0.3))
        if alfa <= 0.0:
            return
        tinta = self.tema["tinta"]
        rr = s["rect"].adjusted(-5, -5, 5, 5)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(color((255, 255, 255), 200 * alfa), 4.0))
        p.drawRoundedRect(rr, 9, 9)
        p.setPen(QPen(color((22, 24, 29), 235 * alfa), 1.6))
        p.drawRoundedRect(rr, 9, 9)
        if ta < 1.2:
            f = out_cubic(ta / 1.2)
            radio = 8.0 + 46.0 * f
            p.setPen(QPen(color(tinta, 150 * (1.0 - f) * alfa), 1.4))
            p.drawEllipse(s["rect"].center(), radio, radio)

    def pintar_cara(self, p):
        r = self.radio_visible()
        if r < 3.0:
            return
        c = self.centro()
        tinta = self.tema["tinta"]
        ojos = lim(self.cara.x)
        tipo = self.expresion()
        _, _, sx, sy, rot = self.pose()
        lt = (self.t - self.expr["t0"]) if (self.expr is not None and tipo == self.expr["valor"]) else self.t
        dur = self.expr["dur"] if (self.expr is not None and tipo == self.expr["valor"]) else 1e9
        if ojos > 0.02:
            objetivo = self.senal["rect"].center() if self.senal is not None else self.cursor()
            dx = objetivo.x() - c.x()
            dy = objetivo.y() - c.y()
            n = math.hypot(dx, dy)
            mx, my = (dx / n, dy / n) if n > 0.001 else (0.0, 0.0)
            mx += 0.25 * math.sin(self.t * 0.7) * (1.0 if n < 60.0 else 0.3)
            ciclo = self.t % 5.3
            parpadeo = 0.12 if (self.t % 3.7) < 0.12 or 0.25 < ciclo - 5.0 < 0.37 else 1.0
            p.save()
            p.translate(c)
            p.rotate(rot)
            p.scale(sx, sy)
            p.setOpacity(ojos)
            dibujar_expresion(p, r, tipo, lt, dur, self.t, (mx, my), tinta, parpadeo)
            p.restore()
            p.save()
            p.translate(c)
            p.setOpacity(ojos)
            dibujar_extras(p, r, tipo, lt, dur, self.t, tinta)
            b = self.burbuja_expr()
            if b is not None:
                bp, br, be = b
                p.setFont(fuente())
                p.setPen(color(tinta, 255 * lim((be - 0.6) * 3.0)))
                p.drawText(QRectF(bp.x() - c.x() - 7.0, bp.y() - c.y() - 8.0, 14.0, 16.0), int(Qt.AlignmentFlag.AlignCenter.value), "?" if tipo == "confundido" else "!")
            p.restore()
        orbe = 1.0 - ojos
        if orbe > 0.02:
            pts = puntos_onda(self.t) if self.modo_orbe == "onda" else puntos_globo(self.t)
            pts.sort(key=lambda d: d[2])
            rho = r * 0.66
            esc = r / 17.0
            p.setPen(Qt.PenStyle.NoPen)
            for X, Y, Z, rd, a in pts:
                p.setBrush(QBrush(color(tinta, 255 * a * orbe)))
                p.drawEllipse(QPointF(c.x() + X * rho, c.y() + Y * rho), rd * esc, rd * esc)
        p.setPen(Qt.PenStyle.NoPen)
        for g, gr, hecho, i in self.gotas_plan():
            if gr < 2.0:
                continue
            if hecho:
                p.setBrush(QBrush(color(tinta, 230)))
                p.drawEllipse(g, gr * 0.42, gr * 0.42)
            else:
                pulso = 0.5 + 0.5 * math.sin(self.t * 6.0)
                p.setPen(QPen(color(tinta, 120 + 100 * pulso), 1.3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(g, gr * (0.42 + 0.12 * pulso), gr * (0.42 + 0.12 * pulso))
        p.setPen(Qt.PenStyle.NoPen)

    def pintar_texto(self, p):
        pr = self.pildora_rect()
        if pr is None or self.lab is None:
            return
        meta = max(1.0, self.lw.meta)
        base = lim((self.lw.x - 0.75 * meta) / (0.25 * meta)) * lim((self.lh.x - 18.0) / 10.0)
        if base <= 0.0:
            return
        tinta = self.tema["tinta"]
        cambio = lim((self.t - self.lab_cambio) / 0.18)
        p.save()
        p.setClipRect(pr.adjusted(4, 0, -4, 0))
        p.setFont(fuente())
        asc = self.fm.ascent()
        desc = self.fm.descent()

        def dibujar(texto, rect, dy=0.0):
            ancho_t = self.fm.horizontalAdvance(texto)
            if ancho_t <= ANCHO_TARJETA:
                x = round(rect.center().x() - ancho_t / 2.0)
                y = round(rect.center().y() + (asc - desc) / 2.0 + dy)
                p.drawText(QPointF(x, y), texto)
            else:
                banderas = int(Qt.AlignmentFlag.AlignLeft.value) | int(Qt.AlignmentFlag.AlignTop.value) | int(Qt.TextFlag.TextWordWrap.value)
                caja_t = QRectF(round(rect.left()) + 16, round(rect.top() + dy) + 10, round(rect.width()) - 32, round(rect.height()) - 18)
                p.drawText(caja_t, banderas, texto)

        if self.lab_prev is not None and cambio < 1.0:
            p.setPen(color(tinta, 255 * base * (1.0 - cambio)))
            dibujar(self.lab_prev, pr)
        p.setPen(color(tinta, 255 * base * cambio))
        dibujar(self.lab, pr, 3.0 * (1.0 - out_cubic(cambio)))
        p.restore()
        if self.cuenta is not None:
            pr_c = lim((self.t - self.cuenta["t0"]) / max(0.1, self.cuenta["dur"]))
            x0 = pr.left() + 14.0
            x1 = pr.right() - 14.0
            pen = QPen(color(tinta, 90 * base), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            y = pr.bottom() - 3.0
            p.drawLine(QPointF(x0, y), QPointF(x0 + (x1 - x0) * (1.0 - pr_c), y))


def leer_stdin(puente):
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            puente.comando.emit(json.loads(linea))
        except Exception:
            continue
    puente.comando.emit({"cmd": "salir"})


def main():
    app = QApplication(sys.argv)
    mostrar_buddy = os.environ.get("JARVIS_BUDDY", "1") != "0"
    capa = Capa(mostrar_buddy)
    app.aboutToQuit.connect(capa.restaurar)
    atexit.register(capa.restaurar)
    puente = Puente()
    puente.comando.connect(capa.comando)
    hilo = threading.Thread(target=leer_stdin, args=(puente,), daemon=True)
    hilo.start()
    capa.show()
    capa.clic_a_traves()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
