"""Interfaz local ficticia de reservas DHCP. No conecta equipos de red.

Las únicas escrituras de configuración provienen de los controles visibles.
La API de localhost solo lee estado o delimita la grabación de una demostración.
"""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import sys
import threading
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView)

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import parametros

SERVIDORES = [
    {'nombre': 'dhcp-a', 'vlan': 20, 'red': '192.168.20.0/24'},
    {'nombre': 'dhcp-b', 'vlan': 40, 'red': '192.168.40.0/24'},
]
INICIAL = [
    {'mac': 'AA:BB:CC:DD:EE:F0', 'ip': '192.168.40.55', 'vlan': 40, 'servidor': 'dhcp-b'},
]
ESCENARIOS = {
    'A — Enseñanza': {'id': 'demo', 'orden': ['mac', 'ip', 'vlan'], 'alternativo': False},
    'B — Sin receta': {'id': 'sin-receta', 'orden': ['vlan', 'ip', 'mac'], 'alternativo': True},
    'C — Con receta': {'id': 'con-receta', 'orden': ['vlan', 'ip', 'mac'], 'alternativo': True},
    'D — Dirección ocupada': {'id': 'ocupada', 'orden': ['ip', 'mac', 'vlan'], 'alternativo': True},
    'E — Servidor ambiguo': {'id': 'ambiguo', 'orden': ['mac', 'vlan', 'ip'], 'alternativo': True,
        'servidores': [{'nombre': 'dhcp-c', 'vlan': 60, 'red': '192.168.60.0/24'},
                       {'nombre': 'dhcp-d', 'vlan': 60, 'red': '192.168.60.0/24'}]},
}


def validar_reserva(dato, servidores, reservas):
    mac, ip = parametros.validar('mac', dato['mac']), parametros.validar('ip', dato['ip'])
    if '/' in ip:
        raise ValueError('La reserva requiere una dirección de dispositivo sin prefijo')
    vlan = int(parametros.validar('vlan', dato['vlan']))
    servidor = next((s for s in servidores if s['nombre'] == dato['servidor']), None)
    if servidor is None:
        raise ValueError('Selecciona un servidor DHCP')
    if servidor['vlan'] != vlan:
        raise ValueError('El servidor seleccionado no corresponde a la VLAN indicada')
    red = ipaddress.ip_network(servidor['red'])
    direccion = ipaddress.ip_address(ip)
    if direccion not in red or direccion in (red.network_address, red.broadcast_address):
        raise ValueError('La IP no es una dirección de dispositivo de la red del servidor')
    if any(r['ip'] == ip and r['mac'] != mac for r in reservas):
        raise ValueError('La IP ya está reservada a otra MAC; no se ha modificado nada')
    return {'mac': mac, 'ip': ip, 'vlan': vlan, 'servidor': servidor['nombre']}


