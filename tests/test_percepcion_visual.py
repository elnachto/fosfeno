import copy
import unittest
from unittest.mock import patch

from PIL import Image
import percepcion_visual as v


class VisionTests(unittest.TestCase):
    def test_geometria_de_celda_no_depende_de_la_app(self):
        self.assertEqual(v.limites_celda((10, 20, 810, 620), 'B2', 8, 6), (110, 120, 210, 220))
        for celda in ['I1', 'A0', '', 'A7']:
            with self.subTest(celda=celda), self.assertRaises(ValueError):
                v.limites_celda((0, 0, 800, 600), celda, 8, 6)

    def test_recorte_respeta_limites_en_bordes(self):
        self.assertEqual(v.ampliar((0, 0, 100, 100), (0, 0, 800, 600)), (0, 0, 150, 150))
        self.assertEqual(v.ampliar((700, 500, 800, 600), (0, 0, 800, 600)), (650, 450, 800, 600))

    def test_rejilla_y_marca_no_modifican_la_captura(self):
        img = Image.new('RGB', (800, 600), 'white')
        antes = img.tobytes()
        self.assertEqual(v.dibujar_rejilla(img, 8, 6).size, img.size)
        self.assertNotEqual(v.senalar(img, (50, 50)).tobytes(), antes)
        self.assertEqual(img.tobytes(), antes)

    def test_ausencia_detiene_sin_crear_punto(self):
        llamadas = []
        def consulta(*args):
            llamadas.append(args)
            return {'visible': False, 'celda': '', 'evidencia': 'Ausente'}
        r = v.localizar(Image.new('RGB', (800, 600)), 'Botón inexistente', consulta)
        self.assertFalse(r['encontrado'])
        self.assertNotIn('punto_local', r)
        self.assertEqual(len(llamadas), 1)

    def test_refinamiento_y_revision_separada(self):
        respuestas = iter([{'visible': True, 'celda': 'A2', 'evidencia': 'Observado'},
                           {'visible': True, 'celda': 'B4', 'evidencia': 'Observado'},
                           {'visible': True, 'celda': 'C5', 'evidencia': 'Observado'},
                           {'coincide': True, 'tipo': 'navegacion', 'evidencia': 'Dentro'}])
        r = v.localizar(Image.new('RGB', (1920, 1080)), 'Etiqueta', lambda *a: next(respuestas))
        self.assertTrue(r['encontrado'])
        self.assertEqual(len(r['pasos']), 3)
        self.assertLess(r['celda_final'][2] - r['celda_final'][0], 20)
        self.assertLess(r['celda_final'][3] - r['celda_final'][1], 20)

    def test_revisor_puede_rechazar_celda_localizada(self):
        def consulta(instruccion, *args):
            return ({'coincide': False, 'tipo': 'desconocido', 'evidencia': 'Punto fuera'}
                    if 'Review' in instruccion else {'visible': True, 'celda': 'A1', 'evidencia': 'Algo'})
        self.assertFalse(v.localizar(Image.new('RGB', (800, 600)), 'Etiqueta', consulta)['encontrado'])

    def test_anclaje_rechaza_cambio_de_ventana_monitor_tamano_y_tiempo(self):
        img = Image.new('RGB', (800, 600), 'white')
        a = v.anclar(img, (100, 100), 10, (-800, 0))
        self.assertTrue(v.anclaje_vigente(a, img, 10, (-800, 0)))
        self.assertFalse(v.anclaje_vigente(a, img, 11, (-800, 0)))
        self.assertFalse(v.anclaje_vigente(a, img, 10, (0, 0)))
        self.assertFalse(v.anclaje_vigente(a, Image.new('RGB', (400, 300)), 10, (-800, 0)))
        viejo = copy.deepcopy(a); viejo['creado'] -= 100
        self.assertFalse(v.anclaje_vigente(viejo, img, 10, (-800, 0)))

    def test_anclaje_rechaza_cambio_del_destino_y_datos_rotos(self):
        img = Image.new('RGB', (800, 600), 'white')
        a = v.anclar(img, (100, 100), 10)
        self.assertFalse(v.anclaje_vigente(a, Image.new('RGB', img.size, 'black'), 10))
        self.assertFalse(v.anclaje_vigente({'hwnd': 10}, img, 10))
        with self.assertRaises(ValueError):
            v.anclar(img, (-1, 20), 10)


if __name__ == '__main__':
    unittest.main()
