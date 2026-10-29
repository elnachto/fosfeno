import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import memoria
import parametros

OBJETIVO = 'Reserva por DHCP la IP 192.168.20.83 para MAC AA:BB:CC:DD:EE:01 en VLAN 20'
PASOS = ['clic en «Leases»', 'escribí «AA:BB:CC:DD:EE:01» en «MAC Address»',
         'escribí «192.168.20.83» en «Address»', 'escribí «20» en «VLAN»', 'clic en «Aplicar»']


class ParametrosTests(unittest.TestCase):
    def test_punto_final_no_forma_parte_del_valor_vlan(self):
        self.assertEqual(parametros.extraer('Reserva DHCP, VLAN 40. Comprueba el resultado.')['valores']['vlan'], '40')
        p = parametros.crear_plantilla(OBJETIVO + '.', PASOS)
        r = parametros.instanciar(p, 'Reserva DHCP IP 192.168.40.9 MAC AA:BB:CC:DD:EE:02 VLAN 40.')
        self.assertIn('escribí «40» en «VLAN»', r['pasos'])
        self.assertNotIn('escribí «40.» en «VLAN»', r['pasos'])

    def test_vlan_sin_espacio_no_conserva_valor_viejo_en_el_objetivo(self):
        p = parametros.crear_plantilla(OBJETIVO.replace('VLAN 20', 'VLAN20'), PASOS)
        r = parametros.instanciar(p, 'Reserva por DHCP IP 192.168.40.9 MAC AA:BB:CC:DD:EE:02 VLAN40')
        self.assertTrue(r['lista'])
        self.assertIn('VLAN40', r['objetivo'])
        self.assertNotIn('VLAN20', r['objetivo'])

    def test_extrae_y_normaliza_sin_inventar_topologia(self):
        datos = parametros.extraer('MAC aa-bb-cc-dd-ee-02 IP 192.168.40.9 VLAN 40')
        self.assertEqual(datos['valores'], {'mac': 'AA:BB:CC:DD:EE:02', 'ip': '192.168.40.9', 'vlan': '40'})
        self.assertNotIn('servidor_dhcp', datos['valores'])

    def test_rechaza_ip_y_vlan_invalidas(self):
        self.assertTrue(parametros.extraer('IP 192.168.300.1 VLAN 4095')['errores'])
        for tipo, valor in [('mac', 'AA:ZZ'), ('ip', '192.168.1.1/60'), ('vlan', '0')]:
            with self.assertRaises(ValueError):
                parametros.validar(tipo, valor)

    def test_varias_ips_son_ambiguas(self):
        datos = parametros.extraer('IP 192.168.1.1 y 192.168.1.2')
        self.assertNotIn('ip', datos['valores'])
        self.assertEqual(len(datos['ambiguos']['ip']), 2)

    def test_demostracion_se_reutiliza_con_otras_tres_variables(self):
        plantilla = parametros.crear_plantilla(OBJETIVO, PASOS)
        resultado = parametros.instanciar(plantilla, 'Reserva por DHCP IP 192.168.40.9 MAC aa-bb-cc-dd-ee-02 VLAN 40')
        self.assertTrue(resultado['lista'])
        texto = json.dumps(resultado, ensure_ascii=False)
        self.assertIn('192.168.40.9', texto)
        self.assertIn('AA:BB:CC:DD:EE:02', texto)
        self.assertNotIn('192.168.20.83', texto)
        self.assertNotIn('AA:BB:CC:DD:EE:01', texto)
        self.assertEqual(resultado['pasos'][0], PASOS[0])

    def test_no_parametriza_clics_ni_valores_no_demostrados(self):
        self.assertIsNone(parametros.crear_plantilla(OBJETIVO, ['clic en «192.168.20.83»']))

    def test_no_sustituye_subcadenas_de_otras_ips(self):
        p = parametros.crear_plantilla(OBJETIVO, PASOS + ['escribí «192.168.20.830»'])
        self.assertEqual(p['pasos'][-1], 'escribí «192.168.20.830»')

    def test_faltantes_y_ambiguedad_no_reusan_valores_anteriores(self):
        p = parametros.crear_plantilla(OBJETIVO, PASOS)
        r = parametros.instanciar(p, 'Reserva por DHCP la IP 192.168.40.9 en VLAN 40')
        self.assertFalse(r['lista'])
        self.assertIn('mac', r['faltantes'])
        self.assertNotIn('pasos', r)

    def test_no_confunde_reserva_dhcp_e_ip_de_interfaz(self):
        p = parametros.crear_plantilla(OBJETIVO, PASOS)
        r = parametros.instanciar(p, 'Asigna IP 192.168.40.9 a la interfaz VLAN 40, MAC AA:BB:CC:DD:EE:02')
        self.assertFalse(r['lista'])
        self.assertIn('reserva DHCP', r['pregunta'])

    def test_receta_persistida_y_legacy_se_instancian_sin_reescribir_original(self):
        with tempfile.TemporaryDirectory() as carpeta, patch.object(memoria, 'CONOCIMIENTO', carpeta), \
                patch.object(memoria, 'RECETAS', str(Path(carpeta) / 'recetas.jsonl')):
            memoria.guardar_receta('winbox', OBJETIVO, PASOS, 'demostracion')
            contenido = Path(memoria.RECETAS).read_text(encoding='utf-8')
            r = memoria.buscar_recetas('Reserva por DHCP IP 192.168.40.9 MAC AA:BB:CC:DD:EE:02 VLAN 40', 'winbox')
            texto = memoria.texto_recetas(r, 'Reserva por DHCP IP 192.168.40.9 MAC AA:BB:CC:DD:EE:02 VLAN 40')
            self.assertIn('192.168.40.9', texto)
            self.assertNotIn('192.168.20.83', texto)
            self.assertEqual(Path(memoria.RECETAS).read_text(encoding='utf-8'), contenido)


if __name__ == '__main__':
    unittest.main()
