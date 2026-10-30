"""Aprendizaje por demostración y aislamiento de referencias entre aplicaciones."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import acciones
import agente
import memoria
import precondiciones
import tareas


class AprendizajeGeneralTests(unittest.TestCase):
    def test_demostracion_conserva_objetivo_y_pasos_sin_generar_plantilla(self):
        with tempfile.TemporaryDirectory() as carpeta, patch.object(memoria, 'CONOCIMIENTO', carpeta), \
                patch.object(memoria, 'RECETAS', str(Path(carpeta)/'recetas.jsonl')):
            pasos = ['clic en «Nombre»', 'escribí «Elena» en «Nombre»', 'clic en «Guardar»']
            memoria.guardar_receta('agenda', 'Crea un contacto llamado Elena', pasos, 'demostracion')
            antes = Path(memoria.RECETAS).read_bytes()
            recetas = memoria.buscar_recetas('Crea un contacto llamado Lucas', 'agenda')
            self.assertEqual(len(recetas), 1)
            self.assertEqual(recetas[0]['pasos'], pasos)
            self.assertNotIn('plantilla', recetas[0])
            texto = memoria.texto_recetas(recetas, 'Crea un contacto llamado Lucas')
            self.assertIn('te lo enseñó el usuario', texto)
            self.assertIn('Elena', texto)  # Referencia histórica literal; el modelo adapta el pedido actual.
            self.assertEqual(Path(memoria.RECETAS).read_bytes(), antes)

    def test_recetas_solo_de_app_actual_sin_contaminacion_por_objetivos_parecidos(self):
        rs = [{'app': app, 'objetivo': 'Crea un registro', 'pasos': ['escribí «'+app+'»'],
               'fuente': 'demostracion'} for app in ('editor', 'inventario')]
        with patch.object(memoria, 'leer_recetas', return_value=rs):
            r = memoria.buscar_recetas('Crea un registro', 'inventario')
            self.assertEqual([x['app'] for x in r], ['inventario'])
            self.assertEqual(memoria.buscar_recetas('Crea un registro', ''), [])
            self.assertEqual(memoria.buscar_recetas('Crea un registro', 'app desconocida'), [])

    def test_metadatos_de_plantilla_antigua_no_imponen_variables_ni_se_reescriben(self):
        r = {'app': 'editor', 'objetivo': 'Crea un registro', 'pasos': ['escribí «dato demostrado»'],
             'fuente': 'demostracion',
             'plantilla': {'objetivo': '{{valor}}', 'parametros': {'valor': {'requerido': True}},
                           'pasos': ['escribí «{{valor}}»'], 'operacion': 'operacion_antigua'}}
        antes = json.dumps(r)
        texto = memoria.texto_recetas([r], 'Crea un registro con otro valor')
        self.assertIn('dato demostrado', texto)
        self.assertNotIn('PREGUNTAR', texto)
        self.assertNotIn('{{', texto)
        self.assertEqual(json.dumps(r), antes)

    def test_memoria_de_trabajo_no_inyecta_campos_de_un_dominio(self):
        t = tareas.SesionTarea('Crea un registro de inventario')
        contexto = t.contexto()
        self.assertNotIn('parametros_usuario', contexto)
        self.assertNotIn('parametros_ambiguos', contexto)
        self.assertNotIn('errores_parametros', contexto)
        self.assertNotIn('parametros', t.resultado())
        t.recordar('{"clave":"codigo","valor":"ABC-17"}', {'texto_visible': 'Código ABC-17'})
        self.assertEqual(t.contexto()['hechos_observados']['codigo']['valor'], 'ABC-17')

    def test_prompts_generales_no_precargan_criterios_de_red(self):
        for prompt in (agente.INSTRUCCION, precondiciones.INSTRUCCION):
            for termino in ('mikrotik', 'winbox', 'dhcp', 'vlan', 'mac address', 'currency', 'gateway'):
                self.assertNotIn(termino, prompt.lower())

    def test_demostracion_llega_como_referencia_al_planificador_con_orden_actual(self):
        refs = memoria.texto_recetas([{'app': 'agenda', 'objetivo': 'Crea el contacto Elena',
                'pasos': ['escribí «Elena» en «Nombre»'], 'fuente': 'demostracion'}])
        recibidos = []
        def consultar(sistema, prompt, *args):
            recibidos.append((sistema, prompt))
            return {'accion': 'ESCRIBIR', 'n': 1, 'texto': 'Lucas', 'reemplazar': True}
        e = [('Edit', 'Nombre', 0, 0, 100, 30)]
        a, _, _ = agente.proponer('Crea el contacto Lucas', e,
            {'foco': {'n': 1, 'editable': True, 'nombre': 'Nombre', 'valor': ''}}, [],
            consultar, acciones.normalizar_tecla, referencias={'recetas': refs})
        self.assertEqual(a['texto'], 'Lucas')
        self.assertIn('Elena', recibidos[0][1])
        self.assertIn('Lucas', recibidos[0][1])
        self.assertIn('Past field values are examples', recibidos[0][0])


if __name__ == '__main__':
    unittest.main()
