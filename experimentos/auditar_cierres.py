import argparse
import ast
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import agente
from entornos_evaluacion import EscritorioSimulado
from evaluacion import AplicacionSimulada, CASOS


FUENTES = [
    ('original-40', 'salidas/arnes-ampliado/medicion', True),
    ('diagnostico-sin-corregir', 'salidas/arnes-ampliado/v2/paso1-diagnostico', True),
    ('v2-listo', 'salidas/arnes-ampliado/v2/paso1-corregido', False),
    ('v2-muestra-interrumpida', 'salidas/arnes-ampliado/v2/paso2-muestra10', False),
]


def oraculo_etapa(caso, indice, app, estado):
    valores = [str(v.get('valor', '')) for v in estado.get('memoria_tarea', {}).get('hechos_observados', {}).values()]
    if indice == 1:
        if caso['modo'].startswith('calculo'):
            igual = app.calculado and ast.dump(ast.parse(app.expresion, mode='eval')) == ast.dump(ast.parse(caso['expresion'], mode='eval'))
            return bool(igual and app.resultado_calculo == caso['esperado']), 'operación y resultado calculados en el estado privado'
        pedidos = list(caso['esperado'].values()) if isinstance(caso['esperado'], dict) else [caso['esperado']]
        return all(any(v in observado for observado in valores) for v in pedidos), 'literales de la fuente conservados en hechos observados'
    if indice == 2:
        return app.enviado == caso['esperado'], 'destino guardado con los valores de la fuente'
    if indice == 3 and caso['modo'] == 'regreso':
        return app.revisado and app.ventana == 'fuente', 'fuente activa y casilla Revisado activada'
    return None, 'etapa sin oráculo definido; no se fuerza un booleano'


def reconstruir(resultado, caso):
    ampliado = bool(caso.get('entorno'))
    app = EscritorioSimulado(caso, resultado['semilla']) if ampliado else AplicacionSimulada(caso, resultado['semilla'])
    traza, observaciones = [], []
    for paso in resultado['traza']:
        elementos, estado = app.observar()
        observado = paso['estado']
        for clave in ('ventana', 'hwnd', 'foco', 'detalles', 'texto_visible'):
            if estado.get(clave) != observado.get(clave):
                raise ValueError(f"Replay distinto: {caso['id']} semilla={resultado['semilla']} paso={paso['numero']} campo={clave}")
        accion = paso['accion']
        if ampliado and accion['tipo'] == 'nada':
            app.detener(accion)
        for campo in ('verificacion_etapa', 'verificacion'):
            if campo not in paso:
                continue
            global_ok = app.cumplida()
            indice = observado.get('memoria_tarea', {}).get('etapa_activa') if campo == 'verificacion_etapa' else None
            if campo == 'verificacion_etapa' and indice is not None:
                verdad, criterio = oraculo_etapa(caso, indice, app, observado)
            elif campo == 'verificacion':
                verdad, criterio = global_ok, 'oráculo independiente del objetivo completo'
            else:
                verdad, criterio = None, 'no se pudo identificar la etapa'
            observaciones.append(copy.deepcopy({'paso': paso['numero'], 'ruta': campo, 'propuesta': accion['tipo'],
                'etapa': indice, 'veredicto': copy.deepcopy(paso[campo]), 'cumplido': paso[campo].get('cumplido') is True,
                'final_confirmado': agente.final_confirmado(paso[campo]), 'oraculo': verdad,
                'oraculo_objetivo_total': global_ok, 'criterio_oraculo': criterio,
                'estado_privado': app.diagnostico() if ampliado else {'enviado': app.enviado, 'valores': app.valores,
                    'nuevo_chat': app.nuevo_chat, 'nueva_pestana': app.nueva_pestana, 'cargando': app.cargando},
                'observacion_reproducida': True}))
        if accion['tipo'] in ('listo', 'nada', 'recordar', 'siguiente'):
            continue
        clave = repr(agente.clave_accion(accion, elementos))
        if agente.repetida_sin_progreso(accion, elementos, traza):
            continue
        if ampliado and not app.revalidar(accion):
            agente.registrar_intento_fallido(accion, elementos, estado, traza, 'Destino no accesible en el simulador')
            continue
        app.aplicar(accion)
        elementos_despues, estado_despues = app.observar()
        if accion['tipo'] == 'clic':
            texto = 'clic en «' + elementos[accion['n'] - 1][1] + '»'
        elif accion['tipo'] == 'escribir':
            texto = ('reemplacé por «' if accion.get('reemplazar') else 'escribí «') + accion['texto'] + '»'
        elif accion['tipo'] == 'tecla':
            texto = 'pulsé la tecla ' + accion['tecla']
        else:
            texto = accion['tipo']
        extra = {'evento': agente.evento_accion(accion, elementos, estado),
                 'firma_operativa': agente.firma_operativa(accion, elementos, estado)} if ampliado else {}
        traza.append({'clave': clave, 'accion': texto, **extra, 'resultado': {
            'cambio_observable': agente.huella(estado, elementos) != agente.huella(estado_despues, elementos_despues),
            'foco': estado_despues['foco'], 'ventana': estado_despues['ventana']}})
    if app.cumplida() != resultado['objetivo_logrado']:
        raise ValueError('El oráculo final no coincide con el registro original')
    return observaciones


