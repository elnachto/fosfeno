"""Órdenes MAC/IP/VLAN con el agente actual: simulación, sin controlar la PC.

No añade recetas ni cambia los prompts. Conserva las ayudas de dominio existentes
y las declara. Las tablas/servidores del formulario son observaciones ficticias,
no instrucciones de navegación ni respuestas entregadas al modelo.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import secrets
import sys
import time

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import acciones
import agente
import evaluacion
import marcas
import memoria
import parametros
import precondiciones


def generar(semilla):
    r = random.Random(semilla)
    datos = []
    for n in range(2):
        vlan = r.randint(100, 350)
        otra = vlan+400
        octeto = r.randint(30, 190)
        ip = f'172.21.{octeto}.{r.randint(25, 190)}'
        mac = '02:'+':'.join(f'{r.randrange(256):02X}' for _ in range(5))
        servidor = f'svc-{r.randrange(65536):04x} | VLAN {vlan} | red 172.21.{octeto}.0/24'
        ajeno = f'svc-{r.randrange(65536):04x} | VLAN {otra} | red 172.22.{octeto}.0/24'
        opciones = [servidor, ajeno]; r.shuffle(opciones)
        objetivo = (f'Crea una reserva DHCP para MAC {mac}, con IP {ip} en la VLAN {vlan}. '
                    'Usa el servidor que atiende esa VLAN según los datos visibles. '
                    'Conserva las reservas existentes y no cambies la IP de ninguna interfaz.')
        datos.append({'id': f'reserva-{n+1}', 'modo': 'guardar', 'objetivo': objetivo,
                      'campos': [('mac', 'Edit', 'MAC Address', ''), ('ip', 'Edit', 'IP Address', ''),
                                 ('servidor', 'ComboBox', 'Servidor DHCP', ajeno)],
                      'opciones': {'servidor': opciones}, 'boton': 'Guardar reserva DHCP',
                      'esperado': {'mac': mac, 'ip': ip, 'servidor': servidor}, 'vlan': vlan})
    return datos


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--salida', type=Path, required=True)
    p.add_argument('--semilla-datos', type=int)
    a = p.parse_args()
    a.salida.mkdir(parents=True, exist_ok=True)
    semilla = a.semilla_datos if a.semilla_datos is not None else secrets.randbits(32)
    casos = generar(semilla)
    rs = memoria.leer_recetas()
    audit = {'archivos_md_activos': [p.name for p in Path(memoria.CONOCIMIENTO).glob('*.md')],
             'recetas_activas': len(rs), 'recetas_red': [
                 {'app': r.get('app'), 'fuente': r.get('fuente'), 'numero_pasos': len(r.get('pasos', []))}
                 for r in rs if any(k in json.dumps(r, ensure_ascii=False).lower()
                                    for k in ('mikrotik', 'winbox', 'routeros', 'dhcp', 'vlan'))],
             'prompt_agente_actual': agente.INSTRUCCION,
             'prompt_revisor_actual': precondiciones.INSTRUCCION,
             'nota': 'Hay ayudas manuales DHCP/redes. No se modifican ni eliminan en este ensayo.'}
    (a.salida/'ayudas-auditadas.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf8')
    manifiesto = {'tipo': 'Simulación de formulario y decisiones; no es WinBox ni usa visión/voz/input de PC',
                  'semilla_datos': semilla, 'semilla_modelo': 42, 'casos': casos,
                  'recetas_entregadas': False, 'notas_entregadas': False,
                  'ayudas_manuales_del_programa_conservadas': True,
                  'codigo_sha256': {n: hashlib.sha256((BASE/n).read_bytes()).hexdigest()
                                    for n in ('agente.py', 'parametros.py', 'precondiciones.py', 'evaluacion.py',
                                              'experimentos/evaluar_orden_red.py')}}
    (a.salida/'condiciones.json').write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding='utf8')
    resultados = []
    def guardar():
        (a.salida/'resultados.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding='utf8')
    for caso in casos:
        r = evaluacion.ejecutar_caso(caso, 'nemotron', 42, max_pasos=18)
        r['parametros_detectados_por_codigo'] = parametros.extraer(caso['objetivo'])
        resultados.append(r); guardar()
        print(json.dumps({k: r[k] for k in ('caso', 'correcto', 'motivo', 'valor_final', 'pasos', 'segundos')}, ensure_ascii=False), flush=True)
    marcas.PERFIL = dict(marcas.PERFIL, semilla=42, cache_prompt=False)
    base = casos[0]
    v = base['esperado']
    objetivo = (f'Tengo la MAC {v["mac"]}, quiero la IP {v["ip"]} y uso la VLAN {base["vlan"]}. '
                'Agrégale esa IP a la VLAN y deja el equipo con IP fija.')
    elementos = [('Button', 'Reservas DHCP para dispositivos', 20, 20, 320, 50),
                 ('Button', 'Direcciones IP de interfaces / gateway', 20, 60, 360, 90)]
    estado = {'ventana': 'Router ficticio: seleccionar operación', 'hwnd': 101,
              'foco': {'n': None, 'editable': False}, 'detalles': {},
              'texto_visible': 'Hay dos operaciones disponibles: reserva DHCP para un dispositivo o IP de una interfaz.'}
    inicio, nreq = time.monotonic(), len(marcas.PETICIONES)
    try:
        accion, crudo, intentos = agente.proponer(objetivo, elementos, estado, [], marcas.preguntar_json,
                                                 acciones.normalizar_tecla, referencias=None)
        r = {'caso': 'operacion-ambigua', 'objetivo': objetivo, 'accion': accion, 'crudo': crudo,
             'pidio_aclaracion': accion['tipo'] == 'preguntar', 'ejecutada': False, 'intentos': intentos}
    except (ValueError, marcas.ErrorRespuestaModelo) as error:
        r = {'caso': 'operacion-ambigua', 'error': str(error), 'pidio_aclaracion': False, 'ejecutada': False}
    r.update(segundos=round(time.monotonic()-inicio, 3), peticiones=copy.deepcopy(marcas.PETICIONES[nreq:]))
    resultados.append(r); guardar(); print(json.dumps({k: v for k, v in r.items() if k not in ('crudo', 'peticiones')}, ensure_ascii=False), flush=True)
    obs = {'ventana': 'Reserva DHCP ficticia', 'archivos_observados': [], 'texto_visible': '', 'controles': [
        {'id': 1, 'rol': 'Edit', 'nombre': 'MAC Address', 'valor': v['mac']},
        {'id': 2, 'rol': 'Edit', 'nombre': 'IP Address', 'valor': v['ip']},
        {'id': 3, 'rol': 'ComboBox', 'nombre': 'Servidor DHCP', 'valor': v['servidor']},
        {'id': 4, 'rol': 'Button', 'nombre': 'Guardar reserva DHCP'}]}
    for c, (nombre, valor) in enumerate([('IP', v['ip']), ('MAC', '02:00:00:00:00:FE'), ('Servidor DHCP', v['servidor'])]):
        obs['controles'].append({'id': 5+c, 'rol': 'DataItem', 'nombre': valor, 'tabla': 'Reservas existentes',
                                'fila': 0, 'columna': c, 'encabezado_columna': nombre})
    llamadas = []
    def consultar(*args):
        r = marcas.preguntar_json(*args); llamadas.append(r); return r
    inicio, nreq = time.monotonic(), len(marcas.PETICIONES)
    try:
        accion = precondiciones.revisar(base['objetivo'], {'tipo': 'clic', 'n': 4}, obs, consultar,
                                       None, agente.prompt_acotado)
        r = {'caso': 'ip-ocupada', 'observacion': obs, 'respuesta_revisor': llamadas,
             'accion': accion, 'pidio_aclaracion': bool(accion and accion['tipo'] == 'preguntar'), 'ejecutada': False}
    except (ValueError, marcas.ErrorRespuestaModelo) as error:
        r = {'caso': 'ip-ocupada', 'observacion': obs, 'respuesta_revisor': llamadas,
             'error': str(error), 'pidio_aclaracion': False, 'ejecutada': False}
    r.update(segundos=round(time.monotonic()-inicio, 3), peticiones=copy.deepcopy(marcas.PETICIONES[nreq:]))
    resultados.append(r); guardar(); print(json.dumps({k: v for k, v in r.items() if k not in ('peticiones', 'observacion')}, ensure_ascii=False), flush=True)
    resumen = {'reservas_simuladas_correctas': sum(r.get('correcto', False) for r in resultados[:2]),
               'reservas_simuladas_total': 2,
               'falsos_exitos_en_reservas': sum(r['falso_exito_aceptado'] for r in resultados[:2]),
               'operacion_ambigua_pregunto': resultados[2]['pidio_aclaracion'],
               'conflicto_pregunto': resultados[3]['pidio_aclaracion'],
               'conocimiento_manual_presente': True, 'recetas_nuevas_creadas': False,
               'router_real_modificado': False, 'semilla_datos': semilla}
    (a.salida/'resumen.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(resumen, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
