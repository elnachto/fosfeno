import copy
from contextlib import ExitStack
from pathlib import Path
import time
from unittest.mock import patch, MagicMock

import jarvis
import marcas
import motor_ia
import rendimiento
from entornos_evaluacion import EscritorioSimulado, imagen_simulada, pregunta_correcta, sin_entrada_nativa


def ejecutar_interaccion(caso, motor, semilla):
    inicio = time.monotonic()
    consultas_inicio = len(marcas.PETICIONES)
    app = EscritorioSimulado(caso, semilla) if caso['entorno'] == 'guia' else None
    perfil = copy.deepcopy(motor_ia.PERFILES[motor])
    perfil.update(semilla=semilla, cache_prompt=False)
    pasos, respuestas = [], []
    correcto, aceptado = False, False
    motivo = 'No hubo una respuesta válida'
    original_post = marcas.requests.post
    carpeta = Path(marcas.OUT) / 'interacciones-simuladas'
    carpeta.mkdir(parents=True, exist_ok=True)
    def post(url, **kwargs):
        if not url.startswith(('http://127.0.0.1:', 'http://localhost:')):
            raise AssertionError('Solo se permiten consultas locales')
        reloj = time.monotonic()
        respuesta = rendimiento.llamar('consulta_modelo_s', original_post, url, **kwargs)
        if url.endswith('/v1/chat/completions') and respuesta.ok:
            datos, payload = respuesta.json(), kwargs.get('json', {})
            opcion = (datos.get('choices') or [{}])[0]
            peticion = {'modelo': perfil['modelo_api'], 'modelo_servidor': datos.get('model'), 'url': url,
                        'segundos': time.monotonic() - reloj, 'uso': datos.get('usage', {}),
                        'timings': datos.get('timings', {}), 'fin': opcion.get('finish_reason'),
                        'max_tokens': payload.get('max_tokens'), 'semilla_servidor': payload.get('seed'),
                        'vision': True, 'salida': 'texto'}
            marcas.PETICIONES.append(peticion)
            rendimiento.registrar_consulta(peticion)
        return respuesta
    def escanear():
        elementos, estado = app.observar()
        marcas.ESTADO_UI.clear()
        marcas.ESTADO_UI.update(estado)
        return imagen_simulada(estado['texto_visible'], elementos), estado['ventana'], elementos
    def validar(elemento, hwnd):
        elementos, estado = app.observar()
        return elemento in elementos and hwnd == estado['hwnd']
    def clic(x, y):
        elementos, _ = app.observar()
        elegidos = [n for n, e in enumerate(elementos, 1) if (e[2] + e[4]) // 2 == x and (e[3] + e[5]) // 2 == y]
        if len(elegidos) != 1:
            return False
        app.aplicar({'tipo': 'clic', 'n': elegidos[0]})
        return True
    try:
        with sin_entrada_nativa(), ExitStack() as pila:
            pila.enter_context(patch.object(marcas, 'PERFIL', perfil))
            pila.enter_context(patch.object(marcas, 'URL', perfil['url']))
            pila.enter_context(patch.object(marcas, 'OUT', str(carpeta)))
            pila.enter_context(patch.object(marcas, 'MONITOR', {'left': 0, 'top': 0, 'width': 800, 'height': 650}))
            pila.enter_context(patch.object(marcas, 'ESTADO_UI', {}))
            pila.enter_context(patch.object(marcas, 'cargar_notas', return_value=''))
            pila.enter_context(patch.object(jarvis.memoria, 'buscar_recetas', return_value=[]))
            pila.enter_context(patch.object(jarvis, 'capa', MagicMock()))
            pila.enter_context(patch.object(jarvis, 'avisar', side_effect=lambda texto, *a, **k: respuestas.append(texto)))
            pila.enter_context(patch.object(marcas.requests, 'post', side_effect=post))
            if app is None:
                with rendimiento.paso(1, 'pregunta-simulada', f'{motor}:{semilla}:{caso["id"]}') as medicion:
                    jarvis.responder(caso['objetivo'], (imagen_simulada(caso['texto']), 'Panel simulado', []))
                    respuesta = respuestas[-1] if respuestas else ''
                    correcto = pregunta_correcta(caso, respuesta)
                    aceptado = bool(respuesta)
                    medicion['accion'] = {'tipo': 'respuesta', 'texto': respuesta}
                    pasos.append({'numero': 1, 'accion': medicion['accion'], 'tiempos': medicion})
                motivo = 'respuesta contrastada con el texto de la imagen simulada' if correcto else 'respuesta no coincide con los datos visibles'
            else:
                pila.enter_context(patch.object(jarvis, 'ESTADO', {'pendiente': None}))
                pila.enter_context(patch.object(jarvis, 'LETRAS', {'actuar': 'K'}, create=True))
                pila.enter_context(patch.object(jarvis, 'mostrar_elemento', return_value=True))
                pila.enter_context(patch.object(jarvis, 'esperar_cancelacion', return_value=False))
                pila.enter_context(patch.object(jarvis, 'escanear', side_effect=escanear))
                pila.enter_context(patch.object(marcas, 'validar_destino', side_effect=validar))
                pila.enter_context(patch.object(jarvis.acciones, 'mover_suave', return_value=True))
                pila.enter_context(patch.object(jarvis.acciones, 'clic', side_effect=clic))
                pila.enter_context(patch.object(jarvis, 'procesar_texto', side_effect=AssertionError('La confirmación no debe reinterpretar la pregunta')))
                pila.enter_context(patch.object(jarvis, 'ejecutar', side_effect=AssertionError('La guía no debe ejecutar una tarea completa')))
                with rendimiento.paso(1, 'guia-simulada', f'{motor}:{semilla}:{caso["id"]}') as medicion:
                    jarvis.guiar(caso['objetivo'], escanear(), f'{motor}-{semilla}-{caso["id"]}', inicio)
                    oferta = jarvis.ESTADO.get('pendiente')
                    medicion['accion'] = {'tipo': 'guiar', 'oferta': copy.deepcopy(oferta)}
                    pasos.append({'numero': 1, 'accion': medicion['accion'], 'tiempos': medicion})
                if oferta:
                    app.paso += 2
                    with rendimiento.paso(2, 'guia-simulada', f'{motor}:{semilla}:{caso["id"]}') as medicion:
                        aceptado = jarvis.ejecutar_guia(oferta)
                        medicion['accion'] = {'tipo': 'confirmacion', 'entrada': 'Ctrl+Alt+K simulado', 'aceptada': aceptado}
                        pasos.append({'numero': 2, 'accion': medicion['accion'], 'tiempos': medicion})
                correcto = aceptado and app.cumplida()
                motivo = 'un solo clic en Archivo, sin reinterpretación' if correcto else 'no se confirmó exactamente el control Archivo'
    except Exception as error:
        motivo = type(error).__name__ + ': ' + str(error)
    peticiones = copy.deepcopy(marcas.PETICIONES[consultas_inicio:])
    resultado = {'caso': caso['id'], 'motor': motor, 'semilla': semilla, 'objetivo': caso['objetivo'],
                 'correcto': bool(correcto), 'objetivo_logrado': bool(correcto), 'falsos_listo_propuestos': 0,
                 'falso_exito_aceptado': bool(aceptado and not correcto), 'motivo': motivo,
                 'segundos': round(time.monotonic() - inicio, 3), 'pasos': len(pasos), 'traza': pasos,
                 'peticiones': peticiones, 'valor_final': respuestas, 'criterio': 'respuesta_observada' if app is None else 'confirmacion_un_clic',
                 'estado_final': app.diagnostico() if app else {'respuesta': respuestas[-1] if respuestas else '', 'acciones_nativas': 0}}
    resultado.update(rendimiento.resumir_consultas(peticiones))
    resultado['tokens_por_paso'] = resultado['tokens_generados'] / max(1, len(pasos))
    resultado['tokens_por_consulta'] = resultado['tokens_generados'] / len(peticiones) if peticiones else None
    return resultado
