import copy
import json
import unittest

from entornos_evaluacion import EscritorioSimulado
from experimentos.banco_verificador import CASOS_POR_ID, capturar, sinteticas
from experimentos.replay_verificador import inconsistente, prueba_condicion, suposiciones
from experimentos.replay_verificador_observado import decidir, objetivos_visibles, prueba
import agente
from unittest.mock import patch


class BancoVerificadorTests(unittest.TestCase):
    def test_inconsistencia_no_convierte_verdadero(self):
        self.assertTrue(inconsistente({'cumplido': False, 'pendiente': 'Ninguna.'}))
        self.assertFalse(inconsistente({'cumplido': True, 'pendiente': 'Ninguna'}))
        self.assertFalse(inconsistente({'cumplido': False, 'pendiente': 'Ninguna nota guardada'}))

    def test_lista_cerrada_de_suposiciones(self):
        for texto in ('Se asume completado', 'SE SUPONE que terminó', 'Presumiblemente guardado'):
            self.assertTrue(suposiciones(texto))
        self.assertFalse(suposiciones('Se observa el resultado'))
        self.assertFalse(suposiciones('Supongo que terminó'))
        self.assertTrue(suposiciones('No se asume: se observa'))

    def test_una_condicion_privada_por_negativo(self):
        caso = CASOS_POR_ID['codigo_a_nota']
        app = EscritorioSimulado(caso, 42)
        app.ventana = 'nota'
        app.enviado = caso['esperado']
        app.valores['cuerpo'] = caso['esperado']
        app.resultado = 'Guardado correctamente: ' + app.enviado
        elementos, estado = app.observar()
        estado['memoria_tarea'] = {'etapas': [
            {'n': 1, 'estado': 'comprobada', 'evidencia': 'Código leído'},
            {'n': 2, 'estado': 'comprobada', 'evidencia': app.resultado}],
            'hechos_observados': {'codigo': {'valor': caso['esperado'], 'fuente': 'Ficha'}}}
        e = {'id': 'prueba', 'caso': caso['id'], 'semilla': 42, 'alcance': 'global',
            'etapa': None, 'objetivo': caso['objetivo'], 'oraculo': True, 'oraculo_v2': True,
            'origen': 'real_exacta', 'contaminacion': [], 'estado': estado,
            'estado_privado': app.diagnostico(), 'elementos': elementos, 'historial': [],
            'payload': {'messages': []}, 'consulta': capturar(caso['objetivo'], elementos, estado, [])}
        es = sinteticas([e])
        self.assertEqual(len(es), 4)
        for s in es:
            cambios = {k for k in e['estado_privado'] if e['estado_privado'][k] != s['estado_privado'][k]}
            if s['origen'] == 'sintetico_negativo':
                self.assertEqual(cambios, {'guardado'})
                self.assertFalse(s['oraculo'])
                self.assertFalse(s['oraculo_v2'])
            else:
                self.assertEqual(cambios, set())
                self.assertTrue(s['oraculo'])
                self.assertTrue(s['oraculo_v2'])

    def test_casilla_actual_no_se_sustituye_por_memoria(self):
        c = {'ventana': 'Ficha', 'controles': [{'nombre': 'Revisado', 'activado': False}],
             'memoria_tarea': {'etapas': [{'estado': 'comprobada', 'evidencia': 'Revisado activado'}]}}
        e = {'caso': 'nota_y_regreso', 'consulta': {'prompt': 'USER REQUEST: prueba\nCURRENT STATE:\n' + json.dumps(c)}}
        self.assertFalse(prueba_condicion(e, 'casilla', '/controles/0/activado'))
        self.assertFalse(prueba_condicion(e, 'casilla', '/memoria_tarea/etapas/0/evidencia'))
        positivo = copy.deepcopy(e)
        c['controles'][0]['activado'] = True
        positivo['consulta']['prompt'] = 'USER REQUEST: prueba\nCURRENT STATE:\n' + json.dumps(c)
        self.assertTrue(prueba_condicion(positivo, 'casilla', '/controles/0/activado'))

    def test_v3_solo_lee_valores_del_estado_y_no_del_oraculo(self):
        c = {'ventana': 'Ficha', 'controles': [], 'memoria_tarea': {
            'hechos_observados': {'registro': {'valor': '417', 'fuente': 'Ficha'}},
            'etapas': [{'n': 2, 'estado': 'comprobada', 'evidencia': 'Guardado correctamente: Registro: 417'}]}}
        e = {'caso': 'nota_y_regreso', 'consulta': {'prompt': 'USER REQUEST: prueba\nCURRENT STATE:\n' + json.dumps(c)},
             'estado_privado': {'guardado': '9999'}, 'oraculo': False,
             'alcance': 'etapa', 'etapa': 2, 'objetivo': 'Escribe el número leído en la nota y guárdala.',
             'elementos': [], 'estado': c, 'historial': []}
        with patch.dict(CASOS_POR_ID['nota_y_regreso'], {'esperado': '1111'}):
            self.assertEqual(objetivos_visibles(e), ['417'])
            self.assertTrue(prueba(e, 'guardado', '/memoria_tarea/etapas/0/evidencia'))
            self.assertTrue(agente.final_confirmado(decidir(e, {'condiciones': [
                {'id': 'guardado', 'observado': True, 'campo': '/memoria_tarea/etapas/0/evidencia',
                 'evidencia': 'Registro: 417'}]})))
