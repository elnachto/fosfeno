"""Inspección de ventanas hijas Win32, de solo lectura y sin dependencias extra."""
import ctypes
from ctypes import wintypes


def inspeccionar(hwnd, limite=250):
    if not hwnd:
        raise ValueError('Falta la ventana objetivo')
    u = ctypes.WinDLL('user32', use_last_error=True)
    u.IsWindow.argtypes = [wintypes.HWND]
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsWindowEnabled.argtypes = [wintypes.HWND]
    if not u.IsWindow(hwnd):
        raise ValueError('La ventana objetivo ya no existe')
    resultados = []
    callback_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def agregar(hijo, _):
        if len(resultados) >= limite:
            return False
        clase, nombre, rect = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(512), wintypes.RECT()
        u.GetClassNameW(hijo, clase, len(clase))
        if not any(k in clase.value.lower() for k in ('edit', 'password')):
            u.GetWindowTextW(hijo, nombre, len(nombre))
        u.GetWindowRect(hijo, ctypes.byref(rect))
        resultados.append({'hwnd': int(hijo), 'clase': clase.value, 'nombre': nombre.value,
                           'rect': [rect.left, rect.top, rect.right, rect.bottom],
                           'visible': bool(u.IsWindowVisible(hijo)), 'habilitado': bool(u.IsWindowEnabled(hijo))})
        return True
    callback = callback_t(agregar)
    u.EnumChildWindows.argtypes = [wintypes.HWND, callback_t, wintypes.LPARAM]
    u.EnumChildWindows(hwnd, callback, 0)
    return {'hwnd': hwnd, 'hijos': resultados, 'limite_alcanzado': len(resultados) >= limite,
            'metodo': 'EnumChildWindows; solo lectura; contenido Edit omitido'}
