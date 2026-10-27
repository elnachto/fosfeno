import ctypes
import queue
import threading
import time
from ctypes import wintypes

import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012
LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01

TIPOS = {
    "ButtonControl", "MenuItemControl", "TabItemControl", "EditControl", "CheckBoxControl", "ComboBoxControl",
    "HyperlinkControl", "ListItemControl", "TreeItemControl", "RadioButtonControl", "SplitButtonControl",
    "DocumentControl",
}
MODIFICADORES = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C, 0x14}
ESPECIALES = {0x0D: "enter", 0x09: "tab", 0x1B: "esc", 0x28: "abajo", 0x26: "arriba"}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def pulsada(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def nombre_tecla(vk):
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk).lower()
    if 0x70 <= vk <= 0x7B:
        return "f" + str(vk - 0x6F)
    return ESPECIALES.get(vk)


def corto(texto, n=60):
    t = (texto or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


class Demostracion:
    def __init__(self):
        self.pasos = []
        self.app_titulo = ""
        self.eventos = queue.Queue()
        self.hilo_ganchos = None
        self.hilo_trabajo = None
        self.id_hilo = 0
        self.parar = threading.Event()
        self.listo_ganchos = threading.Event()
        self._raton = None
        self._teclado = None

    def iniciar(self):
        self.hilo_trabajo = threading.Thread(target=self._trabajar, daemon=True)
        self.hilo_trabajo.start()
        self.hilo_ganchos = threading.Thread(target=self._ganchos, daemon=True)
        self.hilo_ganchos.start()
        self.listo_ganchos.wait(2.0)

    def detener(self):
        if self.id_hilo:
            user32.PostThreadMessageW(self.id_hilo, WM_QUIT, 0, 0)
        if self.hilo_ganchos is not None:
            self.hilo_ganchos.join(2.0)
        self.eventos.put(("fin",))
        self.parar.set()
        if self.hilo_trabajo is not None:
            self.hilo_trabajo.join(3.0)
        return list(self.pasos), self.app_titulo

    def _ganchos(self):
        self.id_hilo = kernel32.GetCurrentThreadId()

        def raton(codigo, wparam, lparam):
            if codigo == 0 and wparam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
                d = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if not d.flags & LLMHF_INJECTED:
                    self.eventos.put(("clic", d.pt.x, d.pt.y, wparam == WM_RBUTTONDOWN))
            return user32.CallNextHookEx(None, codigo, wparam, lparam)

        def teclado(codigo, wparam, lparam):
            if codigo == 0 and wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                d = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not d.flags & LLKHF_INJECTED:
                    self.eventos.put(("tecla", int(d.vkCode), pulsada(0x11), pulsada(0x12)))
            return user32.CallNextHookEx(None, codigo, wparam, lparam)

        self._raton = HOOKPROC(raton)
        self._teclado = HOOKPROC(teclado)
        modulo = kernel32.GetModuleHandleW(None)
        h1 = user32.SetWindowsHookExW(WH_MOUSE_LL, self._raton, modulo, 0)
        h2 = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._teclado, modulo, 0)
        self.listo_ganchos.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        if h1:
            user32.UnhookWindowsHookEx(h1)
        if h2:
            user32.UnhookWindowsHookEx(h2)

    def _trabajar(self):
        with auto.UIAutomationInitializerInThread():
            tipeando = False
            valor = ""
            campo = ""
            secreto = False
            while True:
                try:
                    ev = self.eventos.get(timeout=0.15)
                except queue.Empty:
                    ev = None
                if tipeando:
                    v, c, s = self._leer_campo()
                    if s:
                        secreto = True
                    if v is not None:
                        valor = v
                    if c:
                        campo = c
                if ev is None:
                    continue
                tipo = ev[0]
                if tipo == "fin":
                    if tipeando:
                        self._guardar_texto(valor, campo, secreto)
                    break
                if tipo == "clic":
                    if tipeando:
                        self._guardar_texto(valor, campo, secreto)
                        tipeando = False
                    self._registrar_clic(ev[1], ev[2], ev[3])
                    continue
                vk, ctrl, alt = ev[1], ev[2], ev[3]
                if vk in MODIFICADORES:
                    continue
                nombre = nombre_tecla(vk)
                if ctrl and alt:
                    if vk in (0x4A, 0x4B):
                        continue
                    nombre = None
                elif (ctrl or alt) and nombre:
                    combo = ("ctrl+" if ctrl else "alt+") + nombre
                    if tipeando:
                        self._guardar_texto(valor, campo, secreto)
                        tipeando = False
                    self._anotar_ventana()
                    self.pasos.append("pulsé la tecla " + combo)
                    continue
                if vk in ESPECIALES:
                    if tipeando:
                        self._guardar_texto(valor, campo, secreto)
                        tipeando = False
                    self._anotar_ventana()
                    self.pasos.append("pulsé la tecla " + ESPECIALES[vk])
                    continue
                if not tipeando:
                    tipeando = True
                    valor = ""
                    campo = ""
                    secreto = False

    def _anotar_ventana(self):
        if self.app_titulo:
            return
        try:
            self.app_titulo = auto.GetForegroundControl().Name or ""
        except Exception:
            pass

    def _leer_campo(self):
        try:
            ctrl = auto.GetFocusedControl()
            if ctrl is None:
                return None, "", False
            secreto = bool(getattr(ctrl, "IsPassword", False))
            nombre = corto(ctrl.Name, 40)
            if secreto:
                return None, nombre, True
            try:
                return ctrl.GetValuePattern().Value, nombre, False
            except Exception:
                pass
            try:
                t = ctrl.GetTextPattern().DocumentRange.GetText(300)
                if t and t.strip():
                    return t, nombre, False
            except Exception:
                pass
            try:
                t = ctrl.GetLegacyIAccessiblePattern().Value
                if t and t.strip():
                    return t, nombre, False
            except Exception:
                pass
            try:
                trozos = [h.Name for h, _ in auto.WalkControl(ctrl, includeTop=False, maxDepth=4) if h.ControlTypeName == "TextControl" and h.Name]
                if trozos:
                    return " ".join(trozos), nombre, False
            except Exception:
                pass
            return None, nombre, False
        except Exception:
            return None, "", False

    def _guardar_texto(self, valor, campo, secreto):
        self._anotar_ventana()
        donde = " en «" + campo + "»" if campo else ""
        if secreto:
            self.pasos.append("escribí una contraseña" + donde + " (no la guardo)")
        elif valor and valor.strip():
            self.pasos.append("escribí «" + corto(valor, 120) + "»" + donde)
        else:
            self.pasos.append("escribí texto" + donde)

    def _registrar_clic(self, x, y, derecho):
        try:
            ctrl = auto.ControlFromPoint(x, y)
        except Exception:
            ctrl = None
        nombre = ""
        tipo = ""
        barra = False
        titulo = ""
        actual = ctrl
        for _ in range(6):
            if actual is None:
                break
            try:
                if actual.Name and (actual.ControlTypeName in TIPOS or not nombre):
                    nombre = actual.Name
                    tipo = actual.ControlTypeName.replace("Control", "")
                    if actual.ControlTypeName in TIPOS:
                        break
                actual = actual.GetParentControl()
            except Exception:
                break
        try:
            top = ctrl.GetTopLevelControl() if ctrl is not None else None
            if top is not None:
                barra = top.ClassName in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")
                titulo = top.Name or ""
        except Exception:
            pass
        if not barra and not self.app_titulo and titulo:
            self.app_titulo = titulo
        accion = "clic derecho en" if derecho else "clic en"
        if nombre:
            texto = accion + " «" + corto(nombre) + "»" + (" (" + tipo + ")" if tipo else "")
        else:
            texto = accion + " un elemento sin nombre"
        if barra:
            texto += " en la barra de tareas"
        self.pasos.append(texto)
