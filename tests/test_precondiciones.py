import copy
import unittest
from unittest.mock import Mock

import acciones
import agente
import marcas
from unittest.mock import patch
import precondiciones as p


ELEMENTOS = [('Edit', 'IP', 0, 0, 100, 20), ('RadioButton', 'Servidor A', 0, 30, 100, 50),
             ('Button', 'Guardar reserva DHCP', 0, 60, 100, 80)]
ESTADO = {'ventana': 'Reservas', 'clase_aplicacion': 'Laboratorio', 'texto_visible': '',
          'foco': {'n': 1, 'nombre': 'IP', 'rol': 'Edit', 'editable': True, 'valor': '192.168.40.55'},
          'detalles': {'1': {'valor': '192.168.40.55'}, '2': {'seleccionado': True}}}
ENVIO = {'tipo': 'clic', 'n': 3}


class PrecondicionesTests(unittest.TestCase):
    def test_rechazo_visible_impide_falso_exito_tras_envio_pero_no_una_explicacion(self):
        estado = {**ESTADO, 'texto_visible': 'No se guardó: IP ocupada'}
        def consulta(*a):
            return {'cumplido': True, 'evidencia': 'El modelo supone éxito', 'pendiente': ''}
        r = agente.verificar('Crea la reserva', ELEMENTOS, estado, ['clic en «Guardar reserva DHCP»'], consulta)
        self.assertFalse(r['cumplido'])
        r = agente.verificar('Explica el error visible', ELEMENTOS, estado, ['dije «IP ocupada»'], consulta)
        self.assertTrue(r['cumplido'])

    def test_revalidacion_recaptura_valores_y_rechaza_captura_parcial(self):
        firma = p.firma_formulario(ELEMENTOS, ESTADO)
        with patch.object(marcas, 'ESTADO_UI', ESTADO), patch.object(marcas, 'reunir', return_value=('Reservas', ELEMENTOS, False)) as reunir:
            self.assertTrue(marcas.formulario_sin_cambios(firma, 800, 600))
            reunir.assert_called_once_with(800, 600)
            reunir.return_value = ('Reservas', ELEMENTOS, True)
            self.assertFalse(marcas.formulario_sin_cambios(firma, 800, 600))
        cambiado = copy.deepcopy(ESTADO)
        cambiado['detalles']['1']['valor'] = '192.168.40.90'
        with patch.object(marcas, 'ESTADO_UI', cambiado), patch.object(marcas, 'reunir', return_value=('Reservas', ELEMENTOS, False)):
            self.assertFalse(marcas.formulario_sin_cambios(firma, 800, 600))

    def test_envio_por_boton_o_atajo_pero_no_por_nombre_de_campo(self):
        self.assertTrue(p.es_envio(ENVIO, ELEMENTOS, ESTADO))
        self.assertTrue(p.es_envio({'tipo': 'tecla', 'tecla': 'ctrl+s'}, ELEMENTOS, ESTADO))
        self.assertFalse(p.es_envio({'tipo': 'tecla', 'tecla': 'enter'}, ELEMENTOS, ESTADO))
        self.assertFalse(p.es_envio({'tipo': 'clic', 'n': 1}, [('Edit', 'Guardar', 0, 0, 1, 1)], ESTADO))
        foco_boton = {**ESTADO, 'foco': {'rol': 'Button', 'nombre': 'Apply'}}
        self.assertTrue(p.es_envio({'tipo': 'tecla', 'tecla': 'enter'}, ELEMENTOS, foco_boton))

    def test_bloquea_reintento_aunque_se_explique_error_y_cambie_foco(self):
        traza = [{'evento': agente.evento_accion(ENVIO, ELEMENTOS, ESTADO)}]
        rechazado = {**ESTADO, 'texto_visible': 'No se guardó: IP ocupada'}
        p.observar_resultado(traza, rechazado)
        traza.append({'evento': {'tipo': 'decir'}, 'accion': 'Expliqué el rechazo'})
        cerrado = {**ESTADO, 'foco': {'n': 3, 'rol': 'Button'}, 'texto_visible': ''}
        with self.assertRaisesRegex(ValueError, 'siguen iguales'):
            p.validar_reintento(ENVIO, ELEMENTOS, cerrado, traza)

    def test_un_valor_corregido_o_servidor_distinto_permite_nueva_revision(self):
        traza = [{'evento': agente.evento_accion(ENVIO, ELEMENTOS, ESTADO), 'resultado': {'rechazos': ['Error: ocupado']}}]
        corregido = copy.deepcopy(ESTADO)
        corregido['detalles']['1']['valor'] = '192.168.40.56'
        p.validar_reintento(ENVIO, ELEMENTOS, corregido, traza)
        corregido = copy.deepcopy(ESTADO)
        corregido['detalles']['2']['seleccionado'] = False
        p.validar_reintento(ENVIO, ELEMENTOS, corregido, traza)

    def test_errores_son_resultados_y_no_palabras_historicas(self):
        self.assertEqual(p.errores_visibles({'texto_visible': 'Manual de errores\nEl error anterior ya se corrigió'}), [])
        self.assertEqual(p.errores_visibles({'texto_visible': 'Error: IP inválida'}), ['Error: IP inválida'])
        traza = [{'evento': {'tipo': 'decir'}}]
        p.observar_resultado(traza, {'texto_visible': 'Error: IP inválida'})
        self.assertNotIn('resultado', traza[0])

    def revisar(self, respuesta):
        return p.revisar('Crea una reserva y conserva las existentes', ENVIO,
                         {'texto_visible': 'IP 192.168.40.55 reservada a otra MAC',
                          'controles': [{'id': 1, 'nombre': 'IP', 'valor': '192.168.40.55'}]},
                         lambda *a: respuesta, None, agente.prompt_acotado)

    def test_revisor_pregunta_con_evidencia_literal(self):
        r = self.revisar({'decision': 'preguntar', 'motivo': 'IP ocupada', 'cita': '192.168.40.55', 'pregunta': '¿Qué IP libre quieres usar?'})
        self.assertEqual(r['tipo'], 'preguntar')
        self.assertIn('IP libre', r['texto'])

    def test_revisor_no_puede_inventar_conflicto_o_permitir_con_dudas(self):
        for respuesta in ({'decision': 'preguntar', 'cita': '192.168.99.99', 'pregunta': '¿Cambio?'},
                          {'decision': 'permitir', 'cita': '192.168.40.55', 'pregunta': ''}, {}):
            with self.subTest(respuesta=respuesta), self.assertRaises(ValueError):
                self.revisar(respuesta)

    def test_correccion_se_devuelve_al_planificador_sin_ejecutar(self):
        with self.assertRaisesRegex(ValueError, 'corrige'):
            self.revisar({'decision': 'corregir', 'cita': '192.168.40.55', 'motivo': 'El valor no coincide', 'pregunta': ''})

    def test_planificador_consulta_revision_independiente_antes_de_guardar(self):
        consultor = Mock(side_effect=[{'accion': 'CLIC', 'n': 3, 'texto': '', 'evidencia': 'Datos llenos'},
                                     {'decision': 'preguntar', 'cita': '192.168.40.55', 'motivo': 'Conflicto observado', 'pregunta': '¿Qué IP libre quieres usar?'}])
        accion, _, _ = agente.proponer('Crea reserva', ELEMENTOS, ESTADO, [], consultor, acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'preguntar')
        self.assertEqual(consultor.call_count, 2)
        self.assertIn('independently', consultor.call_args.args[0])

    def test_revision_permite_y_registra_firma_para_revalidar_antes_de_actuar(self):
        consultor = Mock(side_effect=[{'accion': 'CLIC', 'n': 3, 'texto': '', 'evidencia': 'Datos llenos'},
                                     {'decision': 'permitir', 'cita': '', 'motivo': 'Coincide', 'pregunta': ''}])
        accion, _, _ = agente.proponer('Crea reserva', ELEMENTOS, ESTADO, [], consultor, acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'clic')
        self.assertEqual(accion['_revision_previa'], p.firma_formulario(ELEMENTOS, ESTADO))

    def test_navegacion_y_escritura_no_invocan_revisor(self):
        consultor = Mock(return_value={'accion': 'ESCRIBIR', 'n': 1, 'texto': 'nuevo', 'evidencia': 'Campo vacío'})
        agente.proponer('Escribe nuevo', ELEMENTOS, ESTADO, [], consultor, acciones.normalizar_tecla)
        self.assertEqual(consultor.call_count, 1)


if __name__ == '__main__':
    unittest.main()
