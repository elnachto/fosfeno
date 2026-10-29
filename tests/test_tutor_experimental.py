import tempfile
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tutor_experimental as tutor


class TutorTests(unittest.TestCase):
    def test_excluye_codigo_oculto_de_html(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'ayuda.htm'
            p.write_text('<p>IP Configuration</p><script>instrucción oculta</script><style>color:red</style><p>Static</p>', encoding='utf-8')
            self.assertEqual(tutor.texto_manual(p), 'IP Configuration\nStatic')

    def test_recupera_el_fragmento_relevante_y_diversifica(self):
        datos = [{'archivo': f'{i}.htm', 'texto': texto, 'fragmento': 0, 'sha256': 'x'}
                 for i, texto in enumerate(['Wireless SSID settings', 'Desktop IP Configuration Static subnet mask', 'Device IP Configuration menu'])]
        r = tutor.recuperar(datos, ['IP Configuration static subnet mask'], 2)
        self.assertEqual(r[0]['archivo'], '1.htm')
        self.assertEqual(len(r), 2)

    def test_rechaza_cita_inventada(self):
        with self.assertRaises(ValueError):
            tutor.validar_fuentes({'pasos': [{'fuentes': ['F99']}], 'estado': 'PROPUESTA_NO_PROBADA'}, [{'id': 'F1'}])

    def test_no_acepta_que_generar_texto_sea_una_prueba(self):
        with self.assertRaises(ValueError):
            tutor.validar_fuentes({'pasos': [], 'estado': 'VERIFICADO'}, [])

    def test_rechaza_cita_en_prosa_fuera_del_array(self):
        with self.assertRaises(ValueError):
            tutor.validar_fuentes({'conceptos': ['Según F13 funciona'], 'pasos': [], 'estado': 'PROPUESTA_NO_PROBADA'}, [{'id': 'F1'}])

    def test_pasajes_largos_se_acotan(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'largo.txt'
            p.write_text('x' * 5100, encoding='utf-8')
            r = tutor.indexar(d)
            self.assertTrue(all(len(p['texto']) <= 1400 for p in r))
            self.assertEqual(''.join(p['texto'] for p in r), 'x' * 5100)

    def test_seleccion_no_puede_salir_del_catalogo(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                tutor.indexar(d, ['../otro.txt'])

    def resultado(self, configuracion=None):
        return {'aplicacion': 'Prueba', 'pregunta': 'Conserva los equipos', 'observaciones': '',
                'fuentes': [], 'leccion': {'pasos': [], 'estado': 'PROPUESTA_NO_PROBADA',
                                          'configuracion': configuracion or []}}

    def test_bloquea_equipo_nuevo_sin_consultar_modelo(self):
        r = self.resultado([{'equipo': 'Router0'}])
        def no_consultar(*args):
            self.fail('Un bloqueo determinista no debe consultar el modelo')
        revision = tutor.revisar_leccion(r, no_consultar, {'equipos_permitidos': ['PC0', 'PC1']})
        self.assertEqual(revision['estado'], 'BLOQUEADA')
        self.assertIn('Router0', revision['errores_reglas'][0])

    def test_detecta_cambio_de_equipo_fijo_y_duplicado(self):
        leccion = self.resultado([{'equipo': 'PC0', 'ipv4': '10.0.0.2', 'gateway': ''},
                                  {'equipo': 'PC0', 'ipv4': '10.0.0.1', 'gateway': ''}])['leccion']
        errores = tutor.comprobar_restricciones(leccion, {'configuracion_fija': {'PC0': {'ipv4': '10.0.0.1', 'gateway': '0.0.0.0'}}})
        self.assertEqual(len(errores), 2)

    def test_bloquea_critica_y_datos_imprescindibles_ausentes(self):
        for critica in ({'problemas': [{'gravedad': 'critica', 'detalle': 'Contradice petición', 'fuentes': []}], 'faltan_datos': []},
                        {'problemas': [], 'faltan_datos': ['Dirección IP desconocida']}):
            with self.subTest(critica=critica):
                self.assertEqual(tutor.revisar_leccion(self.resultado(), lambda *a: critica)['estado'], 'BLOQUEADA')

    def test_revisor_tampoco_puede_inventar_citas(self):
        critica = {'problemas': [{'gravedad': 'advertencia', 'detalle': 'Ver F99', 'fuentes': ['F99']}], 'faltan_datos': []}
        self.assertEqual(tutor.revisar_leccion(self.resultado(), lambda *a: critica)['estado'], 'BLOQUEADA')

    def test_sin_objeciones_no_significa_verificado(self):
        revision = tutor.revisar_leccion(self.resultado(), lambda *a: {'problemas': [], 'faltan_datos': []})
        self.assertEqual(revision['estado'], 'SIN_OBJECIONES_CRITICAS_AUTOMATICAS')
        self.assertIn('No se ejecutó', revision['alcance'])

    def test_modo_reglas_no_invoca_revisor_inestable(self):
        def no_consultar(*args):
            self.fail('El modo de reglas no debe consultar el revisor')
        revision = tutor.revisar_leccion(self.resultado(), no_consultar, con_modelo=False)
        self.assertEqual(revision['estado'], 'REGLAS_SUPERADAS_NO_VERIFICADA')

    def test_cli_conserva_candidato_bloqueado_y_sale_con_error(self):
        candidato = self.resultado()
        candidato['leccion']['pasos'] = [{'fuentes': ['F99']}]
        with tempfile.TemporaryDirectory() as carpeta:
            salida = Path(carpeta) / 'resultado.json'
            argumentos = ['tutor', '--manuales', carpeta, '--app', 'Prueba', '--pregunta', 'Pregunta', '--salida', str(salida)]
            with patch('sys.argv', argumentos), patch('sys.stdout', new_callable=io.StringIO), \
                 patch.object(tutor, 'crear_leccion', return_value=candidato), self.assertRaises(SystemExit) as error:
                tutor.main()
            self.assertEqual(error.exception.code, 2)
            guardado = json.loads(salida.read_text(encoding='utf-8'))
            self.assertEqual(guardado['revision']['estado'], 'BLOQUEADA')
            self.assertEqual(guardado['leccion']['pasos'][0]['fuentes'], ['F99'])


if __name__ == '__main__':
    unittest.main()
