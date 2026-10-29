import copy
import random
import unittest

import lectura_visual as l
from PIL import Image


class LecturaTests(unittest.TestCase):
    def setUp(self):
        self.refs = {}
        for n, texto, r in [
                (1, 'Inventario', [100, 20, 200, 40]),
                (2, 'Artículo', [110, 80, 180, 100]), (3, 'Depósito', [300, 80, 370, 100]),
                (4, 'Carpetas', [110, 120, 180, 140]), (5, 'Norte', [300, 120, 345, 140]),
                (6, 'Sobres', [110, 150, 165, 170]), (7, 'Sur', [300, 150, 330, 170]),
                (8, 'Stock', [210, 80, 260, 100]), (9, '28', [210, 120, 230, 140]),
                (10, 'Archivo', [105, 180, 170, 200])]:
            self.refs[n] = {'id': n, 'texto': texto, 'rect': r}
        self.dato = {'tablas': [{'contexto': 1, 'encabezados': [2, 3], 'filas': [[4, 5], [6, 7]]}], 'fragmentos': []}

    def test_relaciones_de_celdas_se_renderizan_literalmente(self):
        r = l.reconstruir(self.dato, self.refs)
        self.assertIn('«Artículo» = «Carpetas»; «Depósito» = «Norte»', r['texto'])
        self.assertIn('«Artículo» = «Sobres»; «Depósito» = «Sur»', r['texto'])
        self.assertEqual(r['tablas'], self.dato['tablas'])

    def test_mismo_algoritmo_con_desplazamiento_escala_e_ids_barajados(self):
        # No son tareas del modelo: comprueban que la geometría no depende de
        # píxeles concretos ni de identificadores constantes de una aplicación.
        for semilla in range(12):
            rng = random.Random(semilla)
            ids = list(range(101, 111)); rng.shuffle(ids)
            mapa = dict(zip(self.refs, ids))
            escala, dx, dy = rng.uniform(.7, 2.2), rng.randint(0, 900), rng.randint(0, 600)
            refs = {mapa[n]: {'id': mapa[n], 'texto': 'Dato '+str(n),
                              'rect': [r['rect'][0]*escala+dx, r['rect'][1]*escala+dy,
                                       r['rect'][2]*escala+dx, r['rect'][3]*escala+dy]}
                    for n, r in self.refs.items()}
            d = {'tablas': [{'contexto': mapa[1], 'encabezados': [mapa[2], mapa[3]],
                             'filas': [[mapa[4], mapa[5]], [mapa[6], mapa[7]]]}], 'fragmentos': []}
            with self.subTest(semilla=semilla):
                self.assertIn('«Dato 2» = «Dato 4»', l.reconstruir(d, refs)['texto'])

    def test_rechaza_mezcla_entre_filas_aunque_ambos_valores_existan(self):
        self.dato['tablas'][0]['filas'] = [[4, 7]]
        with self.assertRaisesRegex(ValueError, 'filas diferentes'):
            l.reconstruir(self.dato, self.refs)

    def test_no_saltea_encabezados_intermedios_no_seleccionados(self):
        self.dato['tablas'][0]['filas'] = [[9, 5]]
        with self.assertRaisesRegex(ValueError, 'columna'):
            l.reconstruir(self.dato, self.refs)

    def test_un_menu_bajo_los_encabezados_no_es_contexto_de_la_tabla(self):
        self.dato['tablas'][0]['contexto'] = 10
        with self.assertRaisesRegex(ValueError, 'contexto'):
            l.reconstruir(self.dato, self.refs)

    def test_contexto_de_panel_lejano_no_se_une_a_la_tabla(self):
        self.refs[1]['rect'] = [800, 20, 900, 40]
        with self.assertRaisesRegex(ValueError, 'contexto'):
            l.reconstruir(self.dato, self.refs)

    def test_no_inventa_texto_cortado_ni_valores_completos(self):
        self.refs[4]['texto'] = 'AB-29…'
        r = l.reconstruir(self.dato, self.refs)
        self.assertIn('«AB-29…» (texto cortado; valor completo desconocido)', r['texto'])
        self.assertEqual(r['referencias_truncadas'], [4])

    def test_no_acepta_booleano_de_confianza_sin_referencias(self):
        with self.assertRaisesRegex(ValueError, 'referencias estructuradas'):
            l.reconstruir({'respaldada': True, 'problema': ''}, self.refs)

    def test_rechaza_ids_ausentes_reutilizados_o_encabezados_incorrectos(self):
        for cambio in [dict(contexto=999), dict(encabezados=[3, 2]), dict(encabezados=[2, 2]),
                       dict(filas=[[4, 4]]), dict(filas=[[4, 5], [4, 5]]), dict(filas=[[True, 5]]),
                       dict(filas=[[2, 5]]), dict(filas=[[4, 999]])]:
            d = copy.deepcopy(self.dato); d['tablas'][0].update(cambio)
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                l.reconstruir(d, self.refs)

    def test_fragmentos_no_se_presentan_como_relaciones(self):
        r = l.reconstruir({'tablas': [], 'fragmentos': [4, 7]}, self.refs)
        self.assertIn('sin relación de tabla comprobada', r['texto'])
        self.assertFalse(r['tablas'])

    def test_fila_multilinea_y_encabezado_desalineado_se_rechazan(self):
        self.refs[5]['rect'] = [300, 120, 345, 165]
        with self.assertRaises(ValueError):
            l.reconstruir(self.dato, self.refs)
        self.setUp(); self.refs[3]['rect'] = [300, 110, 370, 130]
        with self.assertRaisesRegex(ValueError, 'encabezados'):
            l.reconstruir(self.dato, self.refs)

    def test_candidatas_no_duplican_celdas_con_dos_contextos(self):
        self.refs[11] = {'id': 11, 'texto': 'Otra etiqueta', 'rect': [105, 45, 205, 65]}
        cs = l.candidatas(self.refs, 'Lee Inventario')
        estructuras = [(tuple(c['referencias']['encabezados']),
                        tuple(tuple(f) for f in c['referencias']['filas'])) for c in cs.values()]
        self.assertTrue(estructuras)
        self.assertEqual(len(estructuras), len(set(estructuras)))
        relacionadas = [c for c in cs.values() if c['referencias']['encabezados'] == [2, 8, 3]]
        self.assertTrue(relacionadas)
        self.assertEqual(relacionadas[0]['referencias']['contexto'], 1)

    def test_lector_no_acepta_id_de_tabla_inventado(self):
        es = [('VisualText', r['texto'], *r['rect']) for r in self.refs.values()]
        estado = {'detalles': {str(n): {'rect_visual': r['rect']} for n, r in self.refs.items()}}
        with self.assertRaisesRegex(ValueError, 'Tabla candidata inexistente'):
            l.leer('Todo es correcto', es, estado, Image.new('RGB', (1000, 600)),
                   lambda *a: {'tabla': 9999, 'texto1': 0, 'texto2': 0, 'texto3': 0}, 'Lee Inventario')

    def test_lector_reconstruye_y_descarta_el_texto_libre(self):
        es = [('VisualText', r['texto'], *r['rect']) for r in self.refs.values()]
        estado = {'detalles': {str(n): {'rect_visual': r['rect']} for n, r in self.refs.items()}}
        cs = l.candidatas(self.refs, 'Lee Inventario')
        n = next(n for n, c in cs.items() if c['referencias']['encabezados'] == [2, 8, 3])
        r = l.leer('Valor inventado que no aparece', es, estado, Image.new('RGB', (1000, 600)),
                   lambda *a: {'tabla': n, 'texto1': 0, 'texto2': 0, 'texto3': 0}, 'Lee Inventario')
        self.assertNotIn('inventado', r['texto'])
        self.assertIn('«Stock» = «28»', r['texto'])
