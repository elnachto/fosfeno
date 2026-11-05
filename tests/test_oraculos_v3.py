import tempfile
import unittest
from pathlib import Path

from experimentos.oraculos_v3 import nota_y_regreso_v3, repuntuar


class OraculoV3Tests(unittest.TestCase):
    def test_numero_como_token_independiente(self):
        for texto in ('417', 'Registro: 417', '(417)', 'Registro:\n417\n'):
            with self.subTest(texto=texto):
                self.assertTrue(nota_y_regreso_v3({'guardado': texto,
                    'revisado': True, 'ventana': 'fuente'}))

    def test_no_acepta_subcadenas_de_otros_tokens(self):
        for texto in ('4170', '1417', 'A417', '417A', '_417', '', None):
            with self.subTest(texto=texto):
                self.assertFalse(nota_y_regreso_v3({'guardado': texto,
                    'revisado': True, 'ventana': 'fuente'}))

    def test_mantiene_guardado_casilla_y_ventana(self):
        for estado in ({'guardado': '417', 'revisado': False, 'ventana': 'fuente'},
                       {'guardado': '417', 'revisado': True, 'ventana': 'nota'},
                       {'guardado': None, 'revisado': True, 'ventana': 'fuente'}):
            with self.subTest(estado=estado):
                self.assertFalse(nota_y_regreso_v3(estado))

    def test_carpeta_sin_resultados(self):
        with tempfile.TemporaryDirectory() as carpeta:
            self.assertEqual(repuntuar(Path(carpeta)), [])
