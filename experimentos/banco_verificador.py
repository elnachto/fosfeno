import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from unittest.mock import patch


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import agente
from evaluacion import AplicacionSimulada, CASOS
from entornos_evaluacion import EscritorioSimulado, operacion, sin_entrada_nativa
from experimentos.auditar_cierres import oraculo_etapa, reconstruir
from experimentos.oraculos_v3 import nota_y_regreso_v3


ANTERIOR = BASE / 'salidas/arnes-ampliado/v2/revision-cierres-01'
FUENTES = {
    'original-40': BASE / 'salidas/arnes-ampliado/medicion',
    'diagnostico-sin-corregir': BASE / 'salidas/arnes-ampliado/v2/paso1-diagnostico',
    'v2-listo': BASE / 'salidas/arnes-ampliado/v2/paso1-corregido',
    'v2-muestra-interrumpida': BASE / 'salidas/arnes-ampliado/v2/paso2-muestra10',
    'punto4-linea-base': ANTERIOR / 'punto4-linea-base',
    'punto7-muestra10': ANTERIOR / 'punto7-muestra10',
}
CASOS_POR_ID = {c['id']: c for c in CASOS}


def guardar(ruta, dato):
    with ruta.open('x', encoding='utf-8') as archivo:
        json.dump(dato, archivo, ensure_ascii=False, indent=2)


