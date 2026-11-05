import tempfile
import unittest
from pathlib import Path

from experimentos.comprobar_instrumentacion import comprobar


class InstrumentacionEquivalenteTests(unittest.TestCase):
    def test_head_actual_y_sin_medicion_mantienen_secuencia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = comprobar(Path(carpeta) / 'comparacion')
        self.assertTrue(resultado['identicos'])
        self.assertTrue(all(resultado['ast_sin_envoltorios_igual_a_head'].values()))
        self.assertEqual(resultado['consultas'], 5)
        self.assertEqual([a['nombre'] for a in resultado['acciones']],
                         ['mover_suave', 'clic', 'seleccionar_todo', 'escribir', 'tecla'])
        self.assertEqual(resultado['tarea']['estado'], 'completada')
