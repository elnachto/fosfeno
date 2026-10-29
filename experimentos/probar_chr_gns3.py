"""Prueba funcional explícita del laboratorio local Fosfeno, no del agente GUI.

Solo acepta el proyecto preparado con la VM Fosfeno-CHR-GNS3 y su consola
loopback. Configura VLAN 40/DHCP en esa VM. No admite direcciones de routers.
Requiere Python 3.12 (telnetlib), requests y el laboratorio ya instalado.
"""
import argparse
import json
from pathlib import Path
import re
import telnetlib
import time

import requests


class Consola:
    def __init__(self, puerto):
        self.tn = telnetlib.Telnet('127.0.0.1', puerto, 5)

    def leer(self, segundos=.5):
        time.sleep(segundos)
        return re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', self.tn.read_very_eager()).decode('utf-8', errors='replace')

    def ejecutar(self, comando, espera=.5):
        self.tn.read_very_eager()
        self.tn.write(comando.encode('ascii') + b'\r')
        return self.leer(espera)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--laboratorio', type=Path, required=True)
    ap.add_argument('--salida', type=Path, required=True)
    args = ap.parse_args()
    p = args.laboratorio
    datos = json.loads((p / 'laboratorio.json').read_text())
    cred = json.loads((p / 'configuracion/credenciales-locales.json').read_text())
    s = requests.Session()
    s.auth = (cred['user'], cred['password'])
    base = 'http://127.0.0.1:3081/v2/projects/' + datos['project_id']
    r = s.get(base + '/nodes', timeout=10)
    r.raise_for_status()
    nodes = {n['node_id']: n for n in r.json()}
    router, pc = (nodes[datos['nodes'][k]] for k in ('router', 'cliente'))
    if (router['properties'].get('vmname') != 'Fosfeno-CHR-GNS3'
            or router.get('console_host') != '127.0.0.1'
            or pc['node_type'] != 'vpcs' or pc.get('console_host') != '127.0.0.1'):
        raise ValueError('No es el laboratorio aislado esperado')
    ros = Consola(router['console'])
    # No publicar credenciales ni la conversación de autenticación.
    inicio = ros.ejecutar('', .7)
    limite = time.monotonic() + 40
    while 'Login:' not in inicio and '] >' not in inicio and time.monotonic() < limite:
        inicio += ros.leer(.5)
    if 'Login:' in inicio:
        local = json.loads((p / 'configuracion/router-local.json').read_text())
        ros.tn.write((local['user'] + '+ct').encode('ascii') + b'\r')
        if b'Password:' not in ros.tn.read_until(b'Password:', 5):
            raise ValueError('No apareció la solicitud de clave de la consola local')
        ros.tn.write(local['password'].encode('ascii') + b'\r')
        if b'] >' not in ros.tn.read_until(b'] >', 10):
            raise ValueError('No se abrió la consola del laboratorio')
    identidad = ros.ejecutar(':put [/system identity get name]')
    if '\nFOSFENO-GNS3-LAB' not in identidad.replace('\r', ''):
        raise ValueError('La identidad de RouterOS no coincide; no modificar nada')
    registros = []

    def comando(c):
        salida = ros.ejecutar(c, .45)
        registros.append({'comando': c, 'salida': salida})
        if re.search(r'\b(failure:|syntax error|expected end of command|bad command name)', salida, re.I):
            raise RuntimeError('RouterOS rechazó un comando; ver salida local')
        return salida

    # Idempotente sobre objetos con nombres exclusivos de este laboratorio.
    configuracion = [
        '/interface bridge add name=br-fosfeno vlan-filtering=yes',
        '/interface bridge port add bridge=br-fosfeno interface=ether2 pvid=40',
        '/interface bridge vlan add bridge=br-fosfeno tagged=br-fosfeno untagged=ether2 vlan-ids=40',
        '/interface vlan add name=vlan40 interface=br-fosfeno vlan-id=40',
        '/ip address add address=192.168.40.1/24 interface=vlan40',
        '/ip pool add name=pool40 ranges=192.168.40.100-192.168.40.120',
        '/ip dhcp-server network add address=192.168.40.0/24 gateway=192.168.40.1',
        '/ip dhcp-server add name=dhcp40 interface=vlan40 address-pool=pool40 lease-time=10m disabled=no',
    ]
    cuenta = comando(':put [/interface bridge print count-only where name="br-fosfeno"]')
    if '\n0\n' in cuenta.replace('\r', ''):
        for c in configuracion:
            comando(c)
    cliente = Consola(pc['console'])
    observaciones = []

    def pc_comando(c, espera=1):
        out = cliente.ejecutar(c, espera)
        observaciones.append({'comando': c, 'salida': out})
        return out

    pruebas = []
    def comprobar(nombre, condicion):
        pruebas.append({'prueba': nombre, 'ok': bool(condicion)})
        print(nombre, 'OK' if condicion else 'FALLO', flush=True)

    info = pc_comando('show ip')
    limite = time.monotonic() + 15
    mac_match = re.search(r'MAC\s*:\s*([0-9a-f:]{17})', info, re.I)
    while not mac_match and time.monotonic() < limite:
        info += cliente.leer(.5)
        mac_match = re.search(r'MAC\s*:\s*([0-9a-f:]{17})', info, re.I)
    if not mac_match:
        raise ValueError('VPCS no entregó su MAC observada; no crear una reserva')
    mac = mac_match.group(1).upper()
    previa = comando(':put [/ip dhcp-server lease print count-only where comment="FOSFENO-RESERVA"]')
    reserva_previa = '\n0\n' not in previa.replace('\r', '')
    pc_comando('ip dhcp', 8)
    ip_dinamica = pc_comando('show ip')
    patron = r'IP/MASK\s*:\s*192\.168\.40\.9/24' if reserva_previa else r'IP/MASK\s*:\s*192\.168\.40\.1(?:0\d|1\d|20)/24'
    comprobar('dhcp_reserva_persistente' if reserva_previa else 'dhcp_dinamico_vlan40', bool(re.search(patron, ip_dinamica)))
    ping = pc_comando('ping 192.168.40.1 -c 3', 5)
    comprobar('ping_gateway_dinamico', ping.count('icmp_seq=') >= 3 and 'timeout' not in ping.lower())
    lease = comando('/ip dhcp-server lease print detail without-paging')
    comprobar('lease_en_router', mac in lease and 'status=bound' in lease)
    cuenta = comando(':put [/ip dhcp-server lease print count-only where comment="FOSFENO-RESERVA"]')
    if '\n0\n' in cuenta.replace('\r', ''):
        comando('/ip dhcp-server lease add address=192.168.40.9 mac-address=' + mac + ' server=dhcp40 comment=FOSFENO-RESERVA')
    pc_comando('ip dhcp -x', 1)
    pc_comando('ip dhcp', 8)
    fija = pc_comando('show ip')
    comprobar('reserva_estatica_recibida', bool(re.search(r'IP/MASK\s*:\s*192\.168\.40\.9/24', fija)))
    ping = pc_comando('ping 192.168.40.1 -c 3', 5)
    comprobar('ping_gateway_estatico', ping.count('icmp_seq=') >= 3 and 'timeout' not in ping.lower())
    leases = comando('/ip dhcp-server lease print detail without-paging')
    comprobar('reserva_bound_en_router', '192.168.40.9' in leases and mac in leases and 'FOSFENO-RESERVA' in leases and 'status=bound' in leases)
    vlan = comando('/interface bridge vlan print detail without-paging')
    comprobar('vlan40_cpu_y_acceso', 'vlan-ids=40' in vlan and 'br-fosfeno' in vlan and 'ether2' in vlan)
    pc_comando('save')
    resultado = {'tipo': 'Prueba funcional RouterOS por consola de laboratorio; no agente GUI',
                 'vm': 'Fosfeno-CHR-GNS3', 'pruebas': pruebas,
                 'router': registros, 'cliente': observaciones}
    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / 'routeros-funcional.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    ros.tn.close()
    cliente.tn.close()
    if not all(p['ok'] for p in pruebas):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
