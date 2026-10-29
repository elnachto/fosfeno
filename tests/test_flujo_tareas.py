"""Integración del coordinador: entradas de escritorio sustituidas por dobles explícitos."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import jarvis
import marcas
import tareas


class FlujoTests(unittest.TestCase):
    def test_nada_se_recupera_solo_con_verificacion_y_cierra_etapas(self):
        propuestas = iter([{'tipo': 'recordar', 'texto': '{"clave":"cantidad","valor":"83"}'},
                           {'tipo': 'siguiente'}, {'tipo': 'decir', 'texto': 'La cantidad es 83.'}, {'tipo': 'nada'}])
        ok = {'cumplido': True, 'evidencia': 'Datos y respuesta comprobados', 'pendiente': ''}
        with tempfile.TemporaryDirectory() as carpeta:
            resultado, _, _ = self.ejecutar(carpeta, ['Lee las cantidades', 'Dime la cantidad'], propuestas, [ok] * 3)
            self.assertEqual(resultado['estado'], 'completada')
            self.assertTrue(all(e['estado'] == 'comprobada' for e in resultado['etapas']))

    def test_verificacion_global_recibe_las_etapas_ya_comprobadas(self):
        propuestas = iter([{'tipo': 'recordar', 'texto': '{"clave":"cantidad","valor":"83"}'},
                           {'tipo': 'siguiente'}, {'tipo': 'decir', 'texto': 'La cantidad es 83.'}, {'tipo': 'listo'}])
        def revisar(objetivo, elementos, estado, *args):
            if ' y luego ' in objetivo:
                self.assertTrue(all(e['estado'] == 'comprobada' for e in estado['memoria_tarea']['etapas']))
            return {'cumplido': True, 'evidencia': 'Dato y respuesta observados', 'pendiente': ''}
        with tempfile.TemporaryDirectory() as carpeta:
            resultado, _, _ = self.ejecutar(carpeta, ['Lee las cantidades', 'Dime la cantidad'], propuestas, revisar)
            self.assertEqual(resultado['estado'], 'completada')

    def test_muestra_el_resultado_aunque_no_pueda_guardar_el_informe(self):
        t = tareas.SesionTarea('Identifica la VLAN')
        def detener(*args):
            t.terminar('requiere_datos', '¿Cuál es la VLAN?')
        with patch.object(jarvis.marcas, 'partir_objetivo', return_value=[]), \
             patch.object(jarvis.tareas, 'SesionTarea', return_value=t), \
             patch.object(jarvis, '_ejecutar_tarea', side_effect=detener), \
             patch.object(t, 'guardar', side_effect=PermissionError('Sin acceso')), patch.object(jarvis, 'avisar') as aviso:
            jarvis.ejecutar('Identifica la VLAN', None, 'test')
        self.assertIn('¿Cuál es la VLAN?', aviso.call_args.args[0])
        self.assertIsNone(jarvis.ESTADO['ultimo_resultado']['ruta'])

    def ejecutar(self, carpeta, partes, propuestas, revisiones):
        estado = {'ventana': 'Nota de prueba', 'hwnd': 10, 'texto_visible': 'Cantidad: 83',
                  'foco': {'n': 1, 'editable': True, 'nombre': 'Texto', 'valor': 'Cantidad: 83'}}
        imagen = MagicMock(size=(500, 400))
        elementos = [('Edit', 'Texto', 0, 0, 400, 300)]
        escaneo = (imagen, 'Nota de prueba', elementos)
        prompts = []
        def decidir(*args, **kwargs):
            prompts.append(kwargs['tarea'].contexto())
            return next(propuestas), '{}', '', imagen, 0
        with patch.object(jarvis.marcas, 'OUT', carpeta), patch.object(jarvis.marcas, 'ESTADO_UI', estado), \
             patch.object(jarvis.marcas, 'PERFIL', {'agente_estado': True, 'nombre': 'Doble de prueba'}), \
             patch.object(jarvis.marcas, 'partir_objetivo', return_value=partes), \
             patch.object(jarvis.marcas, 'decidir_accion', side_effect=decidir), \
             patch.object(jarvis.marcas, 'capturar_estado', return_value=estado), \
             patch.object(jarvis.marcas, 'nombre_ventana', return_value='Nota de prueba'), \
             patch.object(jarvis.marcas, 'evidencia_archivos', return_value=[]), \
             patch.object(jarvis.marcas, 'evidencia_copias', return_value=[]), \
             patch.object(jarvis, 'escanear', return_value=escaneo), \
             patch.object(jarvis, 'es_mi_consola', return_value=False), \
             patch.object(jarvis, 'guardar_exito'), patch.object(jarvis.memoria, 'buscar_recetas', return_value=[]), \
             patch.object(jarvis.agente, 'verificar', side_effect=revisiones), \
             patch.object(jarvis, 'avisar') as aviso, patch.object(jarvis, 'esperar_cancelacion', return_value=False), \
             patch.object(jarvis.time, 'sleep'), patch.object(jarvis, 'control'), patch.object(jarvis, 'capa'), \
             patch.object(jarvis.acciones, 'clic', side_effect=AssertionError('No debe operar el escritorio')):
            jarvis.ejecutar('Lee las cantidades y luego dime el resultado', escaneo, 'test')
        resultados = list((Path(carpeta) / 'tareas').glob('*.json'))
        return json.loads(resultados[0].read_text(encoding='utf-8')), prompts, aviso

    def test_lectura_memoria_respuesta_y_cierre_persistente(self):
        propuestas = iter([{'tipo': 'recordar', 'texto': '{"clave":"cantidad","valor":"83"}'},
                           {'tipo': 'siguiente'}, {'tipo': 'decir', 'texto': 'La cantidad leída es 83.'}, {'tipo': 'listo'}])
        ok = {'cumplido': True, 'evidencia': 'Dato observado y respuesta entregada', 'pendiente': ''}
        with tempfile.TemporaryDirectory() as carpeta:
            resultado, prompts, aviso = self.ejecutar(carpeta, ['Lee las cantidades', 'Dime la cantidad'], propuestas, [ok, ok, ok])
            self.assertEqual(resultado['estado'], 'completada')
            self.assertTrue(all(e['estado'] == 'comprobada' for e in resultado['etapas']))
            self.assertEqual(prompts[2]['hechos_observados']['cantidad']['valor'], '83')
            self.assertIn('83', aviso.call_args.args[0])
            self.assertIn('Tarea comprobada', aviso.call_args.args[0])

    def test_verificador_rechaza_primera_etapa_y_no_avanza(self):
        propuestas = iter([{'tipo': 'siguiente'}] * 3)
        no = {'cumplido': False, 'evidencia': '', 'pendiente': 'Falta leer la fuente'}
        with tempfile.TemporaryDirectory() as carpeta:
            resultado, prompts, _ = self.ejecutar(carpeta, ['Lee las cantidades', 'Dime la cantidad'], propuestas, [no] * 3)
            self.assertEqual(resultado['estado'], 'incompleta')
            self.assertTrue(all(p['etapa_activa'] == 1 for p in prompts))

    def test_aclaracion_detiene_la_tarea_y_guarda_la_pregunta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            resultado, _, aviso = self.ejecutar(carpeta, ['Identifica los datos'],
                                               iter([{'tipo': 'preguntar', 'texto': '¿Cuál es la VLAN?'}]), [])
            self.assertEqual(resultado['estado'], 'requiere_datos')
            self.assertIn('¿Cuál es la VLAN?', aviso.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
