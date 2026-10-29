import copy
import unittest
from unittest.mock import patch
from PIL import Image

import agente
import acciones
import marcas
import percepcion_ocr as ocr
import percepcion_visual as visual


class OcrTests(unittest.TestCase):
    def setUp(self):
        self.img = Image.new('RGB', (800, 600), 'white')
        self.dato = {'texto': 'Etiqueta', 'confianza': .98, 'caja': [[10, 20], [70, 20], [70, 40], [10, 40]]}

    def extraer(self, datos=None):
        return ocr.etiquetas(self.img, (100, 50, 700, 550), 99, (-800, 10),
                             detector=lambda img: datos if datos is not None else [self.dato])

    def test_caja_crop_monitor_negativo_y_no_editable(self):
        es, ds, parcial = self.extraer()
        self.assertEqual(es, [('VisualText', 'Etiqueta', -690, 80, -630, 100)])
        self.assertFalse(agente.es_editable(es[0][0]))
        self.assertFalse(ds[es[0]]['editable'])
        self.assertFalse(parcial)
        self.assertTrue(visual.anclaje_vigente(ds[es[0]]['anclaje_visual'], self.img, 99, (-800, 10)))

    def test_rechaza_confianza_cajas_invalidas_y_duplicados(self):
        malos = [dict(self.dato, confianza=.2), dict(self.dato, confianza=float('nan')),
                 dict(self.dato, caja=[[0, 0]]), dict(self.dato, caja=[[-1, 0], [4, 0], [4, 4], [-1, 4]]),
                 dict(self.dato, caja=[[0, 0], [900, 0], [900, 4], [0, 4]])]
        es, _, _ = self.extraer(malos + [self.dato, self.dato])
        self.assertEqual(len(es), 1)

    def test_region_fuera_y_captura_parcial(self):
        with self.assertRaises(ValueError):
            ocr.etiquetas(self.img, (-1, 0, 100, 100), 99)
        _, _, parcial = ocr.etiquetas(self.img, (0, 0, 800, 600), 99,
                                     detector=lambda im: [self.dato], limite=1)
        self.assertTrue(parcial)

    def test_navegacion_exige_revision_positiva(self):
        es, ds, _ = self.extraer()
        estado = {'detalles': {'1': ds[es[0]]}}
        for revision in [{'coincide': False, 'tipo': 'navegacion'}, {'coincide': True, 'tipo': 'confirmacion'},
                         {'coincide': True, 'tipo': 'terminal'}, {'coincide': True, 'tipo': 'desconocido'}]:
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                ocr.revisar_accion({'tipo': 'clic', 'n': 1}, es, estado, self.img, lambda *a: revision)
        r = ocr.revisar_accion({'tipo': 'clic', 'n': 1}, es, estado, self.img,
                              lambda *a: {'coincide': True, 'tipo': 'navegacion'})
        self.assertTrue(r['coincide'])

    def test_no_teclas_escritura_scroll_ni_clic_sin_anclaje(self):
        for tipo in ['tecla', 'escribir', 'desplazar', 'recordar', 'importar_plan', 'siguiente']:
            with self.subTest(tipo=tipo), self.assertRaises(ValueError):
                ocr.revisar_accion({'tipo': tipo}, [], {}, self.img, None)
        es, _, _ = self.extraer()
        with self.assertRaises(ValueError):
            ocr.revisar_accion({'tipo': 'clic', 'n': 1}, es, {}, self.img, None)

    def test_anclajes_no_consumen_prompt_ni_falsean_cambio(self):
        es, ds, _ = self.extraer()
        estado = {'detalles': {'1': ds[es[0]]}}
        controles = agente.controles_para('Lee', es, detalles=estado['detalles'])
        self.assertNotIn('anclaje_visual', controles[0])
        otro = copy.deepcopy(estado)
        otro['detalles']['1']['anclaje_visual']['creado'] += 3
        otro['detalles']['1']['revision_visual'] = {'coincide': True}
        self.assertEqual(agente.huella(estado, es), agente.huella(otro, es))

    def test_destino_visual_sin_revision_nunca_se_valida(self):
        es, ds, _ = self.extraer()
        with patch.dict(marcas.DETALLES_UI, ds, clear=True), patch.object(marcas, 'grab') as grab:
            self.assertFalse(marcas.validar_destino(es[0]))
            grab.assert_not_called()

    def test_accion_no_soportada_se_replanifica_con_feedback(self):
        es, ds, _ = self.extraer()
        estado = {'detalles': {'1': ds[es[0]]}, 'percepcion_ocr': True}
        propuestas = iter(['DESPLAZAR', 'CLIC'])
        prompts = []
        def consultar(instruccion, prompt, schema, imagen):
            if 'OCR-selected' in instruccion:
                return {'coincide': True, 'tipo': 'navegacion', 'evidencia': 'Etiqueta'}
            prompts.append((prompt, imagen))
            return {'accion': next(propuestas), 'n': 1, 'texto': 'abajo', 'reemplazar': False,
                    'evidencia': 'Observado', 'objetivo_pendiente': 'Abrir vista'}
        a, _, intentos = agente.proponer('Abre la vista Etiqueta', es, estado, [], consultar,
                                        acciones.normalizar_tecla, imagen=self.img)
        self.assertEqual(a['tipo'], 'clic')
        self.assertEqual(intentos, 2)
        self.assertIn('piloto OCR', prompts[1][0])
        self.assertIs(prompts[0][1], self.img)

    def test_revalidacion_real_exige_ventana_imagen_y_revision(self):
        from types import SimpleNamespace
        es, ds, _ = self.extraer()
        ds[es[0]]['revision_visual'] = {'coincide': True, 'tipo': 'navegacion'}
        with patch.dict(marcas.DETALLES_UI, ds, clear=True), \
             patch.dict(marcas.MONITOR, {'left': -800, 'top': 10}, clear=True), \
             patch.object(marcas.auto, 'GetForegroundControl', return_value=SimpleNamespace(NativeWindowHandle=99)), \
             patch.object(marcas, 'grab', return_value=self.img):
            self.assertTrue(marcas.validar_destino(es[0], 99))
            self.assertFalse(marcas.validar_destino(es[0], 100))
            with patch.object(marcas, 'grab', return_value=Image.new('RGB', self.img.size, 'black')):
                self.assertFalse(marcas.validar_destino(es[0], 99))

    def test_respuesta_visual_sin_respaldo_se_rechaza(self):
        with self.assertRaisesRegex(ValueError, 'sin respaldo'):
            ocr.revisar_accion({'tipo': 'decir', 'texto': 'Valor inventado'}, [], {}, self.img,
                               lambda *a: {'respaldada': False, 'problema': 'Columna cortada'})
        with self.assertRaisesRegex(ValueError, 'sin respaldo'):
            ocr.revisar_accion({'tipo': 'decir', 'texto': 'Contradictorio'}, [], {}, self.img,
                               lambda *a: {'respaldada': True, 'problema': 'Asociación incorrecta'})

    def test_lectura_parcial_verificada_se_registra(self):
        a = {'tipo': 'decir', 'texto': 'La columna aparece cortada; falta consultar la otra vista.'}
        ocr.revisar_accion(a, [], {}, self.img, lambda *a: {'respaldada': True, 'problema': ''})
        self.assertTrue(a['_revision_lectura']['respaldada'])

    def test_etiquetas_de_cambio_no_dependen_del_revisor(self):
        for etiqueta in ['Apply', 'Guardar borrador', 'Remove', 'New Terminal', 'Login', 'Disable']:
            e = [('VisualText', etiqueta, 10, 20, 70, 40)]
            with self.subTest(etiqueta=etiqueta), self.assertRaisesRegex(ValueError, 'fuera del piloto'):
                ocr.revisar_accion({'tipo': 'clic', 'n': 1}, e, {}, self.img,
                                   lambda *a: self.fail('El modelo no puede anular el bloqueo de etiquetas'))

    def test_adaptaciones_del_controlador_no_saltan_la_politica(self):
        estado = {'percepcion_ocr': True, 'archivos_observados': [], 'copias_observadas': []}
        for tipo in ['importar_plan', 'siguiente', 'recordar']:
            with self.subTest(tipo=tipo), \
                 patch.object(agente, 'proponer', return_value=({'tipo': tipo, 'texto': 'dato'}, {}, 0)), \
                 patch.object(marcas, 'cargar_notas', return_value=''), \
                 patch.object(marcas, 'ayuda_aplicacion', return_value={}):
                accion, _, _, _, _ = marcas.decidir_accion('Consulta', self.img, 'Ventana', [], [], estado=estado)
                self.assertEqual(accion['tipo'], 'nada')


if __name__ == '__main__':
    unittest.main()
