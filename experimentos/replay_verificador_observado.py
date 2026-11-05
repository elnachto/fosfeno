import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import requests

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import agente
import marcas
from entornos_evaluacion import operacion, sin_entrada_nativa
from experimentos.banco_verificador import CASOS_POR_ID, contexto, guardar
from experimentos.replay_verificador import URL, contratos, filtrar, hojas, payload_v3


def expresion_pedida(e):
    c = contexto(e)
    pedidos = [e['objetivo']] + [t.get('objetivo', '') for t in c.get('memoria_tarea', {}).get('etapas', [])]
    for texto in pedidos:
        match = re.search(r'\b\d+\s*[+*]\s*\d+\b', texto)
        if match:
            return match.group().replace(' ', '')
        match = re.search(r'sumar\s+(\d+)\s+y\s+(\d+)', texto, re.I)
        if match:
            return match[1] + '+' + match[2]
    return None


def objetivos_visibles(e):
    caso = CASOS_POR_ID[e['caso']]
    modo = caso['modo']
    c = contexto(e)
    if modo.startswith('calculo'):
        expresion = expresion_pedida(e)
        return [operacion(expresion)] if expresion else []
    if modo in ('codigo', 'contacto', 'regreso'):
        hechos = c.get('memoria_tarea', {}).get('hechos_observados', {})
        valores = [str(v['valor']) for v in hechos.values() if v.get('valor') is not None and v.get('fuente') == 'Ficha']
        if valores:
            return valores
        if c.get('ventana') == 'Ficha':
            return re.findall(r'^(?:Código de entrega|Número de registro|Nombre|Ciudad):\s*(.+)$', c.get('texto_visible', ''), re.M)
        return []
    literales = re.findall(r'«([^»]+)»', e['objetivo'])
    if e['caso'] == 'checkbox':
        return [False] if re.search(r'\bdesactiva\b', e['objetivo'], re.I) else []
    if e['caso'] == 'selector':
        match = re.search(r'idioma a (.+?) y ', e['objetivo'], re.I)
        return [match[1]] if match else []
    if e['caso'] == 'cantidad':
        match = re.search(r'cantidad a (\d+)', e['objetivo'], re.I)
        return literales[:1] + ([match[1]] if match else [])
    if modo == 'navegar':
        return re.findall(r'https?://[^\s«»"<>]+', e['objetivo'])
    if modo == 'carpeta':
        return literales
    if modo in ('inicio', 'barra'):
        match = re.search(r'Abre\s+([^,.]+)', e['objetivo'], re.I)
        return [match[1].strip()] if match else []
    return literales


def contiene(texto, e):
    valores = objetivos_visibles(e)
    if not valores:
        return False
    if CASOS_POR_ID[e['caso']]['modo'] == 'regreso':
        return all(re.search(r'(?<!\w)' + re.escape(v) + r'(?!\w)', texto) for v in valores)
    return all(str(v).lower() in texto.lower() if isinstance(v, bool) else str(v) in texto for v in valores)


