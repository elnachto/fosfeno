import json
import os
import re
import time
import unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
CONOCIMIENTO = os.path.join(BASE, "conocimiento")
RECETAS = os.path.join(CONOCIMIENTO, "recetas.jsonl")
NAVEGADORES = ("google chrome", "microsoft edge", "mozilla firefox", "firefox", "brave", "opera", "chromium")
VACIAS = {
    "como", "para", "que", "con", "una", "uno", "unos", "unas", "los", "las", "del", "por", "porfa", "favor",
    "puedes", "podrias", "quiero", "quisiera", "esta", "este", "esto", "aqui", "aca", "ahi", "hay", "mas",
    "me", "mi", "tu", "su", "sus", "lo", "la", "el", "de", "en", "y", "a", "al", "se", "le", "les", "hazlo",
    "dale", "ahora", "luego", "despues", "bien", "muy", "solo", "nueva", "nuevo",
}
SECCIONES = ("Correcciones", "Mapa")


def normalizar(texto):
    return "".join(unicodedata.normalize("NFD", c)[0] for c in (texto or "").lower())


def palabras(texto):
    return {p for p in re.findall(r"[a-z0-9]+", normalizar(texto)) if len(p) >= 3 and p not in VACIAS}


def app_de(titulo):
    t = re.sub(r"^\(\d+\)\s*", "", (titulo or "").strip())
    partes = [p.strip() for p in t.split(" - ") if p.strip()]
    if not partes:
        return ""
    ultima = partes[-1].lower()
    if len(partes) > 1 and any(ultima.startswith(n) for n in NAVEGADORES):
        return partes[0].lower()
    return ultima


def _slug(app):
    s = re.sub(r"[^a-z0-9]+", "-", normalizar(app)).strip("-")
    return s[:40] or "app"


def _leer_archivo(ruta):
    with open(ruta, "r", encoding="utf-8") as f:
        texto = f.read()
    lineas = texto.split("\n")
    primera = lineas[0].strip() if lineas else ""
    if not primera.upper().startswith("CLAVES:"):
        return None
    claves = [c.strip().lower() for c in primera[7:].split(",") if c.strip()]
    secciones = {"": []}
    actual = ""
    for linea in lineas[1:]:
        if linea.startswith("## "):
            nombre = linea[3:].strip()
            actual = next((s for s in SECCIONES if nombre.startswith(s)), nombre)
            secciones.setdefault(actual, [])
            continue
        secciones.setdefault(actual, []).append(linea)
    return claves, secciones


def _escribir_archivo(ruta, claves, secciones):
    partes = ["CLAVES: " + ", ".join(claves), ""]
    libre = "\n".join(secciones.get("", [])).strip()
    if libre:
        partes += [libre, ""]
    for nombre in SECCIONES:
        cuerpo = "\n".join(l for l in secciones.get(nombre, []) if l.strip()).strip()
        if cuerpo:
            partes += ["## " + nombre, cuerpo, ""]
    for nombre, lineas in secciones.items():
        if nombre and nombre not in SECCIONES:
            cuerpo = "\n".join(lineas).strip()
            if cuerpo:
                partes += ["## " + nombre, cuerpo, ""]
    os.makedirs(CONOCIMIENTO, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(partes).rstrip() + "\n")


def _archivos():
    if not os.path.isdir(CONOCIMIENTO):
        return []
    return [os.path.join(CONOCIMIENTO, n) for n in sorted(os.listdir(CONOCIMIENTO)) if n.lower().endswith(".md")]


def archivo_de(app):
    for ruta in _archivos():
        datos = _leer_archivo(ruta)
        if datos and app in datos[0]:
            return ruta, datos
    ruta = os.path.join(CONOCIMIENTO, _slug(app) + ".md")
    n = 2
    while os.path.exists(ruta):
        ruta = os.path.join(CONOCIMIENTO, _slug(app) + "-" + str(n) + ".md")
        n += 1
    return ruta, ([app], {"": []})


def notas_para(titulo, maximo):
    app = app_de(titulo)
    bajo = (titulo or "").lower().strip()
    partes = []
    for ruta in _archivos():
        datos = _leer_archivo(ruta)
        if not datos:
            continue
        claves, secciones = datos
        if (app and app in claves) or any(bajo.endswith(c) for c in claves):
            trozos = []
            for nombre in ("Correcciones", ""):
                cuerpo = "\n".join(secciones.get(nombre, [])).strip()
                if cuerpo:
                    trozos.append(("Correcciones del usuario (son lo más fiable):\n" if nombre else "") + cuerpo)
            mapa = "\n".join(secciones.get("Mapa", [])).strip()
            if mapa:
                trozos.append("Mapa de la aplicación:\n" + mapa)
            partes.append("\n\n".join(trozos))
    return "\n\n".join(p for p in partes if p)[:maximo]


