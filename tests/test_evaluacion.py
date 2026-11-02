import unittest
from evaluacion import AplicacionSimulada, CASOS


class EntornoEvaluacionTests(unittest.TestCase):
    def caso(self, nombre):
        return next(c for c in CASOS if c['id'] == nombre)

    def clic(self, app, nombre):
        elementos, _ = app.observar()
        n = next(i for i, e in enumerate(elementos, 1) if e[1] == nombre)
        app.aplicar({'tipo': 'clic', 'n': n})

    def test_no_hay_exito_por_afirmacion(self):
        app = AplicacionSimulada(self.caso('nota'), 42)
        self.assertFalse(app.cumplida())
        self.assertIsNone(app.enviado)

    def test_nota_completa_requiere_guardar(self):
        app = AplicacionSimulada(self.caso('nota'), 42)
        self.clic(app, 'Cuerpo de la nota')
        app.aplicar({'tipo': 'escribir', 'texto': 'Revisar inventario mañana'})
        self.assertFalse(app.cumplida())
        self.clic(app, 'Guardar borrador')
        self.assertTrue(app.cumplida())

    def test_texto_equivocado_guardado_es_fallo(self):
        app = AplicacionSimulada(self.caso('nota'), 42)
        self.clic(app, 'Cuerpo de la nota')
        app.aplicar({'tipo': 'escribir', 'texto': 'Texto incorrecto'})
        self.clic(app, 'Guardar borrador')
        self.assertFalse(app.cumplida())

    def test_chat_borrador_no_es_envio(self):
        app = AplicacionSimulada(self.caso('chat'), 42)
        self.clic(app, 'Nueva conversación')
        app.aplicar({'tipo': 'escribir', 'texto': 'Llegaré a las 18:45'})
        self.assertFalse(app.cumplida())
        self.clic(app, 'Enviar mensaje')
        self.assertTrue(app.cumplida())

    def test_navegacion_exige_pestana_nueva(self):
        app = AplicacionSimulada(self.caso('navegacion'), 42)
        self.clic(app, 'Barra de direcciones y de búsqueda')
        app.aplicar({'tipo': 'escribir', 'texto': 'https://example.org/manual', 'reemplazar': True})
        app.aplicar({'tipo': 'tecla', 'tecla': 'enter'})
        self.assertFalse(app.cumplida())

    def test_busqueda_requiere_esperar_resultado(self):
        app = AplicacionSimulada(self.caso('busqueda'), 42)
        self.clic(app, 'Buscar documentos')
        app.aplicar({'tipo': 'escribir', 'texto': 'factura 072'})
        self.clic(app, 'Buscar')
        self.assertFalse(app.cumplida())
        app.aplicar({'tipo': 'esperar'})
        self.assertTrue(app.cumplida())

    def test_selector_expone_opciones_al_abrir(self):
        app = AplicacionSimulada(self.caso('selector'), 42)
        self.clic(app, 'Idioma')
        elementos, _ = app.observar()
        self.assertIn(('ListItem', 'Español'), [e[:2] for e in elementos])
        self.clic(app, 'Español')
        self.clic(app, 'Guardar selección')
        self.assertTrue(app.cumplida())


if __name__ == '__main__': unittest.main()