def huella(dato):
    return hashlib.sha256(json.dumps(dato, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def capturar(objetivo, elementos, estado, historial):
    capturado = {}
    def consulta(instruccion, texto, esquema, imagen=None):
        capturado.update(instruccion=instruccion, prompt=texto, esquema=esquema, imagen=imagen is not None)
        return {'cumplido': False, 'evidencia': '', 'pendiente': 'Solo reconstrucción'}
    agente.verificar(objetivo, elementos, estado, historial, consulta)
    return capturado


def contexto(entrada):
    return json.loads(entrada['consulta']['prompt'].split('\nCURRENT STATE:\n', 1)[1])


def etiqueta(entrada):
    caso = CASOS_POR_ID[entrada['caso']]
    privado = entrada['estado_privado']
    if caso['modo'] == 'regreso':
        if entrada['alcance'] == 'global':
            return nota_y_regreso_v3(privado)
        if entrada['etapa'] == 2:
            return bool(isinstance(privado.get('guardado'), str)
                        and re.search(r'(?<!\w)417(?!\w)', privado['guardado']))
    if entrada['alcance'] == 'etapa':
        app = SimpleNamespace(enviado=privado.get('guardado'), calculado=privado.get('calculado'),
            expresion=privado.get('expresion', ''), revisado=privado.get('revisado'),
            ventana=privado.get('ventana'), resultado_calculo=operacion(privado['expresion'])
            if privado.get('calculado') else '')
        verdad, _ = oraculo_etapa(caso, entrada['etapa'], app, entrada['estado'])
        return bool(verdad)
    if entrada['origen'] not in ('sintetico_positivo', 'sintetico_negativo'):
        return entrada['oraculo_v2']
    if caso['modo'].startswith('calculo'):
        return bool(privado.get('calculado') and privado['expresion'] == caso['expresion']
            and operacion(privado['expresion']) == caso['esperado'] and privado.get('guardado') == caso['esperado'])
    if caso['modo'] in ('codigo', 'contacto'):
        return privado.get('guardado') == caso['esperado']
    return entrada['oraculo_v2']


def etiqueta_v2(entrada):
    if not entrada['origen'].startswith('sintetico'):
        return entrada['oraculo_v2']
    if CASOS_POR_ID[entrada['caso']]['modo'] == 'regreso':
        privado = entrada['estado_privado']
        if entrada['alcance'] == 'global':
            return bool(privado.get('guardado') == '417' and privado.get('revisado')
                        and privado.get('ventana') == 'fuente')
        if entrada['etapa'] == 2:
            return privado.get('guardado') == '417'
    return etiqueta(entrada)


def cargar_etiquetas():
    filas = []
    historico = json.loads((ANTERIOR / 'punto3-matriz-datos.json').read_text(encoding='utf-8'))
    for v in historico['llamadas']:
        filas.append({**v, 'alcance': 'etapa' if v['ruta'] == 'verificacion_etapa' else 'global'})
    nuevo = json.loads((ANTERIOR / 'punto7-matriz-anexo.json').read_text(encoding='utf-8'))
    for v in nuevo['llamadas']:
        filas.append({**v, 'fuente': v['corrida'], 'contaminacion': [], 'veredicto': v['resultado_final']})
    return {(v['fuente'], v['caso'], v['semilla'], v['paso'], v['alcance']): v for v in filas}


def entrada_base(nombre, r, v, consulta, payload, numero):
    caso = CASOS_POR_ID[r['caso']]
    etapa = None if v['alcance'] == 'global' else v['etapa']
    objetivo = caso['objetivo'] if etapa is None else caso['etapas'][etapa - 1]
    return {'id': f"{nombre}:{r['caso']}:{r['semilla']}:{v['paso']}:{v['alcance']}",
        'origen': 'real_exacta', 'fuente': str(FUENTES[nombre]), 'linea': numero,
        'caso': r['caso'], 'semilla': r['semilla'], 'paso': v['paso'],
        'alcance': v['alcance'], 'etapa': etapa, 'objetivo': objetivo,
        'contaminacion': v['contaminacion'], 'oraculo_v2': v['oraculo'],
        'estado_privado': copy.deepcopy(v.get('estado_privado', r.get('estado_privado'))), 'consulta': copy.deepcopy(consulta),
        'payload': copy.deepcopy(payload), 'veredicto_guardado': copy.deepcopy(v['veredicto']),
        'fijo_paso17': nombre == 'v2-muestra-interrumpida' and r['caso'] == 'nota_y_regreso'
            and r['semilla'] == 42 and v['paso'] == 17 and etapa is None}


def reales():
    etiquetas = cargar_etiquetas()
    entradas = []
    for nombre, carpeta in FUENTES.items():
        if nombre == 'original-40':
            continue
        solicitudes = [json.loads(x) for x in (carpeta / 'consultas-crudas.jsonl').read_text(encoding='utf-8').splitlines()]
        for numero, linea in enumerate((carpeta / 'verificador.jsonl').read_text(encoding='utf-8').splitlines(), 1):
            r = json.loads(linea)
            if len(r['consultas']) != 1:
                raise ValueError('Cantidad de consultas inesperada')
            consulta = r['consultas'][0]
            if consulta['imagen']:
                raise ValueError('No se puede sustituir una imagen perdida')
            caso = CASOS_POR_ID[r['caso']]
            alcance = 'global' if r['objetivo_verificado'] == caso['objetivo'] else 'etapa'
            v = etiquetas[(nombre, r['caso'], r['semilla'], r['paso'], alcance)]
            candidatos = []
            for s in solicitudes:
                if not s.get('verificacion') or (s['caso'], s['semilla'], s['paso']) != (r['caso'], r['semilla'], r['paso']):
                    continue
                mensajes = s['peticion']['messages']
                contenido = mensajes[-1]['content']
                texto = contenido if isinstance(contenido, str) else '\n'.join(t.get('text', '') for t in contenido if t['type'] == 'text')
                if mensajes[0]['content'] == consulta['instruccion'] and texto == consulta['prompt']:
                    candidatos.append(s['peticion'])
            if not candidatos:
                raise ValueError('No se encontró payload original')
            e = entrada_base(nombre, r, v, consulta, candidatos[0], numero)
            e.update(elementos=r['elementos'], estado=r['estado'], historial=r['historial'])
            e['oraculo'] = etiqueta(e)
            e['prompt_regenerado_identico'] = all(capturar(e['objetivo'], e['elementos'], e['estado'], e['historial'])[k] == consulta[k]
                for k in ('instruccion', 'prompt', 'esquema'))
            entradas.append(e)
    return entradas


def reconstruidas():
    import experimentos.auditar_cierres as auditor
    import motor_ia
    etiquetas = cargar_etiquetas()
    rs = json.loads((FUENTES['original-40'] / 'resultados.json').read_text(encoding='utf-8'))
    entradas = []
    confirmar = agente.final_confirmado
    for r in rs:
        caso = CASOS_POR_ID[r['caso']]
        filas = [v for k, v in etiquetas.items() if k[0] == 'original-40' and k[1:3] == (r['caso'], r['semilla'])]
        if not filas:
            continue
        filas.sort(key=lambda v: (v['paso'], 0 if v['alcance'] == 'etapa' else 1))
        cuenta = [0]
        apps = []
        clase = EscritorioSimulado if caso.get('entorno') else AplicacionSimulada
        class App(clase):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.historial_replay = []
                self.ultimos_elementos = []
                apps.append(self)
            def observar(self):
                elementos, estado = super().observar()
                self.ultimos_elementos = elementos
                return elementos, estado
            def aplicar(self, accion):
                if accion['tipo'] == 'clic':
                    texto = 'clic en «' + self.ultimos_elementos[accion['n'] - 1][1] + '»'
                elif accion['tipo'] == 'escribir':
                    texto = ('reemplacé por «' if accion.get('reemplazar') else 'escribí «') + accion['texto'] + '»'
                elif accion['tipo'] == 'tecla':
                    texto = 'pulsé la tecla ' + accion['tecla']
                else:
                    texto = accion['tipo']
                super().aplicar(accion)
                self.historial_replay.append(texto)
        def capturar_cierre(veredicto):
            v = filas[cuenta[0]]
            cuenta[0] += 1
            p = r['traza'][v['paso'] - 1]
            estado = copy.deepcopy(p['estado'])
            elementos = apps[-1].ultimos_elementos
            historial = list(apps[-1].historial_replay)
            objetivo = caso['objetivo'] if v['alcance'] == 'global' else caso['etapas'][v['etapa'] - 1]
            consulta = capturar(objetivo, elementos, estado, historial)
            perfil = motor_ia.PERFILES['nemotron']
            payload = {'model': perfil['modelo_api'], **perfil['muestreo'], **perfil['opciones_api'],
                'max_tokens': 640, 'seed': r['semilla'], 'cache_prompt': False,
                'messages': [{'role': 'system', 'content': consulta['instruccion']},
                    {'role': 'user', 'content': [{'type': 'text', 'text': consulta['prompt']}]}],
                'response_format': {'type': 'json_schema', 'json_schema': {'name': 'respuesta_fosfeno',
                    'strict': True, 'schema': consulta['esquema']}}}
            e = entrada_base('original-40', r, v, consulta, payload, None)
            e.update(origen='reconstruida_no_exacta', elementos=elementos, estado=estado, historial=historial,
                limitacion='No se conservó el prompt ni todos los eventos de memoria/cierre. Historial físico reconstruido; no es una entrada original exacta.')
            e['oraculo'] = etiqueta(e)
            entradas.append(e)
            return confirmar(veredicto)
        with sin_entrada_nativa(), patch.object(auditor, 'EscritorioSimulado' if caso.get('entorno') else 'AplicacionSimulada', App), \
                patch.object(agente, 'final_confirmado', side_effect=capturar_cierre):
            reconstruir(r, caso)
        if cuenta[0] != len(filas):
            raise ValueError('No se recuperaron todas las observaciones')
    return entradas


def actualizar(e):
    e['consulta'] = capturar(e['objetivo'], e['elementos'], e['estado'], e['historial'])
    e['payload']['messages'] = [{'role': 'system', 'content': e['consulta']['instruccion']},
        {'role': 'user', 'content': [{'type': 'text', 'text': e['consulta']['prompt']}]}]
    e['oraculo'] = etiqueta(e)
    return e


def sinteticas(entradas):
    elegidas = {}
    for e in entradas:
        if e['oraculo'] and not e['contaminacion']:
            elegidas.setdefault((e['caso'], e['alcance'], e['etapa']), e)
    resultado = []
    def nueva(base, tipo, positiva):
        e = copy.deepcopy(base)
        e.update(id='sintetica:' + tipo + ':' + base['id'], origen='sintetico_positivo' if positiva else 'sintetico_negativo',
            base_id=base['id'], mutacion=tipo, transformaciones=[])
        e.pop('veredicto_guardado', None)
        e['fijo_paso17'] = False
        return e
    def finalizar(e, positiva):
        actualizar(e)
        if e['oraculo'] != positiva:
            raise ValueError('Mutación no aislada o etiqueta incorrecta: ' + e['id'])
        e['oraculo_v2_base'] = e['oraculo_v2']
        e['oraculo_v2'] = etiqueta_v2(e)
        resultado.append(e)
    for base in elegidas.values():
        e = nueva(base, 'controles_permutados', True)
        n = len(e['elementos'])
        e['elementos'].reverse()
        e['estado']['detalles'] = {str(n + 1 - int(k)): v for k, v in e['estado'].get('detalles', {}).items()}
        if e['estado'].get('foco', {}).get('n'):
            e['estado']['foco']['n'] = n + 1 - e['estado']['foco']['n']
        e['transformaciones'] = ['Orden de controles y sus ids, detalles y foco permutados juntos; mismos valores y estado privado.']
        finalizar(e, True)
        caso = CASOS_POR_ID[base['caso']]
        if caso['modo'] in ('codigo', 'calculo_teclado') and base['estado']['ventana'] == 'Notas' and (base['alcance'] == 'global' or base['etapa'] == 2):
            for tipo, valor in [('nota_vacia', ''), ('nota_distinta', '9999'), ('etapa_final_sin_guardar', None)]:
                e = nueva(base, tipo, False)
                texto_campo = caso['esperado'] if valor is None else valor
                for i, elemento in enumerate(e['elementos'], 1):
                    if elemento[1] == 'Cuerpo de la nota':
                        e['estado'].setdefault('detalles', {})[str(i)] = {'valor': texto_campo}
                        if e['estado'].get('foco', {}).get('n') == i:
                            e['estado']['foco']['valor'] = texto_campo
                e['estado']['texto_visible'] = 'Sin confirmar ni guardar' if valor is None else 'Guardado correctamente: ' + valor
                e['estado_privado']['guardado'] = valor
                for etapa in e['estado'].get('memoria_tarea', {}).get('etapas', []):
                    if etapa['n'] == 2:
                        etapa.update(estado='activa' if valor is None else etapa['estado'],
                            evidencia='' if valor is None else e['estado']['texto_visible'])
                e['transformaciones'] = ['Solo falla persistencia/contenido requerido: campo, confirmación visible y evidencia de guardado coherentes; hechos fuente y cálculo intactos.']
                finalizar(e, False)
        if caso['modo'] == 'regreso' and (base['alcance'] == 'global' or base['etapa'] == 3):
            e = nueva(base, 'revisado_apagado', False)
            e['estado_privado']['revisado'] = False
            for i, elemento in enumerate(e['elementos'], 1):
                if elemento[1] == 'Revisado':
                    e['estado']['detalles'][str(i)]['activado'] = False
            e['estado']['texto_visible'] = e['estado']['texto_visible'].replace('\nRevisado: activado', '')
            for etapa in e['estado'].get('memoria_tarea', {}).get('etapas', []):
                if etapa['n'] == 3:
                    etapa.update(estado='activa', evidencia='')
            e['transformaciones'] = ['Solo casilla apagada; se retira su confirmación y se deja su etapa sin comprobar. Nota y ventana fuente intactas.']
            finalizar(e, False)
        if caso['modo'] == 'regreso' and base['alcance'] == 'global':
            e = nueva(base, 'ventana_equivocada', False)
            app = EscritorioSimulado(caso, e['semilla'])
            app.ventana = 'nota'
            app.enviado = e['estado_privado']['guardado']
            app.valores['cuerpo'] = app.enviado
            app.revisado = True
            app.resultado = 'Guardado correctamente: ' + app.enviado
            e['elementos'], estado = app.observar()
            estado['memoria_tarea'] = e['estado'].get('memoria_tarea', {})
            e['estado'] = estado
            e['estado_privado']['ventana'] = 'nota'
            e['historial'].append('clic en «Notas»')
            e['transformaciones'] = ['Solo ventana final Notas en vez de Ficha; nota y casilla permanecen correctas. Se observa el contenido realista de Notas.']
            finalizar(e, False)
            e = nueva(base, 'nota_etiquetada_417', True)
            e['estado_privado']['guardado'] = 'Registro: 417'
            for etapa in e['estado'].get('memoria_tarea', {}).get('etapas', []):
                if etapa['n'] == 2:
                    etapa['evidencia'] = 'Guardado correctamente: Registro: 417'
            e['transformaciones'] = ['Formato equivalente bajo oráculo v3: nota persistida Registro: 417 y resumen de guardado fiel; número fuente, ventana y casilla intactos.']
            finalizar(e, True)
    return resultado


def construir(carpeta):
    carpeta.mkdir(parents=True, exist_ok=False)
    exactas = reales()
    aproximadas = reconstruidas()
    sintesis = sinteticas(exactas)
    todas = exactas + aproximadas + sintesis
    for e in todas:
        e['unidad'] = huella({'payload': e['payload'], 'objetivo': e['objetivo'],
            'elementos': e['elementos'], 'estado': e['estado'], 'historial': e['historial']})
    grupos = {}
    for e in todas:
        grupos.setdefault(e['unidad'], []).append(e)
    conflictos = [{ 'unidad': k, 'ids': [e['id'] for e in v]} for k, v in grupos.items() if len({e['oraculo'] for e in v}) > 1]
    if conflictos:
        raise ValueError('Entradas indistinguibles con etiquetas incompatibles: ' + json.dumps(conflictos))
    guardar(carpeta / 'banco.json', todas)
    guardar(carpeta / 'casos-fijos.json', [e['id'] for e in todas if e.get('fijo_paso17')])
    resumen = {'entradas': len(todas), 'unidades': len(grupos), 'por_origen': {},
        'limitacion': '70 prompts originales perdidos; solo anexo aproximado, nunca etiquetados como reales exactos.',
        'fuentes_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), BASE / 'agente.py', BASE / 'experimentos/oraculos_v3.py']}}
    for origen in sorted({e['origen'] for e in todas}):
        es = [e for e in todas if e['origen'] == origen]
        resumen['por_origen'][origen] = {'entradas': len(es), 'positivas': sum(e['oraculo'] for e in es),
            'negativas': sum(not e['oraculo'] for e in es), 'contaminadas': sum(bool(e['contaminacion']) for e in es),
            'unidades': len({e['unidad'] for e in es})}
    guardar(carpeta / 'resumen.json', resumen)
    return resumen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    with sin_entrada_nativa():
        resultado = construir(args.salida)
    print(json.dumps(resultado, ensure_ascii=True))


if __name__ == '__main__':
    main()
