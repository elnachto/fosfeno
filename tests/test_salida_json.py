import copy
import json
from pathlib import Path
import tempfile
import warnings
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import agente
import marcas
import motor_ia
import rendimiento
import salida_json
import servidores_lfm3


class SalidaJsonTests(unittest.TestCase):
    def test_nemotron_restringe_json_sin_bloque_de_pensamiento(self):
        esquema = agente.esquema(2)
        with patch.dict('os.environ', {'FOSFENO_GBNF_EXPERIMENTAL': '1'}):
            formato = marcas.formato_salida_json('fosfeno-nemotron', esquema)
        self.assertNotIn('response_format', formato)
        gramatica = formato['grammar']
        self.assertTrue(gramatica.startswith('root ::= "{"'))
        self.assertNotIn('thought', gramatica)
        self.assertIn('char{0,80}', gramatica)
        self.assertIn('char{0,60}', gramatica)
        self.assertIn('campo-3 ::= "0" | "1" | "2"', gramatica)
        self.assertEqual(gramatica.splitlines()[0].count('campo-'), 6)

    def test_json_schema_es_el_valor_por_defecto(self):
        with patch.dict('os.environ', {'FOSFENO_GBNF_EXPERIMENTAL': '0'}):
            formato = marcas.formato_salida_json('fosfeno-nemotron', agente.esquema(3))
        self.assertIn('response_format', formato)
        self.assertNotIn('grammar', formato)

    def test_otros_modelos_y_esquemas_no_soportados_conservan_schema(self):
        esquema = agente.esquema(2)
        formato = marcas.formato_salida_json('fosfeno-lfm3', esquema)
        self.assertEqual(formato['response_format']['json_schema']['schema'], esquema)
        self.assertNotIn('grammar', formato)
        variante = copy.deepcopy(esquema)
        variante['properties']['texto']['pattern'] = '^seguro$'
        self.assertIsNone(salida_json.compacta(variante))
        self.assertIn('response_format', marcas.formato_salida_json('fosfeno-nemotron', variante))
        variante = copy.deepcopy(esquema)
        variante['required'].remove('texto')
        self.assertIsNone(salida_json.compacta(variante))

    def test_enum_respeta_limites_y_escapes(self):
        esquema = {'type': 'object', 'additionalProperties': False,
                   'properties': {'texto': {'type': 'string', 'enum': ['a"b\\c\n', 'demasiado largo'], 'maxLength': 8}},
                   'required': ['texto']}
        gramatica = salida_json.compacta(esquema)
        literal = json.dumps(json.dumps('a"b\\c\n', ensure_ascii=False), ensure_ascii=False)
        self.assertIn(literal, gramatica)
        self.assertNotIn('demasiado', gramatica)

    def test_esquema_nemotron_coincide_con_e2_sin_mutar_original(self):
        from experimentos.evaluar_rapidez_variantes import esquema_observacion
        original = agente.esquema(3)
        esperado = esquema_observacion(original)
        with patch.dict('os.environ', {'FOSFENO_GBNF_EXPERIMENTAL': '0'}):
            formato = marcas.formato_salida_json('fosfeno-nemotron', original)
        self.assertEqual(json.dumps(formato['response_format']['json_schema']['schema']), json.dumps(esperado))
        self.assertEqual(list(original['properties'])[0], 'accion')
        self.assertEqual(marcas.esquema_salida_json('fosfeno-lfm3', original), original)

    def test_presupuesto_solo_se_aplica_al_arranque_nemotron(self):
        nemo = next(s for s in servidores_lfm3.SERVIDORES if s['puerto'] == 8095)
        lfm = next(s for s in servidores_lfm3.SERVIDORES if s['puerto'] == 8096)
        self.assertEqual(servidores_lfm3.opciones_razonamiento(nemo), ['--reasoning-budget', '64'])
        self.assertEqual(servidores_lfm3.opciones_razonamiento(lfm), [])

    def test_aviso_de_servidor_viejo_se_emite_una_vez(self):
        datos = {'choices': [{'message': {'reasoning_content': 'razonamiento de prueba'}}]}
        respuesta = SimpleNamespace(json=lambda: {'tokens': list(range(120))}, raise_for_status=lambda: None)
        with patch.object(marcas, 'SERVIDORES_RAZONAMIENTO_AVISADOS', set()), \
             patch.object(marcas.requests, 'post', return_value=respuesta) as post:
            with self.assertWarnsRegex(RuntimeWarning, 'servidor antiguo'):
                cuenta = marcas.comprobar_presupuesto_razonamiento('http://localhost/v1/chat/completions', 'fosfeno-nemotron', datos)
            marcas.comprobar_presupuesto_razonamiento('http://localhost/v1/chat/completions', 'fosfeno-nemotron', datos)
        self.assertEqual(cuenta, 120)
        self.assertEqual(post.call_count, 1)

    def test_no_avisa_si_el_razonamiento_respeta_el_presupuesto(self):
        datos = {'choices': [{'message': {'reasoning_content': 'razonamiento de prueba'}}]}
        respuesta = SimpleNamespace(json=lambda: {'tokens': list(range(64))}, raise_for_status=lambda: None)
        with patch.object(marcas, 'SERVIDORES_RAZONAMIENTO_AVISADOS', set()), \
             patch.object(marcas.requests, 'post', return_value=respuesta), warnings.catch_warnings(record=True) as avisos:
            cantidad = marcas.comprobar_presupuesto_razonamiento('http://localhost/v1/chat/completions', 'fosfeno-nemotron', datos)
        self.assertEqual(cantidad, 64)
        self.assertEqual(len(avisos), 0)

    def test_crudo_es_optativo_completo_y_limitado_a_doce(self):
        esquema = agente.esquema(2)
        datos = {'choices': [{'message': {'content': '{\n"n":2\n}', 'reasoning_content': 'razón'},
                              'finish_reason': 'stop'}], 'usage': {'completion_tokens': 13}}
        def post(url, json, timeout):
            self.assertTrue(url.endswith('/tokenize'))
            self.assertFalse(json['add_special'])
            return SimpleNamespace(json=lambda: {'tokens': [1, 2, 3]}, raise_for_status=lambda: None)
        with tempfile.TemporaryDirectory() as carpeta, \
             patch.object(rendimiento, 'RUTA_CRUDO', Path(carpeta)), \
             patch.object(rendimiento, 'CRUDO_CONTADOR', 0), \
             patch.object(rendimiento.requests, 'post', side_effect=post) as consulta:
            with patch.dict('os.environ', {'FOSFENO_TIEMPOS_CRUDO': '0'}):
                rendimiento.registrar_crudo('http://localhost/v1/chat/completions', {}, esquema, datos)
            consulta.assert_not_called()
            with patch.dict('os.environ', {'FOSFENO_TIEMPOS_CRUDO': '1'}):
                for i in range(14):
                    rendimiento.registrar_crudo('http://localhost/v1/chat/completions', {'grammar': 'root'}, esquema, datos)
            filas = [json.loads(s) for p in Path(carpeta).glob('*.jsonl') for s in p.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(filas), 12)
        self.assertEqual(consulta.call_count, 24)
        self.assertEqual(filas[0]['respuesta'], datos)
        self.assertEqual(filas[0]['content_tokens'], 3)


if __name__ == '__main__':
    unittest.main()
