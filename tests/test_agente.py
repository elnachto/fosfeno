import copy
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import acciones
import agente
import marcas


ELEMENTOS = [('Edit', 'Nombre', 0, 0, 100, 30), ('Edit', 'Ciudad', 0, 50, 100, 80),
             ('Button', 'Guardar', 0, 100, 100, 130)]


def respuesta(accion, n=0, texto=''):
    return {'accion': accion, 'n': n, 'texto': texto, 'objetivo_pendiente': 'Completar datos', 'evidencia': 'Estado observado'}


class AgenteTests(unittest.TestCase):
    def test_clave_resiste_renumeracion(self):
        self.assertEqual(agente.clave_accion({'tipo': 'clic', 'n': 1}, ELEMENTOS),
                         agente.clave_accion({'tipo': 'clic', 'n': 2}, [ELEMENTOS[2], ELEMENTOS[0]]))

    def test_controles_homonimos_se_distinguen(self):
        elementos = [('Button', 'Guardar', 0, 0, 80, 30), ('Button', 'Guardar', 200, 0, 280, 30)]
        self.assertNotEqual(agente.clave_accion({'tipo': 'clic', 'n': 1}, elementos),
                            agente.clave_accion({'tipo': 'clic', 'n': 2}, elementos))

    def test_id_no_observado_rechazado(self):
        for n in (0, 4, True, '1', -1):
            with self.subTest(n=n), self.assertRaises(ValueError):
                agente.convertir(respuesta('CLIC', n), ELEMENTOS, acciones.normalizar_tecla)

    def test_no_escribir_en_boton(self):
        with self.assertRaises(ValueError):
            agente.convertir(respuesta('ESCRIBIR', 3, 'Ana'), ELEMENTOS, acciones.normalizar_tecla)

    def test_tecla_invalida_rechazada(self):
        with self.assertRaises(ValueError):
            agente.convertir(respuesta('TECLA', texto='ctrl+noexiste'), ELEMENTOS, acciones.normalizar_tecla)

    def test_texto_vacio_rechazado(self):
        with self.assertRaises(ValueError):
            agente.convertir(respuesta('ESCRIBIR'), ELEMENTOS, acciones.normalizar_tecla)

    def test_cambio_de_campo_genera_continuacion(self):
        consulta = lambda *args: respuesta('ESCRIBIR', 2, 'Sucre')
        estado = {'foco': {'n': 1, 'editable': True, 'nombre': 'Nombre'}}
        accion, _, _ = agente.proponer('Completa ciudad Sucre', ELEMENTOS, estado, [], consulta, acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'clic')
        self.assertEqual(accion['n'], 2)
        self.assertEqual(accion['_despues']['texto'], 'Sucre')

    def test_continuacion_solo_si_destino_tiene_foco(self):
        pendiente = {'tipo': 'escribir', 'texto': 'Sucre', '_destino': agente.clave_elemento(ELEMENTOS[1])}
        estado = {'foco': {'n': 2, 'editable': True}}
        self.assertEqual(agente.continuar_pendiente(pendiente, estado, ELEMENTOS)['texto'], 'Sucre')
        estado['foco']['n'] = 1
        self.assertIsNone(agente.continuar_pendiente(pendiente, estado, ELEMENTOS))

    def test_continuacion_no_escribe_contrasena(self):
        pendiente = {'tipo': 'escribir', 'texto': 'Sucre', '_destino': agente.clave_elemento(ELEMENTOS[1])}
        self.assertIsNone(agente.continuar_pendiente(pendiente, {'foco': {'n': 2, 'editable': True, 'secreto': True}}, ELEMENTOS))

    def test_reparacion_no_repite_campo_enfocado(self):
        datos = iter([respuesta('CLIC', 1), respuesta('ESCRIBIR', 1, 'Ana')])
        estado = {'foco': {'n': 1, 'editable': True}}
        accion, _, intentos = agente.proponer('Escribe Ana', ELEMENTOS, estado, [], lambda *a: next(datos), acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'escribir')
        self.assertEqual(intentos, 2)

    def test_reparacion_acotada(self):
        estado = {'foco': {'n': 1, 'editable': True}}
        accion, _, intentos = agente.proponer('Escribe Ana', ELEMENTOS, estado, [], lambda *a: respuesta('CLIC', 1), acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'nada')
        self.assertEqual(intentos, 3)

    def test_no_convierte_razonamiento_en_accion(self):
        with self.assertRaises(marcas.ErrorRespuestaModelo):
            marcas.leer_respuesta({'choices': [{'message': {'content': '', 'reasoning_content': 'CLIC 1'}, 'finish_reason': 'stop'}]})

    def test_json_sin_respuesta_final_rechazado(self):
        with self.assertRaises(marcas.ErrorRespuestaModelo):
            marcas.leer_respuesta({'choices': []})

    def test_acciones_ambiguas_rechazadas(self):
        self.assertIsNone(marcas.parse_accion('CLIC 1\nTECLA enter', 3))

    def test_parser_no_extrae_accion_de_prosa(self):
        self.assertIsNone(marcas.parse_accion('Ya hice CLIC 1 y terminé', 3))

    def test_cancelacion_detiene_escritura(self):
        with patch.object(acciones, 'esc_presionado', side_effect=[False, True]), patch.object(acciones, 'enviar') as enviar:
            self.assertFalse(acciones.escribir('AB'))
            self.assertEqual(enviar.call_count, 2)

    def test_cancelacion_impide_atajo(self):
        with patch.object(acciones, 'esc_presionado', return_value=True), patch.object(acciones, 'enviar') as enviar:
            self.assertFalse(acciones.tecla('ctrl+s'))
            enviar.assert_not_called()

    def test_modificador_se_libera_tras_error(self):
        eventos = []
        def enviar(vk, scan, flags):
            eventos.append((vk, flags))
            if vk == ord('S') and flags == 0:
                raise OSError('fallo simulado')
        with patch.object(acciones, 'esc_presionado', return_value=False), patch.object(acciones, 'enviar', side_effect=enviar):
            with self.assertRaises(OSError):
                acciones.tecla('ctrl+s')
        self.assertEqual(eventos[-1], (0x11, acciones.KEYEVENTF_KEYUP))

    def test_huella_cambia_con_valor_del_campo(self):
        a = {'ventana': 'Formulario', 'foco': {'valor': ''}}
        b = {'ventana': 'Formulario', 'foco': {'valor': 'Ana'}}
        self.assertNotEqual(agente.huella(a, ELEMENTOS), agente.huella(b, ELEMENTOS))

    def test_pendiente_no_cruza_ventanas(self):
        pendiente = {'texto': 'Ana', '_ventana': 100, '_destino': agente.clave_elemento(ELEMENTOS[0])}
        estado = {'hwnd': 200, 'foco': {'n': 1, 'editable': True}}
        self.assertIsNone(agente.continuar_pendiente(pendiente, estado, ELEMENTOS))

    def test_pendiente_no_confunde_campos_homonimos(self):
        elementos = [('Edit', 'Nombre', 0, 0, 100, 30), ('Edit', 'Nombre', 200, 0, 300, 30)]
        pendiente = {'texto': 'Ana', '_destino': agente.clave_elemento(elementos[0]), '_rect': elementos[0][2:]}
        self.assertIsNone(agente.continuar_pendiente(pendiente, {'foco': {'n': 2, 'editable': True}}, elementos))

    def test_flecha_repetida_se_permite_con_progreso(self):
        accion = {'tipo': 'tecla', 'tecla': 'abajo'}
        traza = [{'clave': repr(agente.clave_accion(accion, ELEMENTOS)), 'resultado': {'cambio_observable': True}}]
        self.assertFalse(agente.repetida_sin_progreso(accion, ELEMENTOS, traza))
        traza[-1]['resultado']['cambio_observable'] = False
        self.assertTrue(agente.repetida_sin_progreso(accion, ELEMENTOS, traza))

    def test_reemplazar_preserva_intencion(self):
        accion = agente.convertir({**respuesta('ESCRIBIR', 1, 'Ana'), 'reemplazar': True}, ELEMENTOS, acciones.normalizar_tecla)
        self.assertTrue(accion['reemplazar'])

    def test_spinner_es_editable(self):
        elementos = [('Spinner', 'Cantidad', 0, 0, 100, 30)]
        self.assertEqual(agente.convertir(respuesta('ESCRIBIR', 1, '7'), elementos, acciones.normalizar_tecla)['n'], 1)

    def test_respuesta_truncada_no_se_acepta(self):
        with self.assertRaises(marcas.ErrorRespuestaModelo):
            marcas.leer_respuesta({'choices': [{'message': {'content': 'RESPUESTA: ESCRIBIR texto cortado'}, 'finish_reason': 'length'}]})

    def test_cliente_reintenta_una_respuesta_truncada(self):
        enviados = []
        def post(url, json, timeout):
            enviados.append(copy.deepcopy(json))
            datos = {'choices': [{'message': {'content': '{"n":1}'}, 'finish_reason': 'length' if len(enviados) == 1 else 'stop'}]}
            return SimpleNamespace(json=lambda: datos, raise_for_status=lambda: None)
        with patch.object(marcas.requests, 'post', side_effect=post):
            self.assertEqual(marcas._consultar_json('http://localhost', 'test', 'instruccion', 'estado', {'required': ['n']}), {'n': 1})
        self.assertEqual([p['max_tokens'] for p in enviados], [1200, 2400])

    def test_cliente_rechaza_campos_ausentes(self):
        fake = SimpleNamespace(json=lambda: {'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]}, raise_for_status=lambda: None)
        with patch.object(marcas.requests, 'post', return_value=fake), self.assertRaises(marcas.ErrorRespuestaModelo):
            marcas._consultar_json('http://localhost', 'test', 'i', 'e', {'required': ['n']})

    def test_perfil_cambia_servidor_realmente(self):
        fake = SimpleNamespace(json=lambda: {'choices': [{'message': {'content': '{"n":1}'}, 'finish_reason': 'stop'}]}, raise_for_status=lambda: None)
        perfil = {**marcas.PERFIL, 'url': 'http://localhost:9999/v1/chat/completions', 'modelo_api': 'otro'}
        perfil.pop('planificador_url', None)
        with patch.object(marcas, 'PERFIL', perfil), patch.object(marcas.requests, 'post', return_value=fake) as post:
            marcas.preguntar_json('i', 'e', {'required': ['n']})
        self.assertEqual(post.call_args.args[0], perfil['url'])
        self.assertEqual(post.call_args.kwargs['json']['model'], 'otro')

    def test_no_se_lee_valor_de_password(self):
        class Campo:
            Name = 'Clave'; ControlTypeName = 'EditControl'; IsPassword = True
            BoundingRectangle = SimpleNamespace(left=0, top=0, right=100, bottom=30)
            def GetValuePattern(self):
                raise AssertionError('No se debe leer una contraseña')
        with patch.object(marcas.auto, 'GetFocusedControl', return_value=Campo()):
            estado = marcas.capturar_estado('Prueba', [], SimpleNamespace(NativeWindowHandle=1))
        self.assertTrue(estado['foco']['secreto'])
        self.assertEqual(estado['foco']['valor'], '')

    def test_snapshot_checkbox_cambia_huella(self):
        a = {'detalles': {'1': {'activado': False}}}
        b = {'detalles': {'1': {'activado': True}}}
        self.assertNotEqual(agente.huella(a, ELEMENTOS), agente.huella(b, ELEMENTOS))

    def test_verificacion_no_confirma_literal_ausente(self):
        verificador = lambda *a: {'cumplido': True, 'evidencia': 'Hice clic en guardar', 'pendiente': ''}
        estado = {'ventana': 'Notas', 'foco': {'valor': 'Otro texto'}, 'texto_visible': 'Guardado'}
        resultado = agente.verificar('Escribe «Texto solicitado» y guarda', ELEMENTOS, estado, [], verificador)
        self.assertFalse(resultado['cumplido'])

    def test_verificacion_exige_evidencia(self):
        self.assertFalse(agente.final_confirmado({'cumplido': True, 'evidencia': ''}))
        self.assertFalse(agente.final_confirmado({'cumplido': 1, 'evidencia': 'Texto'}))
        self.assertTrue(agente.final_confirmado({'cumplido': True, 'evidencia': 'Resultado visible'}))
        self.assertFalse(agente.final_confirmado({'cumplido': True, 'evidencia': 'Pestaña nueva', 'pendiente': 'Falta abrir la página'}))

    def test_verificacion_rechaza_url_no_abierta(self):
        consulta = lambda *a: {'cumplido': True, 'evidencia': 'Pestaña abierta', 'pendiente': ''}
        estado = {'foco': {'valor': 'https://example.org/inicio'}, 'texto_visible': 'Pestaña nueva'}
        self.assertFalse(agente.verificar('Abre https://example.org/manual', ELEMENTOS, estado, [], consulta)['cumplido'])

    def test_verificacion_rechaza_selector_incorrecto(self):
        consulta = lambda *a: {'cumplido': True, 'evidencia': 'Guardado', 'pendiente': ''}
        estado = {'detalles': {'1': {'valor': 'English', 'opciones': ['English', 'Español']}}}
        self.assertFalse(agente.verificar('Cambia el idioma a Español', ELEMENTOS, estado, [], consulta)['cumplido'])

    def test_verificacion_espera_resultados(self):
        consulta = lambda *a: {'cumplido': True, 'evidencia': 'Se pulsó Buscar', 'pendiente': ''}
        self.assertFalse(agente.verificar('Busca factura 072 y espera los resultados', ELEMENTOS,
            {'texto_visible': 'Cargando resultados'}, [], consulta)['cumplido'])


if __name__ == '__main__':
    unittest.main()
