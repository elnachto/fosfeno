"""Evalúa lecturas citadas en una captura fija; nunca controla la PC."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from PIL import Image

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import lectura_visual
import marcas
import percepcion_ocr


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--imagen', type=Path, required=True)
    p.add_argument('--casos', type=Path, required=True)
    p.add_argument('--salida', type=Path, required=True)
    p.add_argument('--controlador', action='store_true', help='Ejercitar también la propuesta de acción, sin ejecutarla')
    a = p.parse_args()
    casos = json.loads(a.casos.read_text(encoding='utf8'))
    if not isinstance(casos, list) or not 1 <= len(casos) <= 12:
        raise ValueError('Se requieren entre uno y doce casos')
    a.salida.mkdir(parents=True, exist_ok=True)
    img = Image.open(a.imagen).convert('RGB')
    es, ds, parcial = percepcion_ocr.etiquetas(img, (0, 0, *img.size), 0)
    estado = {'detalles': {str(n): ds[e] for n, e in enumerate(es, 1)}}
    refs = lectura_visual.referencias(es, estado)
    candidatas = lectura_visual.candidatas(refs, casos[0]['objetivo'])
    estado.update(percepcion_ocr=True, archivos_observados=[], copias_observadas=[])
    import memoria
    memoria.CONOCIMIENTO = str(a.salida/'conocimiento-aislado')
    memoria.RECETAS = str(a.salida/'conocimiento-aislado'/'recetas.jsonl')
    marcas.PERFIL = dict(marcas.PERFIL, semilla=42, cache_prompt=False)
    (a.salida/'condiciones.json').write_text(json.dumps({
        'tipo': 'Desarrollo: lectura de captura fija, sin acciones ni recetas', 'casos': casos,
        'controlador': a.controlador,
        'imagen_sha256': hashlib.sha256(a.imagen.read_bytes()).hexdigest(),
        'codigo_sha256': {n: hashlib.sha256((BASE/n).read_bytes()).hexdigest()
                          for n in ('lectura_visual.py', 'percepcion_ocr.py', 'agente.py')},
        'referencias': list(refs.values()), 'captura_incompleta': parcial}, ensure_ascii=False, indent=2), encoding='utf8')
    (a.salida/'candidatas-primer-caso.json').write_text(json.dumps(candidatas, ensure_ascii=False, indent=2), encoding='utf8')
    resultados = []
    for caso in casos:
        comienzo, nreq = time.monotonic(), len(marcas.PETICIONES)
        llamadas = []
        def consultar(sistema, prompt, schema, imagen):
            r = marcas.preguntar_json(sistema, prompt, schema, imagen)
            llamadas.append({'seleccion': r})
            return r
        r = {'id': caso['id'], 'objetivo': caso['objetivo']}
        try:
            if a.controlador:
                accion, crudo, _, _, _ = marcas.decidir_accion(caso['objetivo'], img,
                    'Captura de aplicación propia', es, [], estado=estado)
                r.update(accion=accion, crudo=crudo, ejecutada=False)
                r['referencias_validas'] = bool(accion.get('_revision_lectura'))
                if r['referencias_validas']:
                    r['lectura'] = accion['_revision_lectura']
            else:
                r['lectura'] = lectura_visual.leer(caso.get('propuesta', ''), es, estado, img,
                                                  consultar, caso['objetivo'])
                r['referencias_validas'] = True
        except (ValueError, TypeError, marcas.ErrorRespuestaModelo) as error:
            r.update(referencias_validas=False, rechazo=str(error), tipo_error=type(error).__name__)
        r.update(selecciones=llamadas, segundos=round(time.monotonic()-comienzo, 3),
                 peticiones=marcas.PETICIONES[nreq:])
        if any(p['modelo_servidor'] != 'fosfeno-nemotron' for p in r['peticiones']):
            raise ValueError('Este ensayo requiere el servidor Nemotron esperado')
        resultados.append(r)
        (a.salida/'resultados.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({k: v for k, v in r.items() if k not in ('peticiones', 'selecciones')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
