import copy
import unittest
from experimentos.mikrotik_simulado import validar_reserva, SERVIDORES, INICIAL


class SimuladorTests(unittest.TestCase):
    def test_exige_red_y_servidor_correctos_sin_modificar_las_reservas(self):
        inicial = copy.deepcopy(INICIAL)
        datos = {'mac': 'AA:BB:CC:DD:EE:02', 'ip': '192.168.40.9', 'vlan': '40', 'servidor': 'dhcp-a'}
        with self.assertRaisesRegex(ValueError, 'no corresponde'):
            validar_reserva(datos, SERVIDORES, inicial)
        correcta = validar_reserva({**datos, 'servidor': 'dhcp-b'}, SERVIDORES, inicial)
        self.assertEqual(correcta['servidor'], 'dhcp-b')
        self.assertEqual(inicial, INICIAL)

    def test_rechaza_ip_ocupada_y_direcciones_de_red(self):
        dato = {'mac': 'AA:BB:CC:DD:EE:02', 'ip': '192.168.40.55', 'vlan': '40', 'servidor': 'dhcp-b'}
        for ip in ('192.168.40.55', '192.168.40.0', '192.168.40.255', '192.168.20.9'):
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                validar_reserva({**dato, 'ip': ip}, SERVIDORES, INICIAL)


if __name__ == '__main__':
    unittest.main()
