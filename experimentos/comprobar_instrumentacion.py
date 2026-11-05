import argparse
import ast
from contextlib import ExitStack, nullcontext
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import MagicMock, patch


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))


def fuente(nombre, version):
    if version == 'head':
        return subprocess.run(['git', 'show', 'HEAD:' + nombre + '.py'], cwd=BASE,
            check=True, capture_output=True).stdout.decode('utf-8-sig')
    return (BASE / (nombre + '.py')).read_text(encoding='utf-8-sig')


class SinEnvoltorios(ast.NodeTransformer):
    def visit_Call(self, nodo):
        nodo = self.generic_visit(nodo)
        if (isinstance(nodo.func, ast.Attribute) and nodo.func.attr == 'llamar'
                and isinstance(nodo.func.value, ast.Name) and nodo.func.value.id == 'rendimiento'):
            return ast.copy_location(ast.Call(func=nodo.args[1], args=nodo.args[2:],
                keywords=nodo.keywords), nodo)
        return nodo


def equivalencia_ast():
    resultado = {}
    for nombre in ('jarvis', 'marcas'):
        actual = ast.parse(fuente(nombre, 'actual'))
        anterior = ast.parse(fuente(nombre, 'head'))
        normalizado = SinEnvoltorios().visit(actual)
        resultado[nombre + '.py'] = ast.dump(normalizado) == ast.dump(anterior)
    return resultado


def cargar(version):
    for nombre in ('rendimiento', 'marcas', 'jarvis'):
        if version == 'head':
            modulo = types.ModuleType(nombre)
            modulo.__file__ = str(BASE / (nombre + '.py'))
            sys.modules[nombre] = modulo
            exec(compile(fuente(nombre, version), modulo.__file__, 'exec'), modulo.__dict__)
        else:
            importlib.import_module(nombre)
    return tuple(sys.modules[n] for n in ('rendimiento', 'marcas', 'jarvis'))


