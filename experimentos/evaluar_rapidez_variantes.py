import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

import requests

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import servidores_lfm3
import motor_ia


VARIANTES = {
    'E1': {'presupuesto': 0, 'observacion_primero': False, 'prefill': False, 'gbnf': False},
    'E2': {'presupuesto': 0, 'observacion_primero': True, 'prefill': False, 'gbnf': False},
    'E3': {'presupuesto': None, 'observacion_primero': True, 'prefill': True, 'gbnf': False},
    'E4-64': {'presupuesto': 64, 'observacion_primero': True, 'prefill': False, 'gbnf': False},
    'E4-128': {'presupuesto': 128, 'observacion_primero': True, 'prefill': False, 'gbnf': False},
    'E5': {'presupuesto': None, 'observacion_primero': True, 'prefill': False, 'gbnf': True},
}


def esquema_observacion(esquema):
    orden = ['evidencia', 'objetivo_pendiente', 'accion', 'n', 'texto', 'reemplazar']
    return {**esquema, 'properties': {k: esquema['properties'][k] for k in orden}, 'required': orden}


def resumen(carpeta):
    resultados = json.loads((carpeta / 'resultados.json').read_text(encoding='utf-8'))
    peticiones = [p for r in resultados for p in r['peticiones']]
    return {
        'aciertos': sum(r['correcto'] for r in resultados), 'total': len(resultados),
        'por_semilla': {str(s): {'aciertos': sum(r['correcto'] for r in resultados if r['semilla'] == s),
                                'total': sum(r['semilla'] == s for r in resultados)}
                        for s in sorted({r['semilla'] for r in resultados})},
        'pasos_tarea': statistics.mean(r['pasos'] for r in resultados),
        'tokens_consulta': sum(p['uso']['completion_tokens'] for p in peticiones) / len(peticiones),
        'segundos_tarea': statistics.mean(r['segundos'] for r in resultados),
        'falsos_exitos': sum(r['falso_exito_aceptado'] for r in resultados),
        'truncamientos': sum(p['fin'] == 'length' for p in peticiones),
        'fallos': [{'caso': r['caso'], 'semilla': r['semilla'], 'motivo': r['motivo'],
                    'objetivo_logrado': r['objetivo_logrado']} for r in resultados if not r['correcto']],
    }


def fuentes():
    return {nombre: hashlib.sha256((BASE / nombre).read_bytes()).hexdigest() for nombre in (
        'agente.py', 'marcas.py', 'evaluacion.py', 'rendimiento.py', 'salida_json.py',
        'motor_ia.py', 'precondiciones.py', 'experimentos/evaluar_rapidez_variantes.py')}


def iniciar_servidor(config, carpeta):
    consulta = ('Get-CimInstance Win32_Process -Filter "name = \'llama-server.exe\'" | '
                'Where-Object { $_.CommandLine -match \'--port 8095(?: |$)\' } | '
                'Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json')
    activo = subprocess.check_output(['powershell', '-NoProfile', '-Command', consulta], text=True)
    exe = servidores_lfm3.RUNTIME / 'llama-server.exe'
    if activo.strip():
        proceso = json.loads(activo)
        if (not isinstance(proceso, dict) or Path(proceso['ExecutablePath']).resolve() != exe.resolve()
                or '--alias fosfeno-nemotron' not in proceso['CommandLine']):
            raise RuntimeError('El puerto 8095 pertenece a otro proceso; no se detuvo')
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        'Stop-Process -Id ' + str(proceso['ProcessId'])], check=True)
        time.sleep(.5)
    servidor = next(s for s in servidores_lfm3.SERVIDORES if s['puerto'] == 8095)
    comando = [str(exe), '-m', str(servidores_lfm3.MODELOS / servidor['archivo']),
               '--alias', servidor['alias'], '-ngl', '99', '-c', '16384', '-np', '1',
               '-fa', 'on', '--jinja', '--host', '127.0.0.1', '--port', '8095',
               '--temp', '0.1', '--top-p', '1', '--top-k', '50', '--min-p', '0',
               '--repeat-penalty', '1.1', '--no-reasoning-preserve',
               '--mmproj', str(servidores_lfm3.MODELOS / servidor['vision'])]
    if config['presupuesto'] is not None:
        comando.extend(['--reasoning-budget', str(config['presupuesto'])])
    if config['prefill']:
        original = json.loads((carpeta.parent / 'plantilla-original.json').read_text(encoding='utf-8'))
        marcador = "{{- '<|turn>model\\n' -}}"
        if original.count(marcador) != 1:
            raise RuntimeError('La plantilla original no contiene un único turno de generación esperado')
        plantilla = original.replace(marcador, marcador +
            "\n        {%- if not enable_thinking -%}\n"
            "            {{- '<|channel>thought\\n<channel|>' -}}\n        {%- endif -%}", 1)
        ruta = carpeta / 'nemotron-pensamiento-vacio.jinja'
        ruta.write_text(plantilla, encoding='utf-8')
        comando.extend(['--chat-template-file', str(ruta)])
    with (carpeta / 'servidor.log').open('ab') as log:
        proceso = subprocess.Popen(comando, cwd=servidores_lfm3.RUNTIME,
            env=dict(os.environ, CUDA_VISIBLE_DEVICES='0'), stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    (carpeta / 'arranque.json').write_text(json.dumps({'pid': proceso.pid, 'comando': comando}, indent=2), encoding='utf-8')
    inicio = time.monotonic()
    while time.monotonic() - inicio < 120:
        if proceso.poll() is not None:
            raise RuntimeError('El servidor terminó; consulta ' + str(carpeta / 'servidor.log'))
        try:
            respuesta = requests.get('http://127.0.0.1:8095/health', timeout=1)
            if respuesta.ok:
                props = requests.get('http://127.0.0.1:8095/props', timeout=5).json()
                (carpeta / 'props.json').write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding='utf-8')
                if not config['prefill']:
                    (carpeta.parent / 'plantilla-original.json').write_text(json.dumps(props['chat_template']), encoding='utf-8')
                return
        except requests.RequestException:
            pass
        time.sleep(.5)
    raise TimeoutError('El servidor no quedó listo')


