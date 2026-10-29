"""Evalúa decisiones del controlador sobre ventanas de prueba registradas.

Solo lee la interfaz. Un operador debe ejecutar cada propuesta y confirmar
lo que realmente hizo. No mide los atajos de voz ni SendInput de Fosfeno.
"""
import argparse
import copy
import ctypes
import hashlib
import importlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import time
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
os.environ['FOSFENO_MOTOR'] = 'nemotron'
import agente
import marcas
import memoria
import parametros
import tareas
import uiautomation as auto


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--puerto', type=int, default=8103)
    parser.add_argument('--conocimiento', type=Path, help='Carpeta aislada de recetas del ensayo')
    parser.add_argument('--memoria-tarea', action='store_true', help='Ejercitar memoria y cierre del controlador actual')
    args = parser.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    token, sesion = secrets.token_urlsafe(24), {}
    tarea_actual = [None]
    if args.conocimiento:
        memoria.CONOCIMIENTO = str(args.conocimiento)
        memoria.RECETAS = str(args.conocimiento / 'recetas.jsonl')
    marcas.PERFIL = dict(marcas.PERFIL, semilla=42, cache_prompt=False)
    (args.salida / 'sesion-local.json').write_text(json.dumps({'puerto': args.puerto, 'token': token}), encoding='utf-8')

    class Handler(BaseHTTPRequestHandler):
        def responder(self, dato, status=200):
            body = json.dumps(dato, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)

        def guardar(self):
            if tarea_actual[0] is not None:
                sesion['memoria_tarea'] = tarea_actual[0].resultado()
            (args.salida / (sesion['id'] + '-traza.json')).write_text(
                json.dumps(sesion, ensure_ascii=False, indent=2), encoding='utf-8')

        def observar(self):
            top = auto.GetForegroundControl()
            actual = int(top.NativeWindowHandle)
            # Los diálogos nativos de abrir/guardar tienen otro HWND y pueden
            # no aparecer como ventanas independientes en el adaptador visual.
            # Aceptar únicamente la cadena de propietarios de la ventana propia.
            propietario = actual
            for _ in range(6):
                if propietario in sesion['ventanas']:
                    break
                propietario = int(ctypes.windll.user32.GetWindow(propietario, 4) or 0)
                if not propietario:
                    break
            if propietario not in sesion['ventanas']:
                raise ValueError('La ventana activa no está registrada para esta prueba')
            imagen = marcas.grab()
            titulo, elementos, truncado = marcas.reunir(*imagen.size, incluir_barra=False)
            estado = copy.deepcopy(marcas.ESTADO_UI)
            if estado['hwnd'] != actual:
                raise ValueError('La ventana cambió durante la observación')
            return imagen, titulo, elementos, estado, truncado

        def do_POST(self):
            if self.headers.get('Authorization') != 'Bearer ' + token:
                return self.responder({'error': 'No autorizado'}, 401)
            try:
                datos = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                ruta = urlparse(self.path).path
                if ruta == '/caso':
                    importlib.reload(agente)
                    importlib.reload(marcas)
                    marcas.PERFIL = dict(marcas.PERFIL, semilla=42, cache_prompt=False)
                    ident = datos['id']
                    if not ident.replace('-', '').isalnum():
                        raise ValueError('Id inválido')
                    if datos.get('reanudar'):
                        if args.memoria_tarea:
                            raise ValueError('Los ensayos con memoria se inician de nuevo; no rehidratar una tarea parcial sin validación')
                        anterior = json.loads((args.salida / (ident + '-traza.json')).read_text(encoding='utf-8'))
                        if anterior['objetivo'] != datos['objetivo']:
                            raise ValueError('No se puede cambiar el objetivo al reanudar')
                        sesion.clear()
                        sesion.update(anterior)
                        ejecutadas = [r for r in sesion['resultados'] if r.get('ejecutada_por_operador')]
                        for paso, r in zip(sesion['traza'], ejecutadas):
                            paso['evento'] = agente.evento_accion(r['accion'], r['elementos'], r['estado'])
                            paso['firma_operativa'] = agente.firma_operativa(r['accion'], r['elementos'], r['estado'])
                        sesion['ventanas'] = datos['ventanas']
                        return self.responder({'reanudado': ident, 'pasos': len(sesion['historial'])})
                    sesion.clear()
                    tarea_actual[0] = tareas.SesionTarea(datos['objetivo']) if args.memoria_tarea else None
                    sesion.update(id=ident, objetivo=datos['objetivo'], ventanas=datos['ventanas'], historial=[],
                                  traza=[], resultados=[], pendiente=None,
                                  sin_recetas=bool(datos.get('sin_recetas')),
                                  codigo_sha256={n: hashlib.sha256((BASE / n).read_bytes()).hexdigest()
                                                 for n in ('agente.py', 'marcas.py', 'jarvis.py')})
                    self.guardar()
                    return self.responder({'creado': ident})
                if not sesion:
                    raise ValueError('Falta iniciar un caso')
                if ruta == '/ventanas':
                    sesion['ventanas'] = datos['ventanas']
                    self.guardar()
                    return self.responder({'registradas': sesion['ventanas']})
                if ruta == '/fallo':
                    sesion.pop('actual', None)
                    sesion['resultados'][-1]['incidencia_operador'] = datos['detalle']
                    self.guardar()
                    return self.responder({'incidencia_guardada': True})
                if ruta == '/confirmar':
                    if datos.get('ejecutada') is not True:
                        raise ValueError('Solo confirmar acciones efectivamente ejecutadas')
                    actual = sesion.pop('actual')
                    accion = actual['accion']
                    if tarea_actual[0] is not None:
                        if accion['tipo'] == 'recordar':
                            tarea_actual[0].recordar(accion['texto'], actual['estado'])
                        elif accion['tipo'] == 'importar_plan':
                            tarea_actual[0].importar_plan(accion['texto'], actual['estado'])
                        elif accion['tipo'] == 'decir':
                            tarea_actual[0].registrar_respuesta(accion['texto'])
                        elif accion['tipo'] == 'preguntar':
                            tarea_actual[0].terminar('requiere_datos', accion['texto'])
                    texto = descripcion(accion, actual['elementos'])
                    sesion['historial'].append(texto)
                    sesion['traza'].append({'clave': repr(agente.clave_accion(accion, actual['elementos'])),
                                            'firma_operativa': agente.firma_operativa(accion, actual['elementos'], actual['estado']),
                                            'evento': agente.evento_accion(accion, actual['elementos'], actual['estado']),
                                            'accion': texto, 'huella': agente.huella(actual['estado'], actual['elementos'])})
                    sesion['pendiente'] = accion.get('_despues')
                    sesion['resultados'][-1]['ejecutada_por_operador'] = True
                    self.guardar()
                    return self.responder({'confirmada': texto})
                with auto.UIAutomationInitializerInThread():
                    marcas.preparar_dpi()
                    imagen, titulo, elementos, estado, truncado = self.observar()
                    if ruta == '/estado':
                        return self.responder({'estado': estado, 'elementos': elementos, 'truncado': truncado})
                    if ruta != '/paso':
                        raise ValueError('Ruta desconocida')
                    if 'actual' in sesion:
                        raise ValueError('La propuesta anterior todavía no se ha confirmado')
                    if len(sesion['historial']) >= agente.MAX_PASOS:
                        raise ValueError('Presupuesto de 36 acciones alcanzado')
                    if sesion['traza']:
                        ultimo = sesion['traza'][-1]
                        ultimo['resultado'] = {'cambio_observable': ultimo['huella'] != agente.huella(estado, elementos),
                                               'ventana': titulo, 'foco': estado['foco']}
                    inicio, nreq = time.monotonic(), len(marcas.PETICIONES)
                    estado['archivos_observados'] = marcas.evidencia_archivos(sesion['objetivo'])
                    estado['copias_observadas'] = marcas.evidencia_copias(sesion['objetivo'], sesion['traza'])
                    ejemplos, recetas, preflight = '', [], None
                    if args.conocimiento and not sesion.get('sin_recetas', False):
                        recetas = memoria.buscar_recetas(sesion['objetivo'], memoria.app_de(titulo))
                        ejemplos = memoria.texto_recetas(recetas, sesion['objetivo'])
                        if recetas and recetas[0].get('plantilla'):
                            preparada = parametros.instanciar(recetas[0]['plantilla'], sesion['objetivo'])
                            if not preparada['lista']:
                                preflight = {'tipo': 'preguntar', 'texto': preparada['pregunta'], '_origen': 'validacion_parametros'}
                    sesion['referencias_recuperadas'] = recetas
                    sesion['ejemplos_entregados'] = ejemplos
                    accion = agente.continuar_pendiente(sesion['pendiente'], estado, elementos)
                    sesion['pendiente'] = None
                    if accion:
                        crudo = 'Continuación de escritura con foco observado'
                    else:
                        if preflight:
                            accion, crudo = preflight, 'Validación determinista de parámetros antes de la inferencia'
                        else:
                            accion, crudo, _, _, _ = marcas.decidir_accion(sesion['objetivo'], imagen, titulo, elementos,
                                                                    sesion['historial'], estado=estado, traza=sesion['traza'],
                                                                    feedback=sesion.pop('feedback', ''), ejemplos=ejemplos,
                                                                    tarea=tarea_actual[0])
                    resultado = {'accion': accion, 'crudo': crudo, 'ventana': titulo, 'estado': estado,
                                 'codigo_sha256': {n: hashlib.sha256((BASE / n).read_bytes()).hexdigest() for n in ('agente.py', 'marcas.py', 'jarvis.py')},
                                 'elementos': elementos, 'truncado': truncado, 'segundos': round(time.monotonic() - inicio, 3)}
                    if accion['tipo'] in ('listo', 'nada'):
                        estado['archivos_observados'] = marcas.evidencia_archivos(sesion['objetivo'])
                        estado['copias_observadas'] = marcas.evidencia_copias(sesion['objetivo'], sesion['traza'])
                        if tarea_actual[0] is not None:
                            estado['memoria_tarea'] = tarea_actual[0].contexto()
                        resultado['verificacion'] = agente.verificar(sesion['objetivo'], elementos, estado,
                                                                     sesion['historial'], marcas.preguntar_json, imagen)
                        if accion['tipo'] == 'listo' and not agente.final_confirmado(resultado['verificacion']):
                            sesion['feedback'] = 'La verificación rechazó el final. Falta: ' + resultado['verificacion'].get('pendiente', '')
                        if tarea_actual[0] is not None and agente.final_confirmado(resultado['verificacion']):
                            tarea_actual[0].avanzar(resultado['verificacion'])
                            tarea_actual[0].terminar('completada')
                            resultado['respuesta_final'] = tarea_actual[0].respuesta_final()
                    resultado['peticiones'] = copy.deepcopy(marcas.PETICIONES[nreq:])
                    if any(p['modelo_servidor'] != 'fosfeno-nemotron' for p in resultado['peticiones']):
                        raise ValueError('Respondió otro modelo')
                    if accion['tipo'] == 'clic':
                        resultado['destino'] = elementos[accion['n'] - 1]
                    sesion['resultados'].append(resultado)
                    if accion['tipo'] not in ('listo', 'nada'):
                        sesion['actual'] = {'accion': accion, 'estado': estado, 'elementos': elementos}
                    self.guardar()
                    return self.responder({k: v for k, v in resultado.items() if k not in ('elementos', 'crudo', 'peticiones')})
            except Exception as error:
                self.responder({'error': str(error)}, 409)

        def log_message(self, *args):
            pass

    print('Evaluador listo; solo observa ventanas registradas y propone acciones.', flush=True)
    HTTPServer(('127.0.0.1', args.puerto), Handler).serve_forever()


def descripcion(accion, elementos):
    tipo = accion['tipo']
    if tipo == 'clic':
        return 'clic en «' + elementos[accion['n'] - 1][1] + '»'
    if tipo == 'escribir':
        return ('reemplacé el contenido por «' if accion.get('reemplazar') else 'escribí «') + accion['texto'] + '»'
    if tipo == 'tecla':
        return 'pulsé la tecla ' + accion['tecla']
    return str(accion)


if __name__ == '__main__':
    main()
