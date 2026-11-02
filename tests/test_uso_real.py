import time
import unittest
from unittest.mock import MagicMock, patch

import acciones
import agente
import jarvis
import marcas


class UsoRealTests(unittest.TestCase):
    def test_abrir_configuracion_sin_control_inicia_busqueda_sin_consulta(self):
        consultar = MagicMock(side_effect=AssertionError('No necesita consultar para abrir la búsqueda'))
        accion, _, consultas = agente.proponer('Abre configuración', [('List', 'Escritorio', 0, 0, 500, 500)],
            {'ventana': 'Program Manager', 'hwnd': 10}, [], consultar, acciones.normalizar_tecla)
        self.assertEqual(accion['tecla'], 'win')
        self.assertEqual(accion['_apertura_aplicacion'], 'configuración')
        self.assertEqual(consultas, 0)

    def test_apertura_no_repite_inicio_ni_suplanta_controles_o_archivos(self):
        self.assertIsNone(agente.apertura_sin_control('Abre configuración', [], {'hwnd': 10, 'ventana': 'Configuración'}, [], []))
        self.assertIsNone(agente.apertura_sin_control('Abre configuración', [('Button', 'Configuración', 0, 0, 20, 20)], {'hwnd': 10}, [], []))
        self.assertIsNone(agente.apertura_sin_control('Abre configuración', [], {'hwnd': 10}, ['pulsé win'], []))
        for pedido in ['Abre https://example.org/manual', 'Abre el menú Archivo', 'Abre C:\\datos', 'Abre prueba.py', 'Abre cmd /c dir']:
            self.assertIsNone(agente.apertura_sin_control(pedido, [], {'hwnd': 10}, [], []), pedido)

    def test_apertura_completa_espera_la_ventana_sin_decir_que_ya_abrio(self):
        traza = []
        def registrar(accion, elementos, estado):
            traza.append({'evento': agente.evento_accion(accion, elementos, estado)})
        escritorio = {'hwnd': 10, 'ventana': 'Program Manager'}
        abrir = agente.apertura_sin_control('Abre configuración', [], escritorio, [], [])
        registrar(abrir, [], escritorio)
        elementos = [('Edit', 'Buscar', 0, 0, 300, 30)]
        buscador = {'hwnd': 11, 'ventana': 'Inicio', 'foco': {'n': 1, 'editable': True, 'valor': ''}}
        escribir = agente.continuar_apertura(elementos, buscador, traza)
        self.assertEqual((escribir['tipo'], escribir['texto']), ('escribir', 'configuración'))
        registrar(escribir, elementos, buscador)
        buscador['foco']['valor'] = 'configuración'
        self.assertEqual(agente.continuar_apertura(elementos, buscador, traza)['tipo'], 'esperar')
        elementos.append(('Button', 'Configuración', 0, 40, 300, 80))
        entrar = agente.continuar_apertura(elementos, buscador, traza)
        self.assertEqual(entrar['tecla'], 'enter')
        registrar(entrar, elementos, buscador)
        esperando = agente.continuar_apertura(elementos, buscador, traza)
        self.assertEqual(esperando['tipo'], 'esperar')
        registrar(esperando, elementos, buscador)
        self.assertIsNone(agente.continuar_apertura([], {'hwnd': 12, 'ventana': 'Configuración'}, traza))
        for _ in range(4):
            registrar(esperando, elementos, buscador)
        self.assertEqual(agente.continuar_apertura(elementos, buscador, traza)['tipo'], 'nada')

    def test_apertura_no_escribe_en_otro_contexto_ni_lanza_resultado_ambiguo(self):
        escritorio = {'hwnd': 10, 'ventana': 'Program Manager'}
        abrir = agente.apertura_sin_control('Abre configuración', [], escritorio, [], [])
        traza = [{'evento': agente.evento_accion(abrir, [], escritorio)}]
        elementos = [('Edit', 'Buscar', 0, 0, 300, 30)]
        otra = {'hwnd': 11, 'ventana': 'Otra aplicación', 'foco': {'n': 1, 'editable': True}}
        self.assertEqual(agente.continuar_apertura(elementos, otra, traza)['tipo'], 'esperar')
        inicio = {**otra, 'ventana': 'Inicio'}
        escribir = agente.continuar_apertura(elementos, inicio, traza)
        traza.append({'evento': agente.evento_accion(escribir, elementos, inicio)})
        inicio['foco']['valor'] = 'configuración'
        elementos.extend([('Button', 'Configuración', 0, 40, 100, 80), ('Button', 'Configuración', 0, 90, 100, 130)])
        self.assertEqual(agente.continuar_apertura(elementos, inicio, traza)['tipo'], 'esperar')

    def test_ayudas_solo_en_sus_ventanas_y_dialogos_word(self):
        escritorio = marcas.ayuda_aplicacion({'clase_ventana': 'Progman', 'ventana': 'Program Manager'})
        self.assertIn('ctrl+shift+n', escritorio)
        calc = {'clase_ventana': 'ApplicationFrameWindow', 'ventana': 'Calculadora'}
        self.assertIn('125*8', marcas.ayuda_aplicacion(calc))
        self.assertTrue(marcas.perfil_aplicacion(calc)['entrada_teclado_directa'])
        self.assertEqual(marcas.ayuda_aplicacion({'clase_ventana': 'Chrome_WidgetWin_1', 'ventana': 'Calculadora'}), '')
        self.assertEqual(marcas.ayuda_aplicacion({'clase_ventana': '#32770', 'ventana': 'Calculadora'}), '')
        self.assertIn('Ctrl+Inicio', marcas.ayuda_aplicacion({'clase_ventana': '#32770', 'clase_aplicacion': 'OpusApp'}))

    def test_operacion_directa_sin_campo_editable_conserva_ventana(self):
        estado = {'hwnd': 10, 'ventana': 'Calculadora', 'clase_ventana': 'ApplicationFrameWindow',
                  'foco': {'n': 1, 'nombre': 'Uno', 'rol': 'Button', 'editable': False}}
        estado['entrada_teclado_directa'] = marcas.perfil_aplicacion(estado)['entrada_teclado_directa']
        propuesta = {'accion': 'ESCRIBIR', 'n': 0, 'texto': '125*8', 'reemplazar': False,
                     'evidencia': 'Calculadora activa', 'objetivo_pendiente': 'Calcular la operación'}
        accion, _, _ = agente.proponer('Calcula 125 por 8', [('Button', 'Uno', 0, 0, 20, 20)],
            estado, [], lambda *args: propuesta.copy(), acciones.normalizar_tecla)
        self.assertEqual(accion['_entrada_teclado_directa'], 10)
        self.assertTrue(marcas.validar_entrada_directa(accion, estado))
        self.assertFalse(marcas.validar_entrada_directa(accion, {**estado, 'hwnd': 11}))
        self.assertFalse(marcas.validar_entrada_directa({**accion, 'texto': '125\n8'}, estado))
        self.assertFalse(marcas.validar_entrada_directa({**accion, 'texto': 'abrir.exe'}, estado))

    def test_directa_no_se_concede_en_una_ventana_sin_perfil(self):
        estado = {'hwnd': 10, 'ventana': 'Otra', 'clase_ventana': 'Otra', 'foco': {}}
        propuesta = {'accion': 'ESCRIBIR', 'n': 0, 'texto': '125*8', 'evidencia': 'Nada', 'objetivo_pendiente': ''}
        accion, _, _ = agente.proponer('Calcula 125 por 8', [], estado, [], lambda *args: propuesta.copy(), acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'nada')

    def test_decir_identico_no_se_repite_tras_otra_accion(self):
        accion = {'tipo': 'decir', 'texto': 'Guardar está en Archivo.'}
        evento = agente.evento_accion(accion, [], {})
        traza = [{'clave': repr(agente.clave_accion(accion, [])), 'evento': evento}, {'clave': 'otra'}]
        self.assertTrue(agente.repetida_sin_progreso(accion, [], traza))
        self.assertFalse(agente.repetida_sin_progreso({'tipo': 'decir', 'texto': 'El resultado es 1000.'}, [], traza))

    def guia(self, ventana=10, elementos=None, hasta=None):
        origen = ('MenuItem', 'Archivo', 0, 0, 30, 20)
        oferta = {'hwnd': 10, 'elemento': origen, 'hasta': hasta if hasta is not None else time.time() + 10,
                  'texto': '¿Dónde se guarda?'}
        imagen = MagicMock(size=(300, 200))
        with patch.object(jarvis, 'escanear', return_value=(imagen, 'Nota', elementos if elementos is not None else [origen])), \
             patch.object(marcas, 'ESTADO_UI', {'hwnd': ventana}), \
             patch.object(marcas, 'validar_destino', return_value=True), \
             patch.object(jarvis, 'esperar_cancelacion', return_value=False), \
             patch.object(jarvis, 'mostrar_elemento'), patch.object(jarvis, 'avisar'), \
             patch.object(jarvis, 'capa'), patch.object(jarvis.acciones, 'mover_suave', return_value=True), \
             patch.object(jarvis.acciones, 'clic', return_value=True) as clic, \
             patch.object(jarvis, 'procesar_texto', side_effect=AssertionError('No debe reinterpretar la pregunta')), \
             patch.object(marcas, 'preguntar_json', side_effect=AssertionError('La guía no consulta al modelo')):
            resultado = jarvis.ejecutar_guia(oferta)
            return resultado, clic.call_count

    def test_guia_confirma_un_solo_control_aunque_cambien_los_ids(self):
        elementos = [('Button', 'Otro', 0, 50, 30, 70), ('MenuItem', 'Archivo', 0, 0, 30, 20)]
        self.assertEqual(self.guia(elementos=elementos), (True, 1))
        self.assertIsNone(jarvis.ESTADO['pendiente'])

    def test_guia_caducada_o_en_otra_ventana_no_actua(self):
        self.assertEqual(self.guia(ventana=11), (False, 0))
        self.assertEqual(self.guia(hasta=time.time() - 1), (False, 0))

    def test_guia_no_adivina_entre_controles_ambiguos(self):
        elementos = [('MenuItem', 'Archivo', 0, 50, 30, 70), ('MenuItem', 'Archivo', 0, 90, 30, 110)]
        self.assertEqual(self.guia(elementos=elementos), (False, 0))

    def test_confirmacion_de_guia_tambien_en_modo_sin_voz(self):
        oferta = {'hasta': time.time() + 10, 'texto': '¿Dónde se guarda?'}
        def guiar(*args):
            jarvis.ESTADO['pendiente'] = oferta
        with patch('builtins.input', side_effect=['¿Dónde se guarda?', 'salir']), \
             patch.object(jarvis, 'esperar_tecla', return_value=jarvis.ID_SENALAR), \
             patch.object(jarvis, 'procesar_texto', side_effect=guiar) as procesar, \
             patch.object(jarvis, 'esperar_decision', return_value=jarvis.ID_ACTUAR), \
             patch.object(jarvis, 'ejecutar_guia') as ejecutar, patch.object(jarvis.winsound, 'Beep'), \
             patch.object(jarvis, 'capa'):
            jarvis.modo_texto('J', 'K', True)
        procesar.assert_called_once_with('¿Dónde se guarda?', False)
        ejecutar.assert_called_once_with(oferta)


if __name__ == '__main__':
    unittest.main()
