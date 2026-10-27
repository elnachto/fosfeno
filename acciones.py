import ctypes
import math
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
TECLAS = {
    "enter": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "borrar": 0x08,
    "abajo": 0x28,
    "arriba": 0x26,
    "izquierda": 0x25,
    "derecha": 0x27,
    "espacio": 0x20,
    "suprimir": 0x2E,
    "inicio": 0x24,
    "fin": 0x23,
    "repag": 0x21,
    "avpag": 0x22,
}
SINONIMOS = {
    "intro": "enter",
    "return": "enter",
    "escape": "esc",
    "backspace": "borrar",
    "retroceso": "borrar",
    "down": "abajo",
    "up": "arriba",
    "left": "izquierda",
    "right": "derecha",
    "space": "espacio",
    "delete": "suprimir",
    "supr": "suprimir",
    "del": "suprimir",
    "home": "inicio",
    "end": "fin",
    "pageup": "repag",
    "pagedown": "avpag",
    "control": "ctrl",
    "mayus": "shift",
    "mayús": "shift",
    "windows": "win",
}
MODIFICADORES = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}
ORDEN_MODS = ["ctrl", "alt", "shift", "win"]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _ENTRADA(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _ENTRADA)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def enviar(vk, escaner, banderas):
    evento = (INPUT * 1)()
    evento[0].type = 1
    evento[0].ki = KEYBDINPUT(vk, escaner, banderas, 0, 0)
    user32.SendInput(1, evento, ctypes.sizeof(INPUT))


def posicion():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def mover_suave(x, y):
    x0, y0 = posicion()
    dist = math.hypot(x - x0, y - y0)
    dur = min(0.75, 0.22 + dist / 2600.0)
    pasos = max(8, int(dur / 0.008))
    for i in range(1, pasos + 1):
        if esc_presionado():
            return False
        f = i / pasos
        e = f * f * (3.0 - 2.0 * f)
        user32.SetCursorPos(int(x0 + (x - x0) * e), int(y0 + (y - y0) * e))
        time.sleep(dur / pasos)
    return True


def clic(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.08)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def vk_de(nombre):
    if nombre in TECLAS:
        return TECLAS[nombre]
    if len(nombre) == 1 and nombre.isascii() and nombre.isalnum():
        return ord(nombre.upper())
    if nombre.startswith("f") and nombre[1:].isdigit() and 1 <= int(nombre[1:]) <= 12:
        return 0x6F + int(nombre[1:])
    return None


def normalizar_tecla(texto):
    t = (texto or "").lower().strip().strip("<>[]()'\"`«».").strip()
    t = t.replace(" ", "")
    if not t:
        return None
    partes = [SINONIMOS.get(p, p) for p in t.split("+") if p]
    if not partes:
        return None
    principal = partes[-1]
    mods = partes[:-1]
    if any(m not in MODIFICADORES for m in mods):
        return None
    if vk_de(principal) is None:
        return None
    mods = [m for m in ORDEN_MODS if m in mods]
    return "+".join(mods + [principal])


def tecla(nombre):
    canon = normalizar_tecla(nombre)
    if canon is None:
        return False
    partes = canon.split("+")
    mods = [MODIFICADORES[m] for m in partes[:-1]]
    vk = vk_de(partes[-1])
    for m in mods:
        enviar(m, 0, 0)
    enviar(vk, 0, 0)
    enviar(vk, 0, KEYEVENTF_KEYUP)
    for m in reversed(mods):
        enviar(m, 0, KEYEVENTF_KEYUP)
    return True


def escribir(texto):
    for caracter in texto:
        if caracter == "\n":
            tecla("enter")
            continue
        datos = caracter.encode("utf-16-le")
        for i in range(0, len(datos), 2):
            unidad = int.from_bytes(datos[i:i + 2], "little")
            enviar(0, unidad, KEYEVENTF_UNICODE)
            enviar(0, unidad, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
        time.sleep(0.01)


def esc_presionado():
    return bool(user32.GetAsyncKeyState(0x1B) & 0x8000)
