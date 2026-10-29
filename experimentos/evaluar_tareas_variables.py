"""Ensayos del modelo con memoria y parámetros en interfaces simuladas; nunca opera la PC."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import acciones
import agente
import marcas
import parametros
import tareas


DEMO = 'Reserva por DHCP la IP 192.168.20.83 para MAC AA:BB:CC:DD:EE:01 en VLAN 20'
PASOS_DEMO = ['escribí «AA:BB:CC:DD:EE:01» en «MAC»', 'escribí «192.168.20.83» en «IP»', 'escribí «20» en «VLAN»', 'clic en «Guardar»']


class Laboratorio:
    def __init__(self, caso):
        self.caso = caso
        self.fuente = caso != 'parametros'
        self.foco = 1
        self.guardado = None
        self.valores = {'cantidad': ''} if caso == 'lectura' else {'estado': ''} if caso == 'instrucciones' else {'mac': '', 'ip': '', 'vlan': ''}

    def observar(self):
        if self.fuente:
            texto = 'Cantidad: 83' if self.caso == 'lectura' else 'Escribe «REVISADO» en el campo Estado.\nGuarda el formulario.'
            elementos = [('Document', 'Contenido de la nota', 0, 0, 400, 200), ('Button', 'Abrir formulario', 0, 220, 180, 250)]
            estado = {'ventana': 'Nota ficticia de prueba', 'hwnd': 100,
                      'foco': {'n': 1, 'nombre': 'Contenido de la nota', 'rol': 'Document', 'editable': True, 'valor': texto},
                      'texto_visible': texto, 'detalles': {'1': {'valor': texto}}}
        else:
            elementos = [('Edit', k.upper() if k in ('mac', 'ip', 'vlan') else k.capitalize(), 0, i * 40, 300, i * 40 + 30)
                         for i, k in enumerate(self.valores)]
            elementos.append(('Button', 'Guardar formulario', 0, 200, 200, 230))
            claves = list(self.valores)
            estado = {'ventana': 'Formulario ficticio de prueba', 'hwnd': 101,
                      'foco': {'n': self.foco, 'nombre': elementos[self.foco - 1][1], 'rol': elementos[self.foco - 1][0],
                               'editable': self.foco <= len(claves), 'valor': self.valores[claves[self.foco - 1]] if self.foco <= len(claves) else ''},
                      'texto_visible': 'Guardado: ' + json.dumps(self.guardado, ensure_ascii=False) if self.guardado else 'Cambios sin guardar',
                      'detalles': {str(i): {'valor': self.valores[k]} for i, k in enumerate(claves, 1)}}
        return elementos, estado

    def aplicar(self, a):
        if a['tipo'] == 'clic':
            if self.fuente and a['n'] == 2:
                self.fuente, self.foco = False, 1
            elif not self.fuente and a['n'] == len(self.valores) + 1:
                self.guardado = dict(self.valores)
                self.foco = a['n']
            else:
                self.foco = a['n']
        elif a['tipo'] == 'escribir':
            if self.fuente or not 1 <= self.foco <= len(self.valores):
                raise ValueError('Intento de escribir fuera del campo observado')
            clave = list(self.valores)[self.foco - 1]
            self.valores[clave] = a['texto'] if a.get('reemplazar') else self.valores[clave] + a['texto']
            self.guardado = None
        elif a['tipo'] == 'tecla':
            if a['tecla'] in ('enter', 'ctrl+s', 'ctrl+g') and not self.fuente:
                self.guardado = dict(self.valores)
            else:
                raise ValueError('El laboratorio no soporta esa tecla')
        elif a['tipo'] not in ('decir', 'esperar'):
            raise ValueError('Acción no soportada por el laboratorio')

    def cumplida(self):
        esperado = {'cantidad': '83'} if self.caso == 'lectura' else {'estado': 'REVISADO'} if self.caso == 'instrucciones' else {
            'mac': 'AA:BB:CC:DD:EE:02', 'ip': '192.168.40.9', 'vlan': '40'}
        return self.guardado == esperado


def ejecutar(caso, semilla):
    if caso == 'lectura':
        objetivo = 'Lee la cantidad de la nota actual, luego escríbela en el formulario y guárdalo.'
        partes = ['Lee y conserva la cantidad de la nota', 'Escribe la cantidad en el formulario y guárdalo']
        referencias = None
    elif caso == 'instrucciones':
        objetivo = 'Lee las instrucciones de la nota actual y ejecútalas en el formulario de prueba.'
        partes = ['Lee las instrucciones de la nota', 'Ejecuta las instrucciones']
        referencias = None
    else:
        objetivo = 'Reserva por DHCP IP 192.168.40.9 para MAC AA:BB:CC:DD:EE:02 en VLAN 40 y guarda el formulario ficticio.'
        partes = [objetivo]
        preparada = parametros.instanciar(parametros.crear_plantilla(DEMO, PASOS_DEMO), objetivo)
        assert preparada['lista']
        referencias = {'receta_parametrizada': json.dumps(preparada, ensure_ascii=False)}
    tarea, app = tareas.SesionTarea(objetivo, partes), Laboratorio(caso)
    historial, traza, pasos, pendiente, feedback = [], [], [], None, ''
    inicio, peticion_inicio = time.monotonic(), len(marcas.PETICIONES)
    rechazos = 0
    for _ in range(24):
        elementos, estado = app.observar()
        estado['memoria_tarea'] = tarea.contexto()
        try:
            accion = agente.continuar_pendiente(pendiente, estado, elementos)
            pendiente = None
            if accion is None:
                accion, crudo, intentos = agente.proponer(objetivo, elementos, estado, historial,
                    marcas.preguntar_json, acciones.normalizar_tecla, traza=traza, feedback=feedback,
                    referencias=referencias, partes=partes, tarea=tarea)
            else:
                crudo, intentos = 'Continuación con foco comprobado', 0
            feedback = ''
            paso = {'accion': accion, 'crudo': crudo, 'intentos': intentos,
                    'ventana': estado['ventana'], 'etapa': tarea.indice + 1}
            pasos.append(paso)
            tipo = accion['tipo']
            recuperacion = None
            if tipo == 'nada':
                recuperacion = agente.verificar(objetivo, elementos, estado, historial, marcas.preguntar_json)
                paso['revision_recuperacion'] = recuperacion
                if tareas.confirmado(recuperacion):
                    tipo = 'listo'
                    paso['recuperacion_como_en_jarvis'] = True
            if tipo == 'recordar':
                tarea.recordar(accion['texto'], estado)
            elif tipo == 'importar_plan':
                tarea.importar_plan(accion['texto'], estado)
            elif tipo in ('siguiente', 'listo'):
                if tarea.actual:
                    v = agente.verificar(tarea.actual, elementos, estado, historial, marcas.preguntar_json)
                    paso['revision_etapa'] = v
                    tarea.avanzar(v)
                if not tarea.actual:
                    estado['memoria_tarea'] = tarea.contexto()
                    v = recuperacion or agente.verificar(objetivo, elementos, estado, historial, marcas.preguntar_json)
                    paso['revision_final'] = v
                    if tareas.confirmado(v):
                        tarea.terminar('completada')
                        break
                    tarea.etapas[-1]['estado'] = 'activa'
                    raise ValueError(v['pendiente'])
                continue
            elif tipo in ('nada', 'preguntar'):
                tarea.terminar('requiere_datos' if tipo == 'preguntar' else 'incompleta', accion.get('texto', accion.get('_evidencia', '')))
                break
            else:
                app.aplicar(accion)
                paso['entrada_simulada'] = True
                if tipo == 'decir':
                    tarea.registrar_respuesta(accion['texto'])
            nuevo_e, nuevo_estado = app.observar()
            historial.append(tipo + ': ' + str(accion.get('texto', accion.get('n', ''))))
            traza.append({'clave': repr(agente.clave_accion(accion, elementos)), 'firma_operativa': agente.firma_operativa(accion, elementos, estado),
                          'accion': historial[-1], 'evento': agente.evento_accion(accion, elementos, estado),
                          'resultado': {'cambio_observable': agente.huella(estado, elementos) != agente.huella(nuevo_estado, nuevo_e)}})
            pendiente = accion.get('_despues')
        except (ValueError, TypeError) as error:
            rechazos += 1
            feedback = str(error)
            if pasos:
                pasos[-1]['rechazo'] = feedback
            if rechazos >= 4:
                tarea.terminar('incompleta', feedback)
                break
    if tarea.estado == 'en_curso':
        tarea.terminar('incompleta', 'Límite de pasos del ensayo')
    peticiones = copy.deepcopy(marcas.PETICIONES[peticion_inicio:])
    assert all(p['modelo_servidor'] == 'fosfeno-nemotron' for p in peticiones)
    return {'caso': caso, 'semilla': semilla, 'segundos': round(time.monotonic() - inicio, 3),
            'exito_funcional': app.cumplida(), 'aceptado': tarea.estado == 'completada',
            'falso_exito': tarea.estado == 'completada' and not app.cumplida(),
            'memoria_conservada': bool(tarea.hechos), 'instrucciones_importadas': tarea.importado,
            'valores_guardados': app.guardado, 'respuesta_final': tarea.respuesta_final(),
            'sesion': tarea.resultado(), 'pasos': pasos, 'peticiones': peticiones}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--semillas', default='42')
    parser.add_argument('--casos', default='lectura,instrucciones,parametros')
    args = parser.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    marcas.PERFIL = dict(marcas.motor_ia.PERFILES['nemotron'], semilla=42, cache_prompt=False)
    resultados = []
    fuentes = ['agente.py', 'tareas.py', 'parametros.py', 'memoria.py', 'marcas.py', 'jarvis.py', 'experimentos/evaluar_tareas_variables.py']
    hashes = {n: hashlib.sha256((BASE / n).read_bytes()).hexdigest() for n in fuentes}
    (args.salida / 'condiciones.json').write_text(json.dumps({'codigo_sha256': hashes,
        'semillas': args.semillas, 'casos': args.casos, 'tipo': 'Estados sintéticos, no escritorio ni router'},
        ensure_ascii=False, indent=2), encoding='utf-8')
    for semilla in map(int, args.semillas.split(',')):
        marcas.PERFIL['semilla'] = semilla
        for caso in args.casos.split(','):
            r = ejecutar(caso, semilla)
            resultados.append(r)
            (args.salida / 'resultados.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: r[k] for k in ('caso', 'semilla', 'exito_funcional', 'aceptado', 'falso_exito', 'segundos')}, ensure_ascii=True), flush=True)
    assert hashes == {n: hashlib.sha256((BASE / n).read_bytes()).hexdigest() for n in fuentes}, 'Código cambiado durante el ensayo'
    tokens = [p['uso'].get('prompt_tokens', 0) for r in resultados for p in r['peticiones']]
    resumen = {'metodo': 'Modelo local sobre estados sintéticos; no escritorio, voz, WinBox ni RouterOS real.',
               'total': len(resultados), 'funcionales': sum(r['exito_funcional'] for r in resultados),
               'aceptados': sum(r['aceptado'] for r in resultados), 'falsos_exitos': sum(r['falso_exito'] for r in resultados),
               'max_prompt_tokens_observado': max(tokens, default=0), 'codigo_sha256': hashes,
               'nota': 'Casos nuevos diseñados junto con la función; muestra de desarrollo, no benchmark general. No cambia la comparación histórica de modelos.'}
    (args.salida / 'resumen.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
