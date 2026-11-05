import tempfile
import unittest
from unittest.mock import patch

import acciones
import agente
import evaluacion
import marcas
from entornos_evaluacion import EscritorioSimulado, pregunta_correcta, sin_entrada_nativa
from interacciones_evaluacion import ejecutar_interaccion


class ArnesAmpliadoTests(unittest.TestCase):
    def caso(self, nombre):
        return next(c for c in evaluacion.CASOS if c['id'] == nombre)

    def clic(self, app, clave):
        app.observar()
        app.aplicar({'tipo': 'clic', 'n': app.mapa.index(clave) + 1})

    def test_veinte_objetivos_distintos_y_ocho_originales(self):
        self.assertEqual(len(evaluacion.CASOS), 20)
        self.assertEqual(len({c['id'] for c in evaluacion.CASOS}), 20)
        self.assertEqual(len({c['objetivo'] for c in evaluacion.CASOS}), 20)
        self.assertEqual(evaluacion.CASOS[:8], evaluacion.CASOS_ORIGINALES)

    def test_inicio_requiere_consulta_envio_y_ventana_realizada(self):
        app = EscritorioSimulado(self.caso('app_inicio'), 42)
        app.aplicar({'tipo': 'tecla', 'tecla': 'win'})
        app.aplicar({'tipo': 'escribir', 'texto': 'Configuración'})
        self.assertFalse(app.cumplida())
        app.aplicar({'tipo': 'tecla', 'tecla': 'enter'})
        self.assertFalse(app.cumplida())
        app.aplicar({'tipo': 'esperar'})
        self.assertTrue(app.cumplida())

    def test_abrir_carpeta_existente_no_satisface_crear_otra(self):
        app = EscritorioSimulado(self.caso('carpeta_escritorio'), 42)
        self.clic(app, 'Informe mensual')
        self.assertFalse(app.cumplida())
        app = EscritorioSimulado(self.caso('carpeta_escritorio'), 42)
        app.aplicar({'tipo': 'tecla', 'tecla': 'ctrl+shift+n'})
        app.aplicar({'tipo': 'escribir', 'texto': 'Informe semanal'})
        self.assertFalse(app.cumplida())
        app.aplicar({'tipo': 'tecla', 'tecla': 'enter'})
        self.assertTrue(app.cumplida())

    def test_botones_calculan_y_guardar_preserva_el_resultado(self):
        app = EscritorioSimulado(self.caso('calculo_botones'), 42)
        for clave in ['3', '7', '+', '2', '5', '=']:
            self.clic(app, clave)
        self.assertEqual(app.resultado_calculo, '62')
        self.assertFalse(app.cumplida())
        self.clic(app, 'ir_nota')
        self.clic(app, 'cuerpo')
        app.aplicar({'tipo': 'escribir', 'texto': '62'})
        self.assertFalse(app.cumplida())
        self.clic(app, 'guardar')
        self.assertTrue(app.cumplida())

    def test_adivinar_resultado_sin_operacion_no_pasa(self):
        app = EscritorioSimulado(self.caso('calculo_teclado'), 42)
        self.clic(app, 'ir_nota')
        self.clic(app, 'cuerpo')
        app.aplicar({'tipo': 'escribir', 'texto': '1000'})
        self.clic(app, 'guardar')
        self.assertFalse(app.cumplida())

    def test_regresar_sin_guardar_o_sin_marcar_no_pasa(self):
        app = EscritorioSimulado(self.caso('nota_y_regreso'), 42)
        self.clic(app, 'ir_destino')
        self.clic(app, 'cuerpo')
        app.aplicar({'tipo': 'escribir', 'texto': '417'})
        self.clic(app, 'guardar')
        self.assertFalse(app.cumplida())
        self.clic(app, 'ir_fuente')
        self.clic(app, 'revisado')
        self.assertTrue(app.cumplida())

    def test_editor_exige_nada_y_cero_efectos(self):
        app = EscritorioSimulado(self.caso('editor_inaccesible'), 42)
        app.detener({'tipo': 'listo'})
        self.assertFalse(app.cumplida())
        app.detener({'tipo': 'nada'})
        self.assertTrue(app.cumplida())

    def test_oraculos_de_pregunta_no_premian_respuestas_contradictorias(self):
        self.assertTrue(pregunta_correcta(self.caso('pregunta_importe'), 'El total es 148,50 BOB.'))
        self.assertFalse(pregunta_correcta(self.caso('pregunta_importe'), 'El total es 149,50 BOB.'))
        self.assertTrue(pregunta_correcta(self.caso('pregunta_estado'), 'Está pendiente; no está confirmado.'))
        self.assertFalse(pregunta_correcta(self.caso('pregunta_estado'), 'Está confirmado, aunque pendiente.'))

    def test_guardia_no_permite_input_nativo(self):
        with sin_entrada_nativa():
            for funcion, args in [(acciones.clic, (1, 1)), (acciones.escribir, ('texto',)), (acciones.tecla, ('win',)), (acciones.mover_suave, (1, 1))]:
                with self.assertRaises(AssertionError):
                    funcion(*args)
            for nombre in ('SendInput', 'SetCursorPos', 'mouse_event'):
                with self.assertRaises(AssertionError):
                    getattr(acciones.user32, nombre)(0, 0, 0)

    def test_confirmacion_de_guia_ejecuta_solo_archivo_en_memoria(self):
        caso = self.caso('guia_un_clic')
        app = EscritorioSimulado(caso, 42)
        app.observar()
        numero = app.mapa.index('archivo') + 1
        with tempfile.TemporaryDirectory() as carpeta, patch.object(marcas, 'OUT', carpeta), \
             patch.object(marcas, 'preguntar', return_value='RESPUESTA: ' + str(numero)):
            r = ejecutar_interaccion(caso, 'nemotron', 42)
        self.assertTrue(r['correcto'], r['motivo'])
        self.assertEqual(r['pasos'], 2)
        self.assertEqual(r['estado_final']['ejecuciones'], 1)