def agregar_nota(app, texto):
    ruta, (claves, secciones) = archivo_de(app)
    secciones.setdefault("Correcciones", []).append("- " + texto.strip())
    _escribir_archivo(ruta, claves, secciones)
    return ruta


def guardar_mapa(app, mapa):
    ruta, (claves, secciones) = archivo_de(app)
    secciones["Mapa"] = ["(explorado el " + time.strftime("%Y-%m-%d") + ")"] + mapa.strip().split("\n")
    _escribir_archivo(ruta, claves, secciones)
    return ruta


def guardar_receta(app, objetivo, pasos, fuente, crudos=None):
    os.makedirs(CONOCIMIENTO, exist_ok=True)
    dato = {"app": app, "objetivo": objetivo.strip(), "pasos": list(pasos), "fuente": fuente, "fecha": time.strftime("%Y-%m-%d %H:%M")}
    if crudos is not None and list(crudos) != list(pasos):
        dato["crudos"] = list(crudos)
    with open(RECETAS, "a", encoding="utf-8") as f:
        f.write(json.dumps(dato, ensure_ascii=False) + "\n")


def leer_recetas():
    if not os.path.exists(RECETAS):
        return []
    res = []
    with open(RECETAS, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                res.append(json.loads(linea))
            except Exception:
                continue
    return res


def buscar_recetas(objetivo, app, n=3):
    buscadas = palabras(objetivo)
    if not buscadas:
        return []
    puntuadas = []
    vistos = set()
    for r in reversed(leer_recetas()):
        clave = (r.get("app"), normalizar(r.get("objetivo", "")))
        if clave in vistos:
            continue
        vistos.add(clave)
        suyas = palabras(r.get("objetivo", ""))
        if not suyas:
            continue
        comun = len(buscadas & suyas)
        if comun == 0:
            continue
        puntos = comun / len(buscadas | suyas)
        if app and r.get("app") == app:
            puntos += 0.25
        if r.get("fuente") == "demostracion":
            puntos += 0.1
        if puntos >= 0.3:
            puntuadas.append((puntos, r))
    puntuadas.sort(key=lambda x: -x[0])
    return [r for _, r in puntuadas[:n]]


def texto_recetas(recetas):
    bloques = []
    for r in recetas:
        origen = "te lo enseñó el usuario" if r.get("fuente") == "demostracion" else "lo hiciste bien antes"
        pasos = "; ".join(str(i) + ") " + p for i, p in enumerate(r.get("pasos", []), start=1))
        bloques.append("- «" + r.get("objetivo", "") + "» en " + (r.get("app") or "?") + " (" + origen + "): " + pasos)
    return "\n".join(bloques)


DISPARO_DEMO = re.compile(
    r"^\s*(?:(?:mirame|observame|fijate|mira|observa|aprende)\s*(?:bien\s*)?(?:como\s*|cuando\s*)?(?:se\s+)?"
    r"|te\s+(?:voy\s+a\s+)?ensen\w*\s*(?:a\s+|como\s+)?(?:se\s+)?)"
)
DISPARO_NOTA = re.compile(r"^\s*(?:anota|apunta|recuerda|guarda)\s+(?:que\s+)?")


def objetivo_de_demo(texto):
    m = DISPARO_DEMO.match(normalizar(texto))
    resto = texto[m.end():] if m else texto
    return resto.strip(" ,.:;¿?¡!")


def limpiar_correccion(texto):
    m = DISPARO_NOTA.match(normalizar(texto))
    resto = texto[m.end():] if m else texto
    resto = resto.strip(" ,.:;")
    return resto[:1].upper() + resto[1:] if resto else resto


def limpiar_pasos(pasos):
    limpios = []
    for paso in pasos:
        if paso.startswith(("clic en", "clic derecho en")) and ("(Document)" in paso or "sin nombre" in paso or "(Pane)" in paso or "(Group)" in paso):
            continue
        if limpios and limpios[-1] == paso:
            continue
        limpios.append(paso)
    return limpios


def _escribir_recetas(recetas):
    os.makedirs(CONOCIMIENTO, exist_ok=True)
    with open(RECETAS, "w", encoding="utf-8") as f:
        for r in recetas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def borrar_ultima_receta(app=None):
    recetas = leer_recetas()
    for i in range(len(recetas) - 1, -1, -1):
        if app is None or recetas[i].get("app") == app:
            quitada = recetas.pop(i)
            _escribir_recetas(recetas)
            return quitada
    return None


def recetas_de_app(app):
    return [r for r in leer_recetas() if r.get("app") == app]
