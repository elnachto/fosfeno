import copy
import json
import tempfile
from pathlib import Path
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
    def test_marco_se_identifica_por_jerarquia_no_por_nombre_sistema(self):
        titulo = SimpleNamespace(ControlTypeName='TitleBarControl')
        menu_so = SimpleNamespace(ControlTypeName='MenuBarControl', GetParentControl=lambda: titulo)
        menu_app = SimpleNamespace(ControlTypeName='MenuBarControl', GetParentControl=lambda: SimpleNamespace(ControlTypeName='WindowControl'))
        self.assertTrue(marcas.padre_es_marco_ventana(titulo))
        self.assertTrue(marcas.padre_es_marco_ventana(menu_so))
        self.assertFalse(marcas.padre_es_marco_ventana(menu_app))

    def test_marco_no_suplanta_menu_interno_y_no_impide_cerrar_pedido(self):
        estado = {'detalles': {'1': {'marco_ventana': True}}}
        with self.assertRaisesRegex(ValueError, 'marco de Windows'):
            agente.validar_clic_marco({'tipo': 'clic', 'n': 1}, 'Consulta la configuración de red', estado)
        agente.validar_clic_marco({'tipo': 'clic', 'n': 1}, 'Cierra esta ventana', estado)
        agente.validar_clic_marco({'tipo': 'clic', 'n': 2}, 'Consulta la configuración', estado)

    def test_solo_marco_recibe_imagen_desde_primera_consulta(self):
        estado = {'detalles': {'1': {'marco_ventana': True}}}
        elementos = [('MenuItem', 'Sistema', 0, 0, 20, 20)]
        imagen, vistas = object(), []
        def consultar(*args):
            vistas.append(args)
            return respuesta('NADA')
        accion, _, _ = agente.proponer('Consulta la red', elementos, estado, [], consultar, acciones.normalizar_tecla, imagen=imagen)
        self.assertEqual(accion['tipo'], 'nada')
        self.assertIs(vistas[0][3], imagen)
        self.assertTrue(json.loads(vistas[0][1].split('CURRENT STATE:\n')[1])['solo_marco_accesible'])
        self.assertFalse(agente.solo_marco_accesible(ELEMENTOS, estado))

    def test_insistir_en_marco_para_tarea_interna_se_rechaza_sin_ejecutar(self):
        estado = {'detalles': {'1': {'marco_ventana': True}}}
        accion, _, intentos = agente.proponer('Averigua las IP', [('MenuItem', 'Sistema', 0, 0, 20, 20)], estado,
                                             [], lambda *a: respuesta('CLIC', 1), acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'nada')
        self.assertEqual(intentos, 3)
        self.assertIn('marco de Windows', accion['_evidencia'])

    def test_celda_conserva_asociacion_fila_columna_y_no_es_campo_editable(self):
        ctrl = SimpleNamespace(GetGridItemPattern=lambda: SimpleNamespace(Row=2, Column=0, ContainingGrid=SimpleNamespace(Name='Reservas existentes')),
                               GetTableItemPattern=lambda: SimpleNamespace(GetColumnHeaderItems=lambda: [SimpleNamespace(Name='IP')]))
        self.assertEqual(marcas.detalles_celda(ctrl), {'fila': 2, 'columna': 0, 'tabla': 'Reservas existentes', 'encabezado_columna': 'IP'})
        self.assertIn('DataItemControl', marcas.TIPOS)
        with self.assertRaises(ValueError):
            agente.convertir(respuesta('ESCRIBIR', 1, 'no borrar'), [('DataItem', '192.168.40.55', 0, 0, 100, 50)], acciones.normalizar_tecla)

    def test_rechaza_reescribir_texto_identico_sin_perder_espacios(self):
        estado = {'foco': {'n': 1, 'valor': 'Título\r  Texto\r'}}
        accion = {'tipo': 'escribir', 'n': 1, 'reemplazar': True, 'texto': 'Título\n  Texto\n'}
        with self.assertRaisesRegex(ValueError, 'YA contiene exactamente'):
            agente.validar_reemplazo(accion, 'Escribe y guarda', estado)
        with self.assertRaisesRegex(ValueError, 'YA contiene exactamente'):
            agente.validar_reemplazo({**accion, 'n': 0}, 'Escribe y guarda', estado)
        agente.validar_reemplazo({**accion, 'texto': 'Título\n Texto\n'}, 'Escribe y guarda', estado)
        agente.validar_reemplazo({**accion, 'n': 2}, 'Escribe y guarda', estado)
        with self.assertRaisesRegex(ValueError, 'Solo se observa parte'):
            agente.validar_reemplazo(accion, 'Escribe y guarda', {'foco': {**estado['foco'], 'valor_truncado': True}})

    def test_planificador_recibe_evidencia_archivo_antes_de_proponer_listo(self):
        imagen = SimpleNamespace(size=(400, 300))
        recibidos = []
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'nota.txt'
            ruta.write_text('Texto ya guardado', encoding='utf-8')
            def consulta(instruccion, texto, *resto):
                recibidos.append(texto)
                return respuesta('LISTO')
            with patch.object(marcas, 'PERFIL', {'agente_estado': True}), patch.object(marcas, 'marcar', return_value=imagen), \
                 patch.object(marcas, 'cargar_notas', return_value=''), patch.object(marcas, 'preguntar_json', side_effect=consulta):
                marcas.decidir_accion('Guarda el archivo como ' + str(ruta), imagen, 'Notas', ELEMENTOS, [], estado={})
        self.assertIn('Texto ya guardado', recibidos[0])
        self.assertIn('archivos_observados', recibidos[0])

    def test_ayuda_word_depende_de_clase_real_no_titulo(self):
        self.assertIn('Ctrl+Inicio', marcas.ayuda_aplicacion({'clase_ventana': 'OpusApp'}))
        self.assertEqual(marcas.ayuda_aplicacion({'ventana': 'Word', 'clase_ventana': 'Chrome_WidgetWin_1'}), '')
        self.assertIn('Ctrl+Inicio', marcas.ayuda_aplicacion({'clase_ventana': '#32770', 'clase_aplicacion': 'OpusApp'}))

    def test_continuacion_revalida_contenido_antes_de_borrarlo(self):
        pendiente = {'texto': 'Cuerpo', 'reemplazar': True, '_destino': agente.clave_elemento(ELEMENTOS[0]),
                     '_objetivo_usuario': 'Escribe «Título» y debajo «Cuerpo»'}
        estado = {'foco': {'n': 1, 'editable': True, 'valor': 'Título'}}
        self.assertIsNone(agente.continuar_pendiente(pendiente, estado, ELEMENTOS))

    def test_ubicacion_explorer_solo_consulta_la_ventana_objetivo(self):
        class Ajena:
            HWND = 99
            @property
            def LocationURL(self):
                raise AssertionError('No leer la ubicación de ventanas ajenas')
        with tempfile.TemporaryDirectory() as carpeta:
            ventanas = SimpleNamespace(Count=2, Item=lambda n: [Ajena(), SimpleNamespace(HWND=1, LocationURL=Path(carpeta).as_uri())][n])
            with patch('comtypes.client.CreateObject', return_value=SimpleNamespace(Windows=lambda: ventanas)):
                self.assertEqual(marcas.carpeta_explorador(1), str(Path(carpeta)))

    def test_comprueba_copias_y_rechaza_diferencias(self):
        with tempfile.TemporaryDirectory() as carpeta:
            origen, destino = Path(carpeta) / 'Origen', Path(carpeta) / 'Salida'
            origen.mkdir(); destino.mkdir()
            (origen / 'a.txt').write_text('Original', encoding='utf-8')
            (destino / 'a.txt').write_text('Diferente', encoding='utf-8')
            traza = [{'evento': {'operacion': 'copiar', 'carpeta_visible': str(origen), 'seleccion_antes': ['a.txt']}},
                     {'evento': {'operacion': 'pegar', 'carpeta_visible': str(destino)}}]
            datos = marcas.evidencia_copias('Copia a.txt a la carpeta Salida', traza)
            self.assertFalse(datos[0]['contenido_identico'])
            consulta = lambda *a: {'cumplido': True, 'evidencia': 'Se ven nombres', 'pendiente': ''}
            self.assertFalse(agente.verificar('Copia a.txt', [], {'copias_observadas': datos}, [], consulta)['cumplido'])
            (destino / 'a.txt').write_bytes((origen / 'a.txt').read_bytes())
            self.assertTrue(marcas.evidencia_copias('Copia a.txt a la carpeta Salida', traza)[0]['contenido_identico'])

    def test_abre_carpeta_destino_solo_si_esta_seleccionada_y_no_abierta(self):
        elementos = [('ListItem', 'Entrega', 0, 0, 200, 25), ('Button', 'Pegar', 0, 30, 100, 50)]
        estado = {'ventana': 'Origen - Explorador de archivos', 'foco': {'n': 1, 'rol': 'ListItem'},
                  'detalles': {'1': {'seleccionado': True}, '3': {'id_automatizacion': 'System.ItemTypeText',
                                                               'contenedor': 'ListItem: Entrega', 'valor': 'Carpeta de archivos'}}}
        accion = {'tipo': 'clic', 'n': 2}
        self.assertEqual(agente.abrir_destino_antes_de_pegar(accion, 'Copia a la carpeta Entrega', elementos, estado)['tecla'], 'enter')
        estado['ventana'] = 'Entrega - Explorador de archivos'
        self.assertEqual(agente.abrir_destino_antes_de_pegar(accion, 'Copia a la carpeta Entrega', elementos, estado), accion)
        estado['ventana'] = 'Origen - Explorador de archivos'
        self.assertEqual(agente.abrir_destino_antes_de_pegar(accion, 'Pega aquí', elementos, estado), accion)

    def test_evento_copia_conserva_seleccion_del_momento_sin_afirmar_exito(self):
        elementos = [('ListItem', 'a.txt', 0, 0, 100, 20), ('ListItem', 'b.txt', 0, 30, 100, 50), ('Button', 'Copiar', 0, 60, 100, 80)]
        estado = {'ventana': 'Origen', 'foco': {'nombre': 'b.txt'}, 'detalles': {'1': {'seleccionado': True}, '2': {'seleccionado': True}}}
        evento = agente.evento_accion({'tipo': 'clic', 'n': 3}, elementos, estado)
        self.assertEqual(evento['seleccion_antes'], ['a.txt', 'b.txt'])
        self.assertEqual(evento['operacion'], 'copiar')
        self.assertIn('comprobar', evento['resultado'])
        self.assertEqual(agente.evento_accion({'tipo': 'tecla', 'tecla': 'enter'}, elementos, {'ventana': 'Párrafo'})['ventana'], 'Párrafo')

    def test_amplia_solo_dos_archivos_adyacentes_pedidos(self):
        elementos = [('ListItem', 'a.txt', 0, 0, 200, 25), ('ListItem', 'b.txt', 0, 30, 200, 55)]
        estado = {'foco': {'n': 1}, 'detalles': {'1': {'seleccionado': True, 'contenedor': 'List: Archivos'},
                                               '2': {'seleccionado': False, 'contenedor': 'List: Archivos'}}}
        accion = {'tipo': 'clic', 'n': 2}
        self.assertEqual(agente.ampliar_seleccion_adyacente(accion, 'Copia a.txt y b.txt a Entrega', elementos, estado)['tecla'], 'shift+abajo')
        self.assertEqual(agente.ampliar_seleccion_adyacente(accion, 'Copia a.txt a b.txt', elementos, estado), accion)
        elementos.append(('ListItem', 'no-pedido.txt', 0, 26, 200, 29))
        estado['detalles']['3'] = {'contenedor': 'List: Archivos'}
        self.assertEqual(agente.ampliar_seleccion_adyacente(accion, 'Copia a.txt y b.txt a Entrega', elementos, estado), accion)

    def test_no_reemplaza_titulo_pedido_al_anadir_un_parrafo(self):
        accion = {'tipo': 'escribir', 'texto': 'Cuerpo', 'reemplazar': True, 'n': 1}
        with self.assertRaisesRegex(ValueError, 'borraría'):
            agente.validar_reemplazo(accion, 'Escribe «Título» y debajo «Cuerpo»', {'foco': {'n': 1, 'valor': 'Título'}})
        accion['texto'] = 'Título\nCuerpo'
        agente.validar_reemplazo(accion, 'Escribe «Título» y debajo «Cuerpo»', {'foco': {'n': 1, 'valor': 'Título'}})

    def test_no_reescribe_documento_si_solo_leyo_un_fragmento(self):
        accion = {'tipo': 'escribir', 'texto': 'Cambios parciales', 'reemplazar': True, 'n': 1}
        estado = {'foco': {'n': 1, 'valor': 'Inicio', 'valor_truncado': True}}
        with self.assertRaisesRegex(ValueError, 'parte del contenido'):
            agente.validar_reemplazo(accion, 'Cambia una cantidad', estado)
        agente.validar_reemplazo(accion, 'Reemplaza todo el contenido por «Cambios parciales»', estado)

    def test_selector_con_valor_no_se_confunde_con_campo_de_texto(self):
        class Selector:
            Name = 'Alineación:'; ControlTypeName = 'ComboBoxControl'; IsPassword = False
            BoundingRectangle = SimpleNamespace(left=0, top=0, right=100, bottom=30)
            def GetValuePattern(self):
                return SimpleNamespace(Value='Izquierda', IsReadOnly=False)
        elementos = [('ComboBox', 'Alineación:', 0, 0, 100, 30)]
        with patch.object(marcas.auto, 'GetFocusedControl', return_value=Selector()):
            estado = marcas.capturar_estado('Párrafo', elementos, SimpleNamespace(NativeWindowHandle=1))
        self.assertFalse(estado['foco']['editable'])
        accion, _, _ = agente.proponer('Selecciona Centrada', elementos, estado, [], lambda *a: respuesta('CLIC', 1), acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'clic')

    def test_documento_padre_no_oculta_foco_del_editor_hijo(self):
        elementos = [('Document', 'Documento1', 0, 50, 600, 720), ('Edit', 'Contenido página 1', 50, 80, 550, 700)]
        self.assertEqual(marcas.identificar_foco(elementos, 'Documento1', 'Document', (0, 50, 600, 720), True),
                         (2, 'contenido_editable_unico'))

    def test_no_oculta_el_tercer_boton_homonimo_de_un_dialogo(self):
        controles = [SimpleNamespace(ControlTypeName='ButtonControl', IsOffscreen=False, IsEnabled=True,
                     Name='Abrir', AutomationId=str(n), IsPassword=False,
                     BoundingRectangle=SimpleNamespace(left=n * 50, top=10, right=n * 50 + 30, bottom=30)) for n in range(3)]
        with patch.object(marcas.auto, 'WalkControl', return_value=[(c, 1) for c in controles]), \
             patch.dict(marcas.MONITOR, {'left': 0, 'top': 0}), patch.dict(marcas.DETALLES_UI, {}, clear=True):
            elementos, truncado = marcas.recorrer(object(), 500, 500, '', 150)
        self.assertEqual(len(elementos), 3)
        self.assertFalse(truncado)

    def test_escritura_preserva_espacios_y_normaliza_saltos(self):
        accion = agente.convertir(respuesta('ESCRIBIR', 1, '  á\r\n  β\r\n'), ELEMENTOS, acciones.normalizar_tecla)
        self.assertEqual(accion['texto'], '  á\n  β\n')

    def test_literal_multilinea_acepta_saltos_de_linea_de_uia(self):
        consulta = lambda *a: {'cumplido': True, 'evidencia': 'Texto observado', 'pendiente': ''}
        resultado = agente.verificar('Escribe «Primera\nSegunda» y guarda', ELEMENTOS,
                                     {'foco': {'valor': 'Primera\rSegunda'}}, [], consulta)
        self.assertTrue(resultado['cumplido'])

    def test_archivo_inexistente_impide_confirmar(self):
        consulta = lambda *a: {'cumplido': True, 'evidencia': 'Hice clic', 'pendiente': ''}
        resultado = agente.verificar('Guarda el archivo', ELEMENTOS,
                                     {'archivos_observados': [{'ruta': 'C:\\no-existe.txt', 'existe': False}]}, [], consulta)
        self.assertFalse(resultado['cumplido'])

    def test_lee_solo_ruta_explicita_y_texto_acotado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'nota con espacios.txt'
            ruta.write_text('á' * 6100, encoding='utf-8')
            resultado = marcas.evidencia_archivos('Guarda como ' + str(ruta) + '. No cambies otras ventanas.')
            self.assertEqual([d['ruta'] for d in resultado], [str(ruta)])
            self.assertTrue(resultado[0]['existe'])
            self.assertTrue(resultado[0]['truncado'])
            self.assertEqual(len(resultado[0]['texto']), 6000)
            self.assertEqual(marcas.evidencia_archivos('Lee ' + str(ruta)), [])

    def test_seleccion_no_depende_del_atajo_localizado_ctrl_a(self):
        with patch.object(acciones, 'tecla', return_value=True) as tecla:
            self.assertTrue(acciones.seleccionar_todo())
            self.assertEqual([c.args[0] for c in tecla.call_args_list], ['ctrl+inicio', 'ctrl+shift+fin'])

    def test_no_escribe_en_campo_de_solo_lectura(self):
        estado = {'foco': {'n': 1, 'editable': True}, 'detalles': {'1': {'solo_lectura': True}}}
        accion, _, _ = agente.proponer('Escribe Ana', ELEMENTOS, estado, [], lambda *a: respuesta('ESCRIBIR', 1, 'Ana'), acciones.normalizar_tecla)
        self.assertEqual(accion['tipo'], 'nada')
        self.assertIn('solo lectura', accion['_evidencia'])

    def test_verificacion_no_exige_texto_que_se_pidio_reemplazar(self):
        consulta = lambda *a: {'cumplido': True, 'evidencia': 'El documento contiene el resultado nuevo', 'pendiente': ''}
        estado = {'foco': {'valor': 'nuevo'}}
        self.assertTrue(agente.verificar('Reemplaza «viejo» por «nuevo» y guarda', ELEMENTOS, estado, [], consulta)['cumplido'])

    def test_foco_documento_resuelve_campo_hijo_unico(self):
        elementos = [('Edit', 'Buscar', 0, 0, 150, 25), ('Edit', 'Contenido página 1', 50, 80, 550, 700)]
        self.assertEqual(marcas.identificar_foco(elementos, 'Documento1', 'Document', (10, 50, 600, 720), True),
                         (2, 'contenido_editable_unico'))

    def test_foco_documento_no_adivina_entre_dos_campos(self):
        elementos = [('Edit', 'A', 20, 70, 100, 100), ('Edit', 'B', 20, 120, 100, 150)]
        self.assertIsNone(marcas.identificar_foco(elementos, 'Documento', 'Document', (10, 50, 600, 720), True)[0])
        self.assertIsNone(marcas.identificar_foco(elementos, 'Documento', 'Document', (10, 50, 600, 720), False)[0])

    def test_huella_resiste_renumerar_controles_y_foco(self):
        estado = {'foco': {'n': 1, 'nombre': 'Nombre'}, 'detalles': {'1': {'valor': 'Ana'}}}
        otro = {'foco': {'n': 2, 'nombre': 'Nombre'}, 'detalles': {'2': {'valor': 'Ana'}}}
        self.assertEqual(agente.huella(estado, ELEMENTOS), agente.huella(otro, [ELEMENTOS[2], ELEMENTOS[0], ELEMENTOS[1]]))

    def test_ciclo_de_varios_pasos_no_repite_tercera_vuelta(self):
        accion, estado = {'tipo': 'clic', 'n': 3}, {'ventana': 'Prueba'}
        paso = {'clave': repr(agente.clave_accion(accion, ELEMENTOS)), 'firma_operativa': agente.firma_operativa(accion, ELEMENTOS, estado)}
        traza = [paso, {'clave': 'otra', 'huella': 'otra'}, paso, {'clave': 'otra', 'huella': 'otra'}]
        self.assertTrue(agente.ciclo_sin_progreso(accion, ELEMENTOS, estado, traza))
        self.assertFalse(agente.ciclo_sin_progreso(accion, ELEMENTOS, {'ventana': 'Otra'}, traza))
        self.assertFalse(agente.ciclo_sin_progreso(accion, ELEMENTOS, estado, traza[:2]))

    def test_firma_operativa_ignora_toolbars_parciales(self):
        accion = {'tipo': 'clic', 'n': 3}
        estado = {'ventana': 'Documento', 'foco': {'nombre': 'Documento', 'valor': 'Texto'}}
        self.assertEqual(agente.firma_operativa(accion, ELEMENTOS, estado),
                         agente.firma_operativa(accion, ELEMENTOS + [('Button', 'Tooltip variable', 0, 300, 100, 330)], estado))

    def test_timeout_de_captura_se_declara_incompleto(self):
        with patch.object(marcas.auto, 'WalkControl', return_value=[(object(), 1)]), patch.object(marcas.time, 'time', side_effect=[0, 4]):
            elementos, incompleta = marcas.recorrer(object(), 500, 500, '', 150)
        self.assertEqual(elementos, [])
        self.assertTrue(incompleta)

    def test_ruta_estado_conserva_notas_recetas_y_partes(self):
        imagen = SimpleNamespace(size=(400, 300))
        prompts = []
        def consultar(instruccion, texto, *resto):
            prompts.append((instruccion, texto))
            return respuesta('NADA')
        with patch.object(marcas, 'PERFIL', {'agente_estado': True}), \
             patch.object(marcas, 'marcar', return_value=imagen), \
             patch.object(marcas, 'cargar_notas', return_value='Nota guardada de esta app'), \
             patch.object(marcas, 'preguntar_json', side_effect=consultar):
            marcas.decidir_accion('Completa y guarda', imagen, 'App', ELEMENTOS, [],
                                  ejemplos='Receta anterior', partes=['Completa', 'Guarda'], estado={})
        self.assertIn('Nota guardada de esta app', prompts[0][1])
        self.assertIn('Receta anterior', prompts[0][1])
        self.assertIn(json.dumps(['Completa', 'Guarda']), prompts[0][1])
        self.assertIn('untrusted', prompts[0][1])
        self.assertIn('old control numbers', prompts[0][0])

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