class Laboratorio(QWidget):
    def __init__(self, salida):
        super().__init__()
        self.salida = salida
        self.bloqueo = threading.RLock()
        self.grabando, self.demostracion, self.eventos = False, [], []
        self.snapshot = {}
        self.setWindowTitle('Laboratorio MikroTik — Fosfeno')
        self.resize(940, 740)
        self.setStyleSheet('QWidget {font-size: 14px;} QLineEdit {padding: 5px;} QPushButton {padding: 7px;} QGroupBox {font-weight:bold;}')
        layout = QVBoxLayout(self)
        titulo = QLabel('Laboratorio MikroTik · Reservas DHCP')
        titulo.setStyleSheet('font-size:24px; font-weight:bold; color:#26435b')
        layout.addWidget(titulo)
        layout.addWidget(QLabel('SIMULACIÓN LOCAL · Datos ficticios · Ningún router conectado'))
        linea = QHBoxLayout()
        linea.addWidget(QLabel('Escenario de prueba:'))
        self.escenario = QComboBox()
        self.escenario.setAccessibleName('Escenario de prueba')
        self.escenario.addItems(ESCENARIOS)
        linea.addWidget(self.escenario, 1)
        layout.addLayout(linea)
        self.cuerpo = QVBoxLayout()
        layout.addLayout(self.cuerpo)
        self.escenario.currentTextChanged.connect(self.cambiar)
        self.cambiar(self.escenario.currentText())

    def evento(self, tipo, **dato):
        with self.bloqueo:
            registro = {'n': len(self.eventos) + 1, 'tipo': tipo, 'caso': self.caso['id'], **dato}
            self.eventos.append(registro)
            if self.grabando:
                self.demostracion.append(registro)
            self.persistir()

    def persistir(self):
        self.salida.mkdir(parents=True, exist_ok=True)
        dato = {'estado': self.snapshot, 'eventos': self.eventos, 'demostracion': self.demostracion,
                'grabando': self.grabando}
        (self.salida / 'estado-simulador.json').write_text(json.dumps(dato, ensure_ascii=False, indent=2), encoding='utf-8')

    def observar(self):
        with self.bloqueo:
            self.snapshot = {'caso': self.caso['id'], 'servidores': self.servidores, 'reservas': self.reservas,
                             'campos': {k: w.text() for k, w in self.campos.items()},
                             'servidor_elegido': self.elegido, 'mensaje': self.mensaje.text(),
                             'intentos_aplicar': self.intentos, 'guardados': self.guardados}
            self.persistir()

    def cambiar(self, nombre):
        while self.cuerpo.count():
            item = self.cuerpo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.caso = ESCENARIOS[nombre]
        self.servidores = copy.deepcopy(self.caso.get('servidores', SERVIDORES))
        self.reservas = copy.deepcopy(INICIAL)
        self.elegido, self.intentos, self.guardados = '', 0, 0
        bloque = QGroupBox('Nueva reserva estática para un dispositivo')
        form = QFormLayout(bloque)
        self.campos = {}
        self.nombres = {'mac': 'MAC Address', 'ip': 'Address', 'vlan': 'VLAN'} if not self.caso['alternativo'] else {
            'mac': 'MAC del dispositivo', 'ip': 'Dirección a reservar', 'vlan': 'ID de VLAN'}
        for clave in self.caso['orden']:
            campo = QLineEdit()
            campo.setAccessibleName(self.nombres[clave])
            campo.editingFinished.connect(lambda k=clave: self.fin_escritura(k))
            campo.textChanged.connect(lambda _: self.observar())
            self.campos[clave] = campo
            form.addRow(self.nombres[clave] + ':', campo)
        servidores = QGroupBox('Servidores DHCP disponibles y su red')
        caja = QVBoxLayout(servidores)
        self.grupo = QButtonGroup(self)
        orden = self.servidores if not self.caso['alternativo'] else list(reversed(self.servidores))
        for s in orden:
            nombre_opcion = s['nombre'] + ' — VLAN ' + str(s['vlan']) + ' — ' + s['red']
            boton = QRadioButton(nombre_opcion)
            boton.setAccessibleName(nombre_opcion)
            boton.clicked.connect(lambda _, dato=s, n=nombre_opcion: self.servidor_cambiado(dato['nombre'], n))
            self.grupo.addButton(boton)
            caja.addWidget(boton)
        form.addRow(servidores)
        boton = QPushButton('Aplicar reserva' if not self.caso['alternativo'] else 'Guardar reserva DHCP')
        boton.clicked.connect(self.aplicar)
        self.boton_aplicar = boton
        form.addRow(boton)
        self.cuerpo.addWidget(bloque)
        self.mensaje = QLabel('Sin cambios. Revisa las reservas existentes antes de aplicar.')
        self.mensaje.setWordWrap(True)
        self.cuerpo.addWidget(self.mensaje)
        self.cuerpo.addWidget(QLabel('Reservas existentes (IP, MAC, VLAN, servidor):'))
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(['IP', 'MAC', 'VLAN', 'Servidor DHCP'])
        self.tabla.setAccessibleName('Reservas existentes')
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.setMinimumHeight(180)
        self.cuerpo.addWidget(self.tabla)
        self.refrescar_tabla()
        self.observar()
        self.evento('escenario', nombre=nombre)

    def refrescar_tabla(self):
        self.tabla.setRowCount(len(self.reservas))
        for i, r in enumerate(self.reservas):
            for j, clave in enumerate(('ip', 'mac', 'vlan', 'servidor')):
                self.tabla.setItem(i, j, QTableWidgetItem(str(r[clave])))

    def fin_escritura(self, clave):
        valor = self.campos[clave].text()
        if valor:
            self.evento('escritura', clave=clave, campo=self.nombres[clave], valor=valor)

    def servidor_cambiado(self, nombre, etiqueta):
        self.elegido = nombre
        self.evento('seleccion_servidor', nombre=nombre, etiqueta=etiqueta)
        self.observar()

    def aplicar(self):
        self.intentos += 1
        dato = {k: w.text() for k, w in self.campos.items()}
        dato['servidor'] = self.elegido
        self.evento('aplicar', valores=dato, boton=self.boton_aplicar.text())
        try:
            reserva = validar_reserva(dato, self.servidores, self.reservas)
            self.reservas = [r for r in self.reservas if r['mac'] != reserva['mac']] + [reserva]
            self.guardados += 1
            self.mensaje.setText('Reserva guardada: ' + json.dumps(reserva, ensure_ascii=False))
            self.refrescar_tabla()
        except (ValueError, KeyError) as error:
            self.mensaje.setText('No se guardó: ' + str(error))
        self.observar()


def servidor(app, puerto):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            with app.bloqueo:
                dato = {'estado': app.snapshot, 'eventos': app.eventos, 'demostracion': app.demostracion, 'grabando': app.grabando}
                body = json.dumps(dato, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path not in ('/grabacion/iniciar', '/grabacion/terminar'):
                self.send_error(404)
                return
            with app.bloqueo:
                if self.path.endswith('iniciar'):
                    app.demostracion.clear()
                    app.grabando = True
                else:
                    app.grabando = False
                app.persistir()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')

        def log_message(self, *args):
            pass
    ThreadingHTTPServer(('127.0.0.1', puerto), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--puerto', type=int, default=8108)
    args = parser.parse_args()
    qt = QApplication(sys.argv[:1])
    ventana = Laboratorio(args.salida)
    threading.Thread(target=servidor, args=(ventana, args.puerto), daemon=True).start()
    ventana.show()
    print('Simulador local listo. Ningún equipo de red conectado.', flush=True)
    sys.exit(qt.exec())


if __name__ == '__main__':
    main()