def ejecutar_hijo(args):
    config = VARIANTES[args.variante]
    os.environ['FOSFENO_GBNF_EXPERIMENTAL'] = '1' if config['gbnf'] else '0'
    os.environ['FOSFENO_TIEMPOS_CRUDO'] = '0'
    os.environ['FOSFENO_TIEMPOS_LOG'] = str(args.salida / 'pasos.jsonl')
    motor_ia.PERFILES["nemotron"]["presupuesto_razonamiento"] = None
    motor_ia.PERFILES["nemotron"]["observacion_primero"] = False
    import agente
    import evaluacion
    if config['observacion_primero']:
        original = agente.esquema
        agente.esquema = lambda total: esquema_observacion(original(total))
    post = requests.post
    def registrar(url, **kwargs):
        respuesta = post(url, **kwargs)
        if url.endswith('/v1/chat/completions') and respuesta.ok:
            payload = kwargs.get('json', {})
            esquema = payload.get('response_format', {}).get('json_schema', {}).get('schema', {})
            dato = {'respuesta': respuesta.json(), 'formato': 'GBNF' if 'grammar' in payload else 'json_schema',
                    'properties': list(esquema.get('properties', {})), 'required': esquema.get('required', []),
                    'hash_mensajes': hashlib.sha256(json.dumps(payload.get('messages'), ensure_ascii=False).encode()).hexdigest()}
            with (args.salida / 'respuestas.jsonl').open('a', encoding='utf-8') as archivo:
                archivo.write(json.dumps(dato, ensure_ascii=False) + '\n')
        return respuesta
    requests.post = registrar
    (args.salida / 'variante.json').write_text(json.dumps({
        'variante': args.variante, 'config': config, 'semillas': args.semillas,
        'fuentes': fuentes(), 'prompt_modificado': False,
        'esquema_accion': agente.esquema(3)}, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.argv = ['evaluacion.py', '--motores', 'nemotron', '--semillas', args.semillas,
                '--salida', str(args.salida)]
    evaluacion.main()


def ejecutar_variante(nombre, semillas, carpeta):
    carpeta.mkdir(parents=True, exist_ok=True)
    iniciar_servidor(VARIANTES[nombre], carpeta)
    with (carpeta / 'consola.log').open('wb') as log:
        subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--hijo',
                        '--variante', nombre, '--semillas', semillas, '--salida', str(carpeta)],
                       cwd=BASE, stdout=log, stderr=subprocess.STDOUT, check=True)
    dato = resumen(carpeta)
    (carpeta / 'metricas.json').write_text(json.dumps(dato, ensure_ascii=False, indent=2), encoding='utf-8')
    return dato


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hijo', action='store_true')
    parser.add_argument('--variante', choices=tuple(VARIANTES))
    parser.add_argument('--semillas', default='42,99')
    parser.add_argument('--salida', type=Path, default=BASE / 'salidas' / 'rapidez' / 'aislamiento')
    args = parser.parse_args()
    args.salida = args.salida.resolve()
    if args.hijo:
        ejecutar_hijo(args)
        return
    args.salida.mkdir(parents=True, exist_ok=True)
    if any((p / 'resultados.json').exists() for p in args.salida.iterdir() if p.is_dir()):
        raise FileExistsError('Usa una carpeta --salida nueva para conservar las mediciones anteriores')
    resultados = {}
    confirmaciones = {}
    estado = args.salida / 'estado.json'
    try:
        for nombre in VARIANTES:
            estado.write_text(json.dumps({'activa': nombre, 'resultados': resultados}, indent=2), encoding='utf-8')
            resultados[nombre] = ejecutar_variante(nombre, '42,99', args.salida / nombre)
            print(nombre, json.dumps(resultados[nombre], ensure_ascii=True), flush=True)
        for nombre, dato in resultados.items():
            if dato['aciertos'] == 16 and dato['segundos_tarea'] < 11:
                estado.write_text(json.dumps({'activa': nombre + '-7', 'resultados': resultados,
                                             'confirmaciones': confirmaciones}, indent=2), encoding='utf-8')
                confirmaciones[nombre] = ejecutar_variante(nombre, '7', args.salida / (nombre + '-7'))
                print(nombre + '-7', json.dumps(confirmaciones[nombre], ensure_ascii=True), flush=True)
        estado.write_text(json.dumps({'activa': None, 'resultados': resultados,
                                     'confirmaciones': confirmaciones}, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        restauracion = args.salida / 'servidor-restaurado'
        restauracion.mkdir(exist_ok=True)
        iniciar_servidor({'presupuesto': motor_ia.PERFILES['nemotron'].get('presupuesto_razonamiento'),
                          'prefill': False}, restauracion)


if __name__ == '__main__':
    main()