def auditar(fuentes=FUENTES):
    llamadas, ejecuciones, excluidas = [], [], []
    for nombre, carpeta, bug_listo in fuentes:
        ruta = BASE / carpeta
        resultados = json.loads((ruta / 'resultados.json').read_text(encoding='utf-8'))
        for r in resultados:
            caso = next(c for c in CASOS if c['id'] == r['caso'])
            if caso.get('entorno') in ('guia', 'pregunta'):
                excluidas.append({'fuente': nombre, 'caso': r['caso'], 'semilla': r['semilla'], 'motivo': 'sin llamada al verificador de cumplimiento'})
                continue
            contaminacion = []
            if caso.get('etapas') and bug_listo:
                contaminacion.append('version_con_bug_LISTO_multietapa')
            if caso.get('etapas') and any(p['accion']['tipo'] == 'nada' and agente.final_confirmado(p.get('verificacion'))
                    and p['estado'].get('memoria_tarea', {}).get('etapa_activa') is not None for p in r['traza']):
                contaminacion.append('NADA_aceptado_sin_cerrar_etapas')
            filas = reconstruir(r, caso)
            ejecuciones.append({'fuente': nombre, 'caso': r['caso'], 'semilla': r['semilla'], 'llamadas': len(filas),
                                'contaminacion': contaminacion, 'correcto': r['correcto']})
            for f in filas:
                f.update(fuente=nombre, caso=r['caso'], semilla=r['semilla'], contaminacion=contaminacion)
                if f['oraculo'] is None:
                    f['celda'] = 'no_evaluable'
                else:
                    f['celda'] = ('acepta_correcto' if f['oraculo'] else 'acepta_falso') if f['cumplido'] else ('rechaza_correcto' if f['oraculo'] else 'rechaza_falso')
                llamadas.append(f)
    grupos = defaultdict(Counter)
    for f in llamadas:
        limpio = 'contaminadas' if f['contaminacion'] else 'sin_contaminacion_detectada'
        alcance = 'etapa' if f['ruta'] == 'verificacion_etapa' else 'global'
        grupos[(limpio, alcance, f['caso'])][f['celda']] += 1
    return {'ejecuciones_auditadas': ejecuciones, 'interacciones_sin_verificador': excluidas, 'llamadas': llamadas,
            'matrices': [{'estrato': k[0], 'alcance': k[1], 'caso': k[2], **dict(v)} for k, v in grupos.items()]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    resultado = auditar()
    with args.salida.open('x', encoding='utf-8') as archivo:
        json.dump(resultado, archivo, ensure_ascii=False, indent=2)
    print(json.dumps({'llamadas': len(resultado['llamadas']), 'ejecuciones': len(resultado['ejecuciones_auditadas'])}, ensure_ascii=True))


if __name__ == '__main__':
    main()
