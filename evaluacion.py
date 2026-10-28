"""Comparación reproducible de decisiones y tareas simuladas. Nunca opera la PC."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import statistics
import time

import acciones
import agente
import marcas
import motor_ia


CASOS = [
    {"id": "nota", "modo": "guardar", "objetivo": "En Notas escribe exactamente «Revisar inventario mañana» y guarda el borrador.",
     "campos": [("cuerpo", "Edit", "Cuerpo de la nota", "")], "esperado": {"cuerpo": "Revisar inventario mañana"}, "boton": "Guardar borrador"},
    {"id": "contacto", "modo": "guardar", "objetivo": "Cambia el nombre a «Mateo Ríos» y la ciudad a «Tarija», y guarda el contacto.",
     "campos": [("nombre", "Edit", "Nombre del contacto", "Invitado"), ("ciudad", "Edit", "Ciudad", "Pendiente")],
     "esperado": {"nombre": "Mateo Ríos", "ciudad": "Tarija"}, "boton": "Guardar contacto"},
    {"id": "chat", "modo": "chat", "objetivo": "Crea una conversación nueva y envía «Llegaré a las 18:45».",
     "campos": [("mensaje", "Edit", "Escribe un mensaje", "")], "esperado": {"mensaje": "Llegaré a las 18:45"}, "boton": "Enviar mensaje"},
    {"id": "busqueda", "modo": "buscar", "objetivo": "Busca «factura 072» en esta aplicación y espera a ver el resultado.",
     "campos": [("consulta", "Edit", "Buscar documentos", "")], "esperado": {"consulta": "factura 072"}, "boton": "Buscar"},
    {"id": "navegacion", "modo": "navegar", "objetivo": "Abre https://example.org/manual en una pestaña nueva.",
     "campos": [("url", "Edit", "Barra de direcciones y de búsqueda", "https://example.org/inicio")],
     "esperado": {"url": "https://example.org/manual"}, "boton": "Ir"},
    {"id": "checkbox", "modo": "guardar", "objetivo": "Desactiva «Mostrar avisos» y aplica las preferencias.",
     "campos": [("avisos", "CheckBox", "Mostrar avisos", True)], "esperado": {"avisos": False}, "boton": "Aplicar preferencias"},
    {"id": "selector", "modo": "guardar", "objetivo": "Cambia el idioma a Español y guarda la selección.",
     "campos": [("idioma", "ComboBox", "Idioma", "English")], "opciones": {"idioma": ["English", "Português", "Español"]},
     "esperado": {"idioma": "Español"}, "boton": "Guardar selección"},
    {"id": "cantidad", "modo": "guardar", "objetivo": "Introduce el producto «Cuadernos A5», cambia la cantidad a 7 y confirma la simulación.",
     "campos": [("producto", "Edit", "Producto", ""), ("cantidad", "Spinner", "Cantidad", "1")],
     "esperado": {"producto": "Cuadernos A5", "cantidad": "7"}, "boton": "Confirmar simulación"},
]


class AplicacionSimulada:
    """Estado independiente del modelo; el resultado real lo comprueba este entorno."""

    def __init__(self, caso, semilla):
        self.caso = caso
        self.semilla = semilla
        self.valores = {c[0]: c[3] for c in caso["campos"]}
        self.foco = None
        self.seleccionado = False
        self.enviado = None
        self.nuevo_chat = False
        self.nueva_pestana = False
        self.cargando = 0
        self.resultado = ""
        self.paso = 0
        self.mapa = []
        self.combo_abierto = None

    def observar(self):
        controles = [(k, rol, nombre) for k, rol, nombre, _ in self.caso["campos"]]
        controles += [("enviar", "Button", self.caso["boton"]), ("ayuda", "Button", "Ayuda")]
        if self.caso["modo"] == "chat":
            controles.append(("nuevo", "Button", "Nueva conversación"))
        if self.caso["modo"] == "navegar":
            controles.append(("pestana", "Button", "Nueva pestaña"))
        if self.combo_abierto:
            controles += [("opcion:" + valor, "ListItem", valor) for valor in self.caso['opciones'][self.combo_abierto]]
        posiciones = {k: i for i, (k, _, _) in enumerate(controles)}
        random.Random(self.semilla + self.paso // 2).shuffle(controles)
        self.mapa = [c[0] for c in controles]
        elementos = [(rol, nombre, 20, 60 + posiciones[k] * 50, 500, 90 + posiciones[k] * 50) for k, rol, nombre in controles]
        detalles = {}
        for n, (k, rol, _) in enumerate(controles, 1):
            if k in self.valores:
                detalles[str(n)] = {"activado": self.valores[k]} if rol == "CheckBox" else {"valor": self.valores[k]}
                if k in self.caso.get("opciones", {}):
                    detalles[str(n)]["opciones"] = self.caso["opciones"][k]
        foco = {"n": None, "nombre": "", "rol": "", "editable": False, "valor": ""}
        if self.foco in self.mapa:
            n = self.mapa.index(self.foco) + 1
            e = elementos[n - 1]
            foco.update(n=n, nombre=e[1], rol=e[0], editable=agente.es_editable(e[0]),
                        valor=self.valores.get(self.foco, ""), seleccionado=self.seleccionado)
        texto = self.resultado or ("Cargando resultados" if self.cargando else "Sin confirmar ni guardar")
        if self.caso["modo"] == "chat":
            texto += "\n" + ("Conversación nueva" if self.nuevo_chat else "Conversación anterior")
        if self.caso["modo"] == "navegar":
            texto += "\nPestaña actual: " + ("pestaña nueva" if self.nueva_pestana else "pestaña original")
        estado = {"ventana": "Aplicación de prueba: " + self.caso["id"], "hwnd": 101,
                  "foco": foco, "detalles": detalles, "texto_visible": texto}
        return elementos, estado

    def confirmar(self):
        self.enviado = copy.deepcopy(self.valores)
        if self.caso["modo"] == "chat":
            self.resultado = "Mensaje enviado: " + str(self.valores["mensaje"])
            self.valores["mensaje"] = ""
        elif self.caso["modo"] == "buscar":
            self.cargando = 1
        elif self.caso["modo"] == "navegar":
            self.resultado = "Página abierta: " + self.valores["url"]
        else:
            self.resultado = "Guardado correctamente: " + json.dumps(self.enviado, ensure_ascii=False)

    def aplicar(self, accion):
        tipo = accion["tipo"]
        if tipo == "clic":
            k = self.mapa[accion["n"] - 1]
            self.foco = k
            if k == "enviar": self.confirmar()
            elif k == "nuevo":
                self.nuevo_chat = True; self.foco = "mensaje"; self.valores["mensaje"] = ""
            elif k == "pestana":
                self.nueva_pestana = True; self.foco = "url"; self.valores["url"] = ""
            elif k.startswith('opcion:') and self.combo_abierto:
                self.valores[self.combo_abierto] = k.split(':', 1)[1]
                self.foco = self.combo_abierto
                self.combo_abierto = None
            elif k in self.caso.get('opciones', {}):
                self.combo_abierto = k
            elif isinstance(self.valores.get(k), bool): self.valores[k] = not self.valores[k]
        elif tipo == "escribir":
            if self.foco not in self.valores or isinstance(self.valores[self.foco], bool):
                raise ValueError("Escritura sin un campo enfocado")
            if accion.get("n") and self.mapa[accion["n"] - 1] != self.foco:
                raise ValueError("Escritura dirigida a otro campo")
            if accion.get("reemplazar") or self.seleccionado:
                self.valores[self.foco] = accion["texto"]
            else:
                self.valores[self.foco] = str(self.valores[self.foco]) + accion["texto"]
            self.seleccionado = False
        elif tipo == "tecla":
            tecla = accion["tecla"]
            if tecla == "ctrl+a": self.seleccionado = True
            elif tecla == "ctrl+t" and "url" in self.valores:
                self.nueva_pestana = True; self.foco = "url"; self.valores["url"] = ""
            elif tecla == "ctrl+l" and "url" in self.valores:
                self.foco = "url"; self.seleccionado = True
            elif tecla == "ctrl+s": self.confirmar()
            elif tecla == "enter" and (self.foco == "enviar" or self.caso["modo"] in ("chat", "buscar", "navegar")):
                self.confirmar()
            elif tecla in ("abajo", "arriba", "inicio", "fin") and self.foco in self.caso.get("opciones", {}):
                opciones = self.caso["opciones"][self.foco]
                indice = opciones.index(self.valores[self.foco])
                indice = 0 if tecla == "inicio" else len(opciones) - 1 if tecla == "fin" else min(len(opciones) - 1, max(0, indice + (1 if tecla == "abajo" else -1)))
                self.valores[self.foco] = opciones[indice]
            elif tecla == "tab":
                campos = list(self.valores)
                self.foco = campos[(campos.index(self.foco) + 1) % len(campos)] if self.foco in campos else campos[0]
        elif tipo == "esperar" and self.cargando:
            self.cargando -= 1
            self.resultado = "Resultado encontrado para: " + str(self.enviado["consulta"])
        elif tipo not in ("decir", "desplazar", "esperar"):
            raise ValueError("Acción no ejecutable: " + tipo)
        self.paso += 1

    def cumplida(self):
        if self.enviado != self.caso["esperado"]:
            return False
        if self.caso["modo"] == "chat" and not self.nuevo_chat: return False
        if self.caso["modo"] == "navegar" and not self.nueva_pestana: return False
        return not self.cargando


def ejecutar_caso(caso, motor, semilla, max_pasos=14):
    perfil_anterior = marcas.PERFIL
    marcas.PERFIL = copy.deepcopy(motor_ia.PERFILES[motor])
    marcas.PERFIL.update(semilla=semilla, cache_prompt=False)
    app = AplicacionSimulada(caso, semilla)
    historial, traza, pasos = [], [], []
    pendiente, feedback = None, ""
    inicio = time.monotonic()
    peticiones_inicio = len(marcas.PETICIONES)
    resultado = {"caso": caso["id"], "motor": motor, "semilla": semilla, "correcto": False,
                 "falsos_listo_propuestos": 0, "falso_exito_aceptado": False}
    try:
        for numero in range(max_pasos):
            elementos, estado = app.observar()
            accion = agente.continuar_pendiente(pendiente, estado, elementos)
            pendiente = None
            if accion is None:
                accion, dato, intentos = agente.proponer(caso["objetivo"], elementos, estado, historial,
                    marcas.preguntar_json, acciones.normalizar_tecla, traza=traza, feedback=feedback)
            feedback = ""
            registro = {"numero": numero + 1, "accion": accion, "estado": copy.deepcopy(estado)}
            pasos.append(registro)
            if accion["tipo"] in ("listo", "nada"):
                verificacion = agente.verificar(caso["objetivo"], elementos, estado, historial, marcas.preguntar_json)
                registro["verificacion"] = verificacion
                if accion['tipo'] == 'listo' and not app.cumplida(): resultado["falsos_listo_propuestos"] += 1
                if agente.final_confirmado(verificacion):
                    resultado["correcto"] = app.cumplida()
                    resultado["falso_exito_aceptado"] = not resultado["correcto"]
                    resultado["motivo"] = "completado" if resultado["correcto"] else "declaró éxito sin cumplir el objetivo real"
                    break
                if accion['tipo'] == 'nada':
                    resultado['motivo'] = 'no pudo continuar y no se confirmó el objetivo'
                    break
                feedback = "Verificación: " + str(verificacion.get("pendiente", "Falta evidencia"))
                continue
            if accion["tipo"] == "nada":
                resultado["motivo"] = "no pudo continuar"
                break
            clave = repr(agente.clave_accion(accion, elementos))
            if agente.repetida_sin_progreso(accion, elementos, traza):
                feedback = "No se ejecutó una acción repetida sin progreso. Elige un paso distinto."
                continue
            app.aplicar(accion)
            elementos_despues, estado_despues = app.observar()
            if accion["tipo"] == "clic": texto = "clic en «" + elementos[accion["n"] - 1][1] + "»"
            elif accion["tipo"] == "escribir": texto = ("reemplacé por «" if accion.get("reemplazar") else "escribí «") + accion["texto"] + "»"
            elif accion["tipo"] == "tecla": texto = "pulsé la tecla " + accion["tecla"]
            else: texto = accion["tipo"]
            historial.append(texto)
            traza.append({"clave": clave, "accion": texto, "resultado": {
                "cambio_observable": agente.huella(estado, elementos) != agente.huella(estado_despues, elementos_despues),
                "foco": estado_despues["foco"], "ventana": estado_despues["ventana"]}})
            pendiente = accion.get("_despues")
        else:
            resultado["motivo"] = "límite de pasos"
    except Exception as error:
        resultado["motivo"] = type(error).__name__ + ": " + str(error)
    finally:
        marcas.PERFIL = perfil_anterior
    resultado.update(segundos=round(time.monotonic() - inicio, 3), pasos=len(pasos), objetivo_logrado=app.cumplida(),
        objetivo=caso["objetivo"], valor_final=app.enviado, traza=pasos,
        peticiones=copy.deepcopy(marcas.PETICIONES[peticiones_inicio:]))
    esperados = motor_ia.PERFILES[motor]
    urls = {esperados['url'], esperados.get('planificador_url', esperados['url'])}
    modelos = {esperados['modelo_api'], esperados.get('planificador_modelo', esperados['modelo_api'])}
    if any(p['url'] not in urls or p.get('modelo_servidor') not in modelos for p in resultado['peticiones']):
        raise RuntimeError('Comparación inválida: respondió un servidor distinto al motor seleccionado')
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--motores", default="lfm3,nemotron")
    parser.add_argument("--semillas", default="42,99")
    parser.add_argument("--casos", default="")
    parser.add_argument("--salida", type=Path, default=Path(marcas.OUT) / "evaluacion")
    args = parser.parse_args()
    motores = args.motores.split(",")
    if any(m not in motor_ia.PERFILES for m in motores): parser.error("Motor desconocido")
    semillas = [int(v) for v in args.semillas.split(",")]
    casos = [c for c in CASOS if not args.casos or c["id"] in args.casos.split(",")]
    args.salida.mkdir(parents=True, exist_ok=True)
    manifiesto = {"tipo": "tareas simuladas, sin control del escritorio", "motores": motores, "semillas": semillas,
        "versiones": {}, "archivos": {n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
        for n in ("agente.py", "marcas.py", "evaluacion.py", "motor_ia.py")}, "casos": casos}
    for motor in motores:
        url = motor_ia.PERFILES[motor]["url"].rsplit('/v1/', 1)[0]
        try:
            props = marcas.requests.get(url + '/props', timeout=5).json()
            manifiesto["versiones"][motor] = {k: props.get(k) for k in ('model_alias', 'model_path', 'build_info', 'modalities')}
        except Exception as error:
            parser.error('Servidor no disponible: ' + motor + ': ' + str(error))
    (args.salida / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding='utf-8')
    resultados = []
    for semilla in semillas:
        orden = [(caso, motor) for caso in casos for motor in motores]
        random.Random(semilla).shuffle(orden)
        for caso, motor in orden:
            resultado = ejecutar_caso(caso, motor, semilla)
            resultados.append(resultado)
            (args.salida / 'resultados.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: v for k, v in resultado.items() if k not in ('traza', 'peticiones', 'objetivo')}, ensure_ascii=True), flush=True)
    resumen = {}
    for motor in motores:
        grupo = [r for r in resultados if r['motor'] == motor]
        resumen[motor] = {'completadas': sum(r['correcto'] for r in grupo), 'total': len(grupo),
            'objetivos_logrados': sum(r['objetivo_logrado'] for r in grupo),
            'falsos_exitos': sum(r['falso_exito_aceptado'] for r in grupo),
            'mediana_segundos': round(statistics.median(r['segundos'] for r in grupo), 3),
            'mediana_exitos_segundos': round(statistics.median(r['segundos'] for r in grupo if r['correcto']), 3) if any(r['correcto'] for r in grupo) else None,
            'peticiones': sum(len(r['peticiones']) for r in grupo)}
    (args.salida / 'resumen.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=True), flush=True)


if __name__ == '__main__': main()