def prueba(e, identificador, campo):
    c = contexto(e)
    modo = CASOS_POR_ID[e['caso']]['modo']
    texto = c.get('texto_visible', '')
    normal = agente.normalizar(texto)
    memoria = c.get('memoria_tarea', {})
    etapas = memoria.get('etapas', [])
    hechos = memoria.get('hechos_observados', {})
    cita = hojas(c).get(campo, '')
    valores = objetivos_visibles(e)
    if identificador == 'ventana':
        return campo == '/ventana' and c.get('ventana') == 'Ficha'
    if identificador == 'casilla':
        return any(v.get('nombre') == 'Revisado' and v.get('activado') is True and campo == f'/controles/{i}/activado'
                   for i, v in enumerate(c.get('controles', [])))
    if identificador == 'lectura':
        if campo.startswith('/memoria_tarea/hechos_observados/') and campo.endswith('/valor'):
            conservados = '\n'.join(str(v.get('valor', '')) for v in hechos.values())
            if not contiene(conservados, e):
                return False
            return not modo.startswith('calculo') or any(t.get('n') == 1 and t.get('estado') == 'comprobada' for t in etapas)
        if campo == '/texto_visible' and contiene(texto, e):
            if modo.startswith('calculo'):
                acciones = '\n'.join(c.get('acciones_ejecutadas', []))
                return 'Resultado:' in texto and bool(expresion_pedida(e)) and expresion_pedida(e) in acciones and 'enter' in acciones
            return c.get('ventana') == 'Ficha'
        return False
    if identificador == 'guardado':
        if campo == '/texto_visible':
            return 'guardado correctamente:' in normal and contiene(texto, e)
        if re.fullmatch(r'/memoria_tarea/etapas/\d+/evidencia', campo):
            indice = int(campo.split('/')[3])
            etapa = etapas[indice]
            return etapa.get('n') == 2 and etapa.get('estado') == 'comprobada' and contiene(cita, e) and bool(re.search(r'guard|persist', agente.normalizar(cita)))
        return False
    if identificador == 'carpeta':
        historia = '\n'.join(c.get('acciones_ejecutadas', []))
        return bool(valores) and any(v.get('nombre') in valores and v.get('rol') == 'ListItem' for v in c.get('controles', [])) and c.get('ventana') == 'Program Manager' and 'ctrl+shift+n' in historia and 'enter' in historia and (campo == '/texto_visible' or campo.endswith('/nombre'))
    if identificador == 'aplicacion':
        return bool(valores) and all(v in c.get('ventana', '') for v in valores) and 'cargando' not in normal and campo in ('/ventana', '/texto_visible')
    if identificador == 'url':
        return campo == '/texto_visible' and contiene(texto, e) and 'pagina abierta:' in normal
    if identificador == 'pestana':
        return campo == '/texto_visible' and 'pestana nueva' in normal
    if identificador == 'resultado':
        return campo == '/texto_visible' and 'resultado encontrado para:' in normal and contiene(texto, e)
    if identificador == 'enviado':
        return campo == '/texto_visible' and 'mensaje enviado:' in normal and contiene(texto, e)
    if identificador == 'conversacion':
        return campo == '/texto_visible' and 'conversacion nueva' in normal
    if identificador == 'valores':
        campos = CASOS_POR_ID[e['caso']]['campos']
        if len(valores) != len(campos):
            return False
        for (_, rol, nombre, _), valor in zip(campos, valores):
            if not any(v.get('nombre') == nombre and v.get('activado' if isinstance(valor, bool) else 'valor') == valor for v in c.get('controles', [])):
                return False
        return campo == '/texto_visible' or campo.startswith('/controles/') or campo.startswith('/foco/')
    return False


def decidir(e, respuesta):
    exigidas = {i for i, _ in contratos(e)}
    filas = respuesta.get('condiciones', [])
    ids = [v.get('id') for v in filas if isinstance(v, dict)]
    problemas = []
    if len(ids) != len(filas) or len(ids) != len(set(ids)) or set(ids) != exigidas:
        problemas.append('Conjunto de condiciones incompleto, desconocido o duplicado')
    datos = hojas(contexto(e))
    for fila in filas:
        if not isinstance(fila, dict):
            problemas.append('Condición inválida')
            continue
        campo, evidencia = fila.get('campo', ''), fila.get('evidencia', '')
        if fila.get('observado') is not True:
            problemas.append(str(fila.get('id')) + ': no observado')
        elif not evidencia or campo not in datos or evidencia not in datos[campo]:
            problemas.append(str(fila.get('id')) + ': cita no sustentada')
        elif not prueba(e, fila.get('id'), campo):
            problemas.append(str(fila.get('id')) + ': condición no demostrada por ese campo')
    return filtrar(e, {'cumplido': not problemas, 'evidencia': 'Condiciones comprobadas por código' if not problemas else '',
        'pendiente': '; '.join(problemas)})


