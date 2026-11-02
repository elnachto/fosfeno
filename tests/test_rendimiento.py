import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import agente
import evaluacion
import marcas
import rendimiento
import tareas


class RendimientoTests(unittest.TestCase):
    def test_accion_corta_y_verificacion_larga_son_independientes(self):
        esquema = agente.esquema(4)
        self.assertEqual(list(esquema['properties'])[:3], ['accion', 'n', 'texto'])
        self.assertEqual(esquema['required'][:3], ['accion', 'n', 'texto'])
        self.assertEqual(esquema['properties']['evidencia']['maxLength'], 80)
        self.assertEqual(esquema['properties']['objetivo_pendiente']['maxLength'], 60)
        self.assertEqual(marcas.limite_salida_json(esquema), 640)
        capturados = []
        def consultar(instruccion, prompt, schema, imagen):
            capturados.append(schema)
            return {'cumplido': True, 'evidencia': 'a' * 300, 'pendiente': ''}
        final = agente.verificar('Completa la tarea', [], {}, [], consultar)
        self.assertTrue(agente.final_confirmado(final))
        self.assertEqual(capturados[0]['properties']['evidencia']['maxLength'], 300)
        self.assertEqual(marcas.limite_salida_json(capturados[0]), 640)
        sesion = tareas.SesionTarea('Completa la tarea')
        sesion.avanzar(final)
        self.assertEqual(sesion.etapas[0]['evidencia'], 'a' * 300)

    def test_reintento_conserva_tokens_de_la_salida_truncada(self):
        enviados = []
        json_module = json
        def post(url, json, timeout):
            enviados.append(copy.deepcopy(json))
            contenido = json_module.dumps({'accion': 'CLIC', 'n': 1, 'texto': '', 'reemplazar': False,
                                           'evidencia': 'Control visible', 'objetivo_pendiente': 'Abrir'})
            dato = {'choices': [{'message': {'content': contenido},
                                'finish_reason': 'length' if len(enviados) == 1 else 'stop'}],
                    'usage': {'completion_tokens': 50},
                    'timings': {'prompt_ms': 20, 'predicted_ms': 80}}
            return SimpleNamespace(json=lambda: dato, raise_for_status=lambda: None)
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'pasos.jsonl'
            with patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': str(ruta)}), \
                 patch.object(marcas.requests, 'post', side_effect=post):
                with rendimiento.paso(1, 'prueba') as paso:
                    paso['accion'] = marcas._consultar_json('http://localhost', 'test', 'i', 'e', agente.esquema(1))
            registrado = json.loads(ruta.read_text(encoding='utf-8'))
        self.assertEqual([p['max_tokens'] for p in enviados], [640, 2400])
        self.assertEqual(registrado['tokens_generados'], 100)
        self.assertEqual(registrado['consultas'], 2)
        self.assertAlmostEqual(registrado['generacion_s'], .16)
        self.assertEqual(registrado['accion']['accion'], 'CLIC')
        self.assertEqual(registrado['accion']['n'], 1)
        self.assertIsNone(rendimiento.ACTUAL.get())

    def test_fases_anidadas_no_se_cuentan_dos_veces_y_se_registra_error(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'pasos.jsonl'
            with patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': str(ruta)}):
                with self.assertRaises(ValueError):
                    with rendimiento.paso(1, 'prueba'):
                        with patch.object(rendimiento.time, 'perf_counter', side_effect=[0, 1, 3, 4]):
                            with rendimiento.fase('prompt_local_s'):
                                with rendimiento.fase('prompt_local_s'):
                                    pass
                        raise ValueError('cancelado')
            dato = json.loads(ruta.read_text(encoding='utf-8'))
        self.assertEqual(dato['prompt_local_s'], 4)
        self.assertEqual(dato['tokens_generados'], 0)
        self.assertIn('cancelado', dato['error'])
        self.assertIsNone(rendimiento.ACTUAL.get())

    def test_caso_incluye_verificacion_en_los_tiempos_del_paso(self):
        caso = next(c for c in evaluacion.CASOS if c['id'] == 'checkbox')
        respuestas = iter([{'tipo': 'clic', 'n': 1}, {'tipo': 'nada'}])
        def proponer(*args, **kwargs):
            return next(respuestas), {}, 1
        with tempfile.TemporaryDirectory() as carpeta, \
             patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': str(Path(carpeta) / 'pasos.jsonl')}), \
             patch.object(agente, 'proponer', side_effect=proponer), \
             patch.object(agente, 'verificar', return_value={'cumplido': False, 'pendiente': 'falta'}):
            resultado = evaluacion.ejecutar_caso(caso, 'nemotron', 42)
        self.assertEqual(len(resultado['traza']), 2)
        self.assertEqual(resultado['traza'][1]['tiempos']['accion']['tipo'], 'nada')
        self.assertIn('verificacion', resultado['traza'][1])
        self.assertIn('generacion_s', resultado['traza'][1]['tiempos'])


if __name__ == '__main__':
    unittest.main()