def simular(version, carpeta):
    rendimiento, marcas, jarvis = cargar(version)
    from PIL import Image
    import tareas
    from entornos_evaluacion import sin_entrada_nativa
    carpeta.mkdir(parents=True, exist_ok=False)
    eventos = []
    acciones = []
    consultas = []
    estado = {'ventana': 'Panel simulado', 'hwnd': 10, 'foco': {},
        'detalles': {'1': {'valor': ''}}, 'texto_visible': ''}
    elementos = [('Edit', 'Texto', 0, 0, 100, 30)]
    imagen = Image.new('RGB', (200, 100), 'white')
    guardado = None
    propuestas = iter([{'tipo': 'clic', 'n': 1},
        {'tipo': 'escribir', 'n': 1, 'texto': 'prueba', 'reemplazar': True},
        {'tipo': 'tecla', 'tecla': 'ctrl+s'}, {'tipo': 'listo'}])
    esquema = {'type': 'object', 'properties': {'tipo': {'type': 'string'}}, 'required': ['tipo']}
    def anotar(tipo, dato):
        eventos.append({'tipo': tipo, 'dato': copy.deepcopy(dato)})
    def post(url, **kwargs):
        payload = copy.deepcopy(kwargs['json'])
        consultas.append({'url': url, 'payload': payload, 'timeout': kwargs.get('timeout')})
        anotar('consulta', consultas[-1])
        schema = payload['response_format']['json_schema']['schema']
        dato = ({'cumplido': True, 'evidencia': 'Guardado correctamente: prueba', 'pendiente': ''}
                if 'cumplido' in schema.get('properties', {}) else next(propuestas))
        respuesta = marcas.requests.Response()
        respuesta.status_code = 200
        respuesta._content = json.dumps({'model': 'modelo-prueba', 'choices': [
            {'message': {'content': json.dumps(dato)}, 'finish_reason': 'stop'}],
            'usage': {'completion_tokens': 12, 'prompt_tokens': 20, 'total_tokens': 32},
            'timings': {'prompt_ms': 1, 'predicted_ms': 1}}).encode()
        return respuesta
    def decidir(objetivo, img, titulo, controles, historial, *args, **kwargs):
        dato = marcas.preguntar_json('Prueba determinista del transporte JSON.',
            json.dumps({'objetivo': objetivo, 'estado': estado, 'historial': historial},
                       ensure_ascii=False, sort_keys=True), esquema)
        anotar('propuesta', dato)
        return dato, json.dumps(dato), '1: Texto', img, 0.0
    def observar(*args, **kwargs):
        anotar('reobservacion', estado)
        return copy.deepcopy(estado)
    def escanear():
        anotar('captura', estado)
        return imagen, estado['ventana'], elementos
    def validar(*args, **kwargs):
        anotar('validacion', {'args': args, 'kwargs': kwargs})
        return True
    def pausa(segundos):
        anotar('espera', segundos)
    def cancelar(segundos):
        anotar('espera_cancelable', segundos)
        return False
    def aplicar(nombre, *args):
        nonlocal guardado
        registro = {'nombre': nombre, 'args': list(args)}
        acciones.append(registro)
        anotar('accion', registro)
        if nombre == 'clic':
            estado['foco'] = {'n': 1, 'nombre': 'Texto', 'rol': 'Edit',
                'editable': True, 'valor': estado['detalles']['1']['valor']}
        elif nombre == 'escribir':
            estado['detalles']['1']['valor'] = args[0]
            estado['foco']['valor'] = args[0]
        elif nombre == 'tecla':
            guardado = estado['detalles']['1']['valor']
            estado['texto_visible'] = 'Guardado correctamente: ' + guardado
        return True
    def evidencia(nombre, *args):
        anotar(nombre, args)
        return []
    tarea = tareas.SesionTarea('Escribe prueba en el campo y guarda el resultado.')
    tarea.id = 'determinista'
    with sin_entrada_nativa(), ExitStack() as pila:
        pila.enter_context(patch.dict(os.environ, {'FOSFENO_TIEMPOS_LOG': str(carpeta / 'pasos.jsonl'),
            'FOSFENO_TIEMPOS_CRUDO': '0', 'FOSFENO_GBNF_EXPERIMENTAL': '0'}))
        pila.enter_context(patch.object(marcas, 'OUT', str(carpeta)))
        pila.enter_context(patch.object(marcas, 'ESTADO_UI', estado))
        pila.enter_context(patch.object(marcas, 'PERFIL', {'nombre': 'Prueba determinista',
            'url': 'http://127.0.0.1:8095/v1/chat/completions', 'modelo_api': 'modelo-prueba',
            'muestreo': {'temperature': 0}, 'agente_estado': True}))
        pila.enter_context(patch.object(marcas.requests, 'post', side_effect=post))
        pila.enter_context(patch.object(marcas.requests, 'get', side_effect=AssertionError('Red no simulada')))
        for modulo, nombre, funcion in [
            (jarvis, 'escanear', escanear),
            (jarvis, 'es_mi_consola', lambda *a: False),
            (jarvis, 'esperar_cancelacion', cancelar),
            (jarvis.time, 'sleep', pausa),
            (marcas, 'decidir_accion', decidir),
            (marcas, 'capturar_estado', observar),
            (marcas, 'nombre_ventana', lambda: estado['ventana']),
            (marcas, 'validar_destino', validar),
            (marcas, 'evidencia_archivos', lambda *a: evidencia('evidencia_archivos', *a)),
            (marcas, 'evidencia_copias', lambda *a: evidencia('evidencia_copias', *a)),
            (jarvis.memoria, 'buscar_recetas', lambda *a: []),
            (jarvis.memoria, 'texto_recetas', lambda *a: ''),
            (jarvis, 'control', lambda *a, **k: anotar('control', {'args': a, 'kwargs': k})),
            (jarvis, 'avisar', lambda *a, **k: anotar('aviso', {'args': a, 'kwargs': k})),
            (jarvis, 'guardar_exito', lambda *a, **k: anotar('guardar_exito', {'args': a, 'kwargs': k})),
        ]:
            pila.enter_context(patch.object(modulo, nombre, side_effect=funcion))
        for nombre in ('mover_suave', 'clic', 'seleccionar_todo', 'escribir', 'tecla'):
            pila.enter_context(patch.object(jarvis.acciones, nombre,
                side_effect=lambda *args, _nombre=nombre: aplicar(_nombre, *args)))
        capa = MagicMock()
        capa.activa.return_value = True
        capa.enviar.side_effect = lambda *a, **k: anotar('capa', {'args': a, 'kwargs': k})
        pila.enter_context(patch.object(jarvis, 'capa', capa))
        if version == 'sin-medicion':
            pila.enter_context(patch.object(rendimiento, 'llamar', side_effect=lambda n, f, *a, **k: f(*a, **k)))
            pila.enter_context(patch.object(rendimiento, 'actividad', side_effect=lambda *a: nullcontext()))
            pila.enter_context(patch.object(rendimiento, 'fase', side_effect=lambda *a: nullcontext()))
            pila.enter_context(patch.object(rendimiento, 'paso', side_effect=lambda *a, **k: nullcontext({'accion': None, 'peticiones': []})))
            pila.enter_context(patch.object(rendimiento, 'registrar_consulta'))
        jarvis._ejecutar_tarea(tarea.objetivo, (imagen, estado['ventana'], elementos),
            'determinista', tarea)
    if tarea.estado != 'completada' or guardado != 'prueba':
        raise AssertionError('La simulación no completó el contrato')
    return {'eventos': eventos, 'acciones': acciones, 'consultas': consultas,
        'guardado': guardado, 'tarea': {'estado': tarea.estado, 'contexto': tarea.contexto()}}


