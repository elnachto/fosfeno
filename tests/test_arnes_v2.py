import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agente
import evaluacion
import tareas
from entornos_evaluacion import sin_entrada_nativa
from experimentos import evaluar_arnes_v2


class ArnesV2Tests(unittest.TestCase):
    def test_listo_verifica_etapa_y_actualiza_memoria_antes_del_objetivo(self):
        caso = copy.deepcopy(next(c for c in evaluacion.CASOS if c['id'] == 'app_inicio'))
        caso['etapas'] = ['Comprueba la ventana solicitada']
        sesion = tareas.SesionTarea(caso['objetivo'], caso['etapas'])
        vistos = []
        def verificar(objetivo, elementos, estado, *args):
            vistos.append((objetivo, copy.deepcopy(estado['memoria_tarea'])))
            return {'cumplido': True, 'evidencia': 'Doble de verificación; el oráculo sigue independiente', 'pendiente': ''}
        with tempfile.TemporaryDirectory() as carpeta, sin_entrada_nativa(), \
             patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': carpeta + '/pasos.jsonl'}), \
             patch.object(evaluacion.tareas, 'SesionTarea', return_value=sesion), \
             patch.object(agente, 'proponer', return_value=({'tipo': 'listo'}, {}, 1)), \
             patch.object(agente, 'verificar', side_effect=verificar):
            resultado = evaluacion.ejecutar_caso(caso, 'nemotron', 99)
        self.assertEqual([v[0] for v in vistos], [caso['etapas'][0], caso['objetivo']])
        self.assertEqual(vistos[0][1]['etapa_activa'], 1)
        self.assertIsNone(vistos[1][1]['etapa_activa'])
        self.assertFalse(resultado['correcto'])
        self.assertTrue(resultado['falso_exito_aceptado'])

    def test_corrida_v2_rechaza_carpeta_existente_antes_de_escribir(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaises(FileExistsError):
                evaluar_arnes_v2.ejecutar(Path(carpeta), [], [])

    def test_nada_promovido_no_salta_una_etapa_rechazada(self):
        caso = copy.deepcopy(next(c for c in evaluacion.CASOS if c['id'] == 'app_inicio'))
        caso['etapas'] = ['Comprueba la ventana solicitada']
        propuestas = iter([{'tipo': 'esperar'}, {'tipo': 'nada'}])
        objetivos = []
        def verificar(objetivo, *args):
            objetivos.append(objetivo)
            return {'cumplido': objetivo == caso['objetivo'], 'evidencia': 'Doble de prueba',
                    'pendiente': '' if objetivo == caso['objetivo'] else 'Falta comprobar la ventana'}
        with tempfile.TemporaryDirectory() as carpeta, sin_entrada_nativa(), \
             patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': carpeta + '/pasos.jsonl'}), \
             patch.object(agente, 'proponer', side_effect=lambda *a, **k: (next(propuestas), {}, 1)), \
             patch.object(agente, 'verificar', side_effect=verificar):
            resultado = evaluacion.ejecutar_caso(caso, 'nemotron', 42)
        self.assertEqual(objetivos, [caso['objetivo'], caso['etapas'][0]])
        self.assertFalse(resultado['falso_exito_aceptado'])
        self.assertFalse(resultado['correcto'])

    def test_nada_positivo_no_se_etiqueta_rechazo_seguro(self):
        caso = copy.deepcopy(next(c for c in evaluacion.CASOS if c['id'] == 'app_inicio'))
        app = evaluacion.EscritorioSimulado(caso, 42)
        app.ventana = 'configuracion'
        app.app_abierta = 'Configuración'
        with tempfile.TemporaryDirectory() as carpeta, sin_entrada_nativa(), \
             patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': carpeta + '/pasos.jsonl'}), \
             patch.object(evaluacion, 'EscritorioSimulado', return_value=app), \
             patch.object(agente, 'proponer', return_value=({'tipo': 'nada'}, {}, 1)):
            resultado = evaluacion.ejecutar_caso(caso, 'nemotron', 42)
        self.assertTrue(resultado['objetivo_logrado'])
        self.assertFalse(resultado['correcto'])
        self.assertNotIn('rechazo seguro', resultado['motivo'])

    def test_siguiente_final_pasa_al_cierre_global(self):
        caso = copy.deepcopy(next(c for c in evaluacion.CASOS if c['id'] == 'app_inicio'))
        caso['etapas'] = ['Comprueba la ventana solicitada']
        with tempfile.TemporaryDirectory() as carpeta, sin_entrada_nativa(), \
             patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': carpeta + '/pasos.jsonl'}), \
             patch.object(agente, 'proponer', return_value=({'tipo': 'siguiente'}, {}, 1)) as proponer, \
             patch.object(agente, 'verificar', return_value={'cumplido': True, 'evidencia': 'Doble de prueba', 'pendiente': ''}) as verificar:
            resultado = evaluacion.ejecutar_caso(caso, 'nemotron', 42)
        self.assertEqual(proponer.call_count, 1)
        self.assertEqual(verificar.call_count, 2)
        self.assertTrue(resultado['falso_exito_aceptado'])

    def test_alerta_aborta_solo_la_ejecucion_y_conserva_evidencia(self):
        casos = evaluacion.CASOS[:2]
        resultados = [{'caso': c['id'], 'semilla': 42, 'correcto': i == 1,
            'motivo': 'doble', 'pasos': 1, 'consultas': 0, 'tokens_por_consulta': 0,
            'segundos': 0, 'objetivo_logrado': i == 1, 'falso_exito_aceptado': i == 0}
            for i, c in enumerate(casos)]
        with tempfile.TemporaryDirectory() as carpeta, \
             patch.object(evaluacion, 'ejecutar_caso', side_effect=resultados):
            salida = Path(carpeta) / 'nueva'
            obtenidos = evaluar_arnes_v2.ejecutar(salida, casos, [42], continuar_falsos=True)
            self.assertEqual(len(obtenidos), 2)
            self.assertTrue((salida / 'ALERTA-FALSO-EXITO-nota-42.json').is_file())