def ejecutar(banco, salida):
    salida.mkdir(parents=True, exist_ok=False)
    entradas = json.loads(banco.read_text(encoding='utf-8'))
    unidades = {}
    for e in entradas:
        unidades.setdefault(e['unidad'], e)
    props = requests.get(URL.rsplit('/v1/', 1)[0] + '/props', timeout=10)
    props.raise_for_status()
    guardar(salida / 'manifiesto.json', {'banco_sha256': hashlib.sha256(banco.read_bytes()).hexdigest(),
        'fuentes_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), BASE / 'experimentos/replay_verificador.py', BASE / 'agente.py']},
        'props': props.json(), 'variante': 'V3 solo observaciones; no consulta CASOS.esperado ni etiquetas privadas',
        'unidades': len(unidades)})
    def anexar(nombre, dato):
        with (salida / nombre).open('a', encoding='utf-8') as archivo:
            archivo.write(json.dumps(dato, ensure_ascii=False) + '\n')
    contador = 0
    with sin_entrada_nativa():
        for numero, e in enumerate(unidades.values(), 1):
            payload = payload_v3(e)
            ids = []
            for intento in range(2):
                contador += 1
                inicio = time.perf_counter()
                r = requests.post(URL, json=payload, timeout=120)
                segundos = time.perf_counter() - inicio
                r.raise_for_status()
                respuesta = r.json()
                if respuesta.get('model') != 'fosfeno-nemotron':
                    raise ValueError('Motor distinto del previsto')
                anexar('consultas.jsonl', {'id': contador, 'unidad': e['unidad'], 'entrada': e['id'],
                    'variante': 'V3', 'payload': payload, 'respuesta': respuesta, 'segundos': segundos,
                    'tokens': respuesta.get('usage', {}).get('completion_tokens')})
                ids.append(contador)
                if respuesta['choices'][0].get('finish_reason') == 'length' and intento == 0:
                    payload = {**payload, 'max_tokens': 2400}
                    continue
                dato = json.loads(marcas.leer_respuesta(respuesta))
                break
            v = decidir(e, dato)
            anexar('resultados.jsonl', {'unidad': e['unidad'], 'entrada_representante': e['id'],
                'votos': {'V3': {'veredicto': v, 'acepta': agente.final_confirmado(v), 'consultas': ids, 'condiciones_modelo': dato}}})
            anexar('estado.jsonl', {'terminadas': numero, 'total': len(unidades), 'consultas_http': contador})
            print(json.dumps({'terminadas': numero, 'total': len(unidades), 'entrada': e['id'],
                'acepta': agente.final_confirmado(v)}, ensure_ascii=True), flush=True)
    guardar(salida / 'terminado.json', {'unidades': len(unidades), 'consultas_http': contador})


def recalcular(banco, respuestas, salida):
    salida.mkdir(parents=True, exist_ok=False)
    entradas = json.loads(banco.read_text(encoding='utf-8'))
    unidades = {}
    for e in entradas:
        unidades.setdefault(e['unidad'], e)
    anteriores = [json.loads(x) for x in (respuestas / 'resultados.jsonl').read_text(encoding='utf-8').splitlines()]
    crudas = {v['id']: v for v in [json.loads(x) for x in (respuestas / 'consultas.jsonl').read_text(encoding='utf-8').splitlines()]}
    if len(anteriores) != len(unidades) or not (respuestas / 'terminado.json').exists():
        raise ValueError('La corrida fuente no está completa')
    guardar(salida / 'manifiesto.json', {'banco_sha256': hashlib.sha256(banco.read_bytes()).hexdigest(),
        'respuestas': str(respuestas.resolve()), 'consultas_nuevas': 0,
        'fuentes_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), BASE / 'experimentos/replay_verificador.py', BASE / 'agente.py']},
        'metodo': 'Mismo prompt/esquema/payload V3 y mismas condiciones emitidas; solo cambia el código de comprobación, sin literales del oráculo.'})
    with sin_entrada_nativa(), (salida / 'resultados.jsonl').open('x', encoding='utf-8') as archivo:
        for r in anteriores:
            e = unidades[r['unidad']]
            anterior = r['votos']['V3']
            if crudas[anterior['consultas'][0]]['payload'] != payload_v3(e):
                raise ValueError('El prompt V3 cambió; no se puede reutilizar la respuesta')
            v = decidir(e, anterior['condiciones_modelo'])
            archivo.write(json.dumps({'unidad': r['unidad'], 'entrada_representante': e['id'],
                'votos': {'V3': {'veredicto': v, 'acepta': agente.final_confirmado(v),
                    'consultas': anterior['consultas'], 'condiciones_modelo': anterior['condiciones_modelo']}}}, ensure_ascii=False) + '\n')
    guardar(salida / 'terminado.json', {'unidades': len(unidades), 'consultas_nuevas': 0})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--banco', type=Path, required=True)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--respuestas', type=Path)
    args = parser.parse_args()
    if args.respuestas:
        recalcular(args.banco, args.respuestas, args.salida)
    else:
        ejecutar(args.banco, args.salida)


if __name__ == '__main__':
    main()
