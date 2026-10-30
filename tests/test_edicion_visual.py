import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image

import acciones
import agente
import marcas
import percepcion_ocr as ocr
import percepcion_visual as visual
import precondiciones


class EdicionVisualTests(unittest.TestCase):
    def setUp(self):
        self.img = Image.new('RGB', (800, 600), 'white')
        self.estado = {'hwnd': 99, 'raiz_edicion_visual': 99, 'edicion_visual': True,
                       'percepcion_ocr': True, 'capturado_en': time.monotonic(),
                       'foco': {'n': None, 'rol': 'Window', 'editable': False}, 'detalles': {}}

    def test_escritura_visual_no_inventa_foco_uia_y_se_admite_en_lab(self):
        d = {'accion': 'ESCRIBIR', 'n': 0, 'texto': '192.168.50.61', 'reemplazar': True,
             'evidencia': 'Entrada enfocada en la imagen', 'objetivo_pendiente': 'Rellenar dirección'}
        def consultar(sistema, *args):
            return {'confirmado': True, 'secreto': False, 'evidencia': 'Borde de foco'} if 'Verify keyboard focus' in sistema else d
        a, _, _ = agente.proponer('Escribe 192.168.50.61', [], self.estado, [], consultar,
                                  acciones.normalizar_tecla, imagen=self.img)
        self.assertEqual(a['tipo'], 'escribir')
        self.assertIn('_escritura_visual', a)
        self.assertFalse(self.estado['foco']['editable'])
        self.assertIn('no verificado por UIA', a['_escritura_visual']['foco'])

    def test_sin_vinculo_imagen_o_con_clave_no_se_escribe(self):
        for estado, imagen in [(dict(self.estado, raiz_edicion_visual=0), self.img),
                               (self.estado, None),
                               (dict(self.estado, foco={'secreto': True}), self.img)]:
            with self.subTest(estado=estado), self.assertRaises(ValueError):
                ocr.revisar_accion({'tipo': 'escribir', 'texto': 'abc'}, [], estado, imagen, None)

    def test_escritura_con_id_visual_se_adapta_a_clic_y_continuacion(self):
        e = ('VisualText', '0.0.0.0', 100, 100, 160, 120)
        self.estado['detalles'] = {'1': {'anclaje_visual': visual.anclar(self.img, (130, 110), 99)}}
        d = {'accion': 'ESCRIBIR', 'n': 1, 'texto': '192.168.50.61', 'reemplazar': True,
             'evidencia': 'Rellenar dirección', 'objetivo_pendiente': 'Rellenar dirección'}
        def consultar(sistema, *args):
            if 'OCR-selected' in sistema:
                return {'coincide': True, 'tipo': 'campo', 'evidencia': 'Valor de una entrada'}
            if 'Verify keyboard focus' in sistema:
                return {'confirmado': True, 'secreto': False, 'evidencia': 'Foco en la región pedida'}
            return d
        a, _, _ = agente.proponer('Escribe 192.168.50.61', [e], self.estado, [], consultar,
                                  acciones.normalizar_tecla, imagen=self.img)
        self.assertEqual(a['tipo'], 'clic')
        siguiente = agente.continuar_pendiente(a['_despues'], self.estado, [e], self.img, consultar)
        self.assertEqual(siguiente['texto'], '192.168.50.61')
        self.assertIn('_escritura_visual', siguiente)
        self.assertIsNone(agente.continuar_pendiente(a['_despues'], dict(self.estado, hwnd=100), [e]))
        self.assertIsNone(agente.continuar_pendiente(a['_despues'], self.estado, []))
        with self.assertRaises(ValueError):
            agente.convertir(d, [e], acciones.normalizar_tecla)

    def test_etiqueta_no_autoriza_escribir_y_foco_ajeno_no_continua(self):
        e = ('VisualText', 'Address', 100, 100, 160, 120)
        self.estado['detalles'] = {'1': {'anclaje_visual': visual.anclar(self.img, (130, 110), 99)}}
        with self.assertRaises(ValueError):
            ocr.revisar_accion({'tipo': 'escribir', 'n': 1, 'texto': 'abc'}, [e], self.estado, self.img,
                              lambda *a: {'coincide': True, 'tipo': 'desconocido'})
        pendiente = {'_destino_visual': e, '_raiz_visual': 99, 'texto': 'abc'}
        self.assertIsNone(agente.continuar_pendiente(pendiente, self.estado, [e], self.img,
                          lambda *a: {'confirmado': False, 'secreto': False, 'evidencia': 'Otro campo'}))
        with self.assertRaises(ValueError):
            ocr.revisar_accion({'tipo': 'escribir', 'n': 0, 'texto': 'abc'}, [e], self.estado, self.img,
                              lambda *a: {'confirmado': False, 'secreto': False})

    def test_nuevo_y_confirmacion_se_permiten_solo_con_edicion(self):
        e = ('VisualText', 'New', 100, 100, 160, 120)
        self.estado['detalles'] = {'1': {'anclaje_visual': visual.anclar(self.img, (130, 110), 99)}}
        r = ocr.revisar_accion({'tipo': 'clic', 'n': 1}, [e], self.estado, self.img,
                               lambda *a: {'coincide': True, 'tipo': 'campo', 'evidencia': 'Formulario'})
        self.assertEqual(r['tipo'], 'campo')
        with self.assertRaises(ValueError):
            ocr.revisar_accion({'tipo': 'clic', 'n': 1}, [e], dict(self.estado, edicion_visual=False), self.img, None)

    def test_ids_internos_no_se_piden_al_usuario(self):
        with self.assertRaises(ValueError):
            ocr.revisar_accion({'tipo': 'preguntar', 'texto': '¿Cuál es el ID del campo de entrada?'},
                              [], self.estado, self.img, None)
        ocr.revisar_accion({'tipo': 'preguntar', 'texto': '¿Qué IP necesita el dispositivo?'},
                          [], self.estado, self.img, None)

    def test_observacion_visual_no_sustituye_foco_uia_y_requiere_revision(self):
        e = ('VisualText', 'abc', 100, 100, 160, 120)
        def consultar(sistema, *args):
            if 'Observe keyboard focus' in sistema:
                return {'n': 1, 'evidencia': 'Borde visible'}
            return {'confirmado': False, 'secreto': False, 'evidencia': 'La región es etiqueta'}
        r = ocr.observar_foco(self.img, [e], self.estado, consultar)
        self.assertFalse(r['confirmado'])
        self.assertFalse(self.estado['foco']['editable'])
        self.assertEqual(r['n_region_ocr'], 1)

    def test_observador_no_acepta_region_inventada_ni_marco(self):
        for n in (0, 2, True):
            self.assertFalse(ocr.observar_foco(self.img, [('Window', 'Marco', 0, 0, 400, 300),
                              ('VisualText', 'abc', 100, 100, 160, 120)], self.estado,
                              lambda *a: {'n': n, 'confirmado': False})['confirmado'])

    def test_cobertura_incluye_regiones_inferiores_sin_agotar_contexto(self):
        elementos = [('VisualText', 'texto visible '+str(n), 100, n*2, 200, n*2+1) for n in range(1, 201)]
        elementos[-1] = ('VisualText', 'Apply', 100, 500, 150, 520)
        prompts = []
        def consultar(sistema, prompt, *args):
            prompts.append(prompt)
            return {'accion': 'NADA', 'n': 0, 'texto': '', 'evidencia': 'Detener', 'objetivo_pendiente': ''}
        with patch.object(ocr, 'observar_foco', return_value={'confirmado': False}):
            agente.proponer('Revisa el formulario', elementos, self.estado, [], consultar,
                            acciones.normalizar_tecla, imagen=self.img)
        self.assertIn('"id":200', prompts[-1])
        self.assertIn('Apply', prompts[-1])
        self.assertLessEqual(len(prompts[-1]), agente.MAX_PROMPT_CARACTERES)

    def test_borrar_y_autenticacion_siguen_fuera_de_la_tarea(self):
        for texto in ['Remove', 'Login', 'New Terminal']:
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                ocr.revisar_accion({'tipo': 'clic', 'n': 1}, [('VisualText', texto, 0, 0, 30, 20)],
                                   self.estado, self.img, None)

    def test_region_de_valor_sin_tipo_de_widget_se_puede_pulsar_en_lab(self):
        e = ('VisualText', '0.0.0.0', 100, 100, 160, 120)
        self.estado['detalles'] = {'1': {'anclaje_visual': visual.anclar(self.img, (130, 110), 99)}}
        r = ocr.revisar_accion({'tipo': 'clic', 'n': 1}, [e], self.estado, self.img,
                               lambda *a: {'coincide': True, 'tipo': 'desconocido', 'evidencia': 'Valor visible'})
        self.assertEqual(r['tipo'], 'desconocido')
        with self.assertRaises(ValueError):
            ocr.revisar_accion({'tipo': 'clic', 'n': 1}, [e], dict(self.estado, edicion_visual=False), self.img,
                               lambda *a: {'coincide': True, 'tipo': 'desconocido'})

    def test_confirmacion_visual_pasa_por_revisor_de_formulario(self):
        es = [('VisualText', 'Apply', 0, 0, 50, 20)]
        self.assertTrue(precondiciones.es_envio({'tipo': 'clic', 'n': 1}, es, self.estado))
        self.assertFalse(precondiciones.es_envio({'tipo': 'clic', 'n': 1}, es, {}))

    def test_escritura_se_revalida_por_ventana_y_antiguedad(self):
        a = {'_escritura_visual': {'hwnd': 99, 'raiz': 99, 'capturado_en': time.monotonic(),
                                  'revision_foco': {'confirmado': True, 'secreto': False}}}
        with patch.dict(marcas.PERFIL, {'ventana_edicion_visual': 99}), \
             patch.object(marcas, 'ventana_edicion_autorizada', return_value=True), \
             patch.object(marcas.auto, 'GetForegroundControl', return_value=SimpleNamespace(NativeWindowHandle=99)):
            self.assertTrue(marcas.validar_escritura_visual(a, 99))
            self.assertFalse(marcas.validar_escritura_visual(a, 100))
            a['_escritura_visual']['capturado_en'] -= 100
            self.assertFalse(marcas.validar_escritura_visual(a, 99))

    def test_teclas_de_formulario_sin_atajos_a_otras_apps(self):
        ocr.revisar_accion({'tipo': 'tecla', 'tecla': 'tab'}, [], self.estado, self.img, None)
        with self.assertRaises(ValueError):
            ocr.revisar_accion({'tipo': 'tecla', 'tecla': 'ctrl+l'}, [], self.estado, self.img, None)

    def test_vinculo_exige_titulo_y_ventana_o_propietario(self):
        def texto(hwnd, buf, limite):
            buf.value = 'Laboratorio propio'
            return len(buf.value)
        def propietario(hwnd, modo):
            return 99 if hwnd.value == 100 else 0
        with patch.dict(marcas.PERFIL, {'edicion_visual': True, 'ventana_edicion_visual': 99,
                                       'titulo_edicion_visual': 'Laboratorio propio'}), \
             patch.object(marcas.ctypes.windll.user32, 'GetWindowTextW', side_effect=texto), \
             patch.object(marcas.ctypes.windll.user32, 'GetWindow', side_effect=propietario):
            self.assertTrue(marcas.ventana_edicion_autorizada(99))
            self.assertTrue(marcas.ventana_edicion_autorizada(100))
            self.assertFalse(marcas.ventana_edicion_autorizada(101))
            with patch.dict(marcas.PERFIL, {'titulo_edicion_visual': 'Otra sesión'}):
                self.assertFalse(marcas.ventana_edicion_autorizada(99))


if __name__ == '__main__':
    unittest.main()