def comprobar(carpeta):
    carpeta.mkdir(parents=True, exist_ok=False)
    resultados = {}
    for version in ('head', 'actual', 'sin-medicion'):
        salida = carpeta / (version + '.json')
        proc = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
            '--version', version, '--salida', str(salida)], cwd=BASE, capture_output=True)
        (carpeta / (version + '.log')).open('xb').write(proc.stdout + proc.stderr)
        if proc.returncode:
            raise RuntimeError('Falló la simulación ' + version + ': ' + str(carpeta / (version + '.log')))
        resultados[version] = json.loads(salida.read_text(encoding='utf-8'))
    if not resultados['head'] == resultados['actual'] == resultados['sin-medicion']:
        raise AssertionError('Las secuencias de comportamiento difieren')
    asts = equivalencia_ast()
    if not all(asts.values()):
        raise AssertionError('Hay cambios AST ajenos a los envoltorios')
    actual = resultados['actual']
    resumen = {'identicos': True, 'comparaciones': ['HEAD frente a árbol actual',
        'árbol actual frente a mediciones desactivadas en el proceso aislado'],
        'ast_sin_envoltorios_igual_a_head': asts,
        'eventos': len(actual['eventos']), 'consultas': len(actual['consultas']),
        'acciones': actual['acciones'], 'tarea': actual['tarea'],
        'sha256_traza': hashlib.sha256(json.dumps(actual, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    with (carpeta / 'comparacion.json').open('x', encoding='utf-8') as archivo:
        json.dump(resumen, archivo, ensure_ascii=False, indent=2)
    return resumen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--version', choices=('head', 'actual', 'sin-medicion'))
    args = parser.parse_args()
    if args.version:
        resultado = simular(args.version, args.salida.with_suffix(''))
        with args.salida.open('x', encoding='utf-8') as archivo:
            json.dump(resultado, archivo, ensure_ascii=False, indent=2)
    else:
        resultado = comprobar(args.salida)
    print(json.dumps({'correcto': True, 'eventos': resultado.get('eventos') if not args.version else len(resultado['eventos'])}, ensure_ascii=True))


if __name__ == '__main__':
    main()
