import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agente
from experimentos import evaluar_rapidez_variantes as variantes


class VariantesTests(unittest.TestCase):
    def test_orden_observacion_no_cambia_los_limites_ni_el_original(self):
        esquema = agente.esquema(8)
        anterior = copy.deepcopy(esquema)
        ordenado = variantes.esquema_observacion(esquema)
        esperado = ['evidencia', 'objetivo_pendiente', 'accion', 'n', 'texto', 'reemplazar']
        self.assertEqual(list(ordenado['properties']), esperado)
        self.assertEqual(ordenado['required'], esperado)
        self.assertEqual(ordenado['properties'], anterior['properties'])
        self.assertEqual(esquema, anterior)

    def test_no_sobrescribe_mediciones_ni_toca_el_servidor(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'E1'
            ruta.mkdir()
            (ruta / 'resultados.json').write_text(json.dumps([]), encoding='utf-8')
            with patch('sys.argv', ['variantes', '--salida', carpeta]), \
                 patch.object(variantes, 'iniciar_servidor') as iniciar:
                with self.assertRaises(FileExistsError):
                    variantes.main()
                iniciar.assert_not_called()

    def test_restaura_el_presupuesto_adoptado_al_final(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with patch('sys.argv', ['variantes', '--salida', carpeta]), \
                 patch.dict(variantes.VARIANTES, {}, clear=True), \
                 patch.object(variantes, 'iniciar_servidor') as iniciar:
                variantes.main()
                iniciar.assert_called_once_with(
                    {'presupuesto': 64, 'prefill': False}, Path(carpeta).resolve() / 'servidor-restaurado')


if __name__ == '__main__':
    unittest.main()
