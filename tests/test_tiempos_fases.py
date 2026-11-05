import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import rendimiento
from experimentos.medir_tiempos_simulados import medir, Reloj


class FasesTests(unittest.TestCase):
    def test_desglose_del_controlador_con_reloj_virtual_sin_input(self):
        resultado = medir()
        clic, cierre = resultado['pasos']
        self.assertAlmostEqual(clic['espera_antes_accion_s'], 1.8)
        self.assertAlmostEqual(clic['ejecucion_accion_s'], .55)
        self.assertAlmostEqual(clic['reobservacion_s'], .07)
        self.assertAlmostEqual(clic['fases_exclusivas_s']['consulta_modelo_s'], 2.2)
        self.assertAlmostEqual(clic['segundos'], 4.65)
        self.assertAlmostEqual(clic['segundos_con_captura_inicial_s'], 5.35)
        self.assertAlmostEqual(cierre['espera_posterior_s'], .45)
        self.assertAlmostEqual(cierre['fases_exclusivas_s']['captura_percepcion_s'], .7)
        self.assertAlmostEqual(clic['no_atribuido_s'], 0)
        for fila in resultado['pasos']:
            self.assertAlmostEqual(sum(fila['fases_exclusivas_s'].values()) + fila['no_atribuido_s'], fila['segundos'])

    def test_actividad_descuenta_hijos_y_conserva_error(self):
        reloj = Reloj()
        with tempfile.TemporaryDirectory() as carpeta, \
             patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': str(Path(carpeta) / 'pasos.jsonl')}), \
             patch.object(rendimiento.time, 'perf_counter', side_effect=reloj.ahora):
            with self.assertRaises(ValueError):
                with rendimiento.paso(1, 'prueba') as paso:
                    with rendimiento.actividad('padre'):
                        reloj.avanzar(1)
                        with rendimiento.actividad('hijo'):
                            reloj.avanzar(2)
                        reloj.avanzar(1)
                        raise ValueError('prueba')
        self.assertEqual(paso['fases_exclusivas_s'], {'hijo': 2, 'padre': 2})
        self.assertIsNone(rendimiento.ACTIVIDAD.get())
