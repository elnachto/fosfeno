import argparse
import json
from pathlib import Path
import re


def nota_y_regreso_v3(estado):
    guardado = estado.get('guardado')
    return bool(isinstance(guardado, str)
                and re.search(r'(?<!\w)417(?!\w)', guardado)
                and estado.get('revisado')
                and estado.get('ventana') == 'fuente')


def repuntuar(carpeta):
    filas = []
    for ruta in sorted(carpeta.rglob('resultados.json')):
        resultados = json.loads(ruta.read_text(encoding='utf-8'))
        if not isinstance(resultados, list):
            continue
        for r in resultados:
            if r.get('caso') != 'nota_y_regreso':
                continue
            estado = r['estado_final']
            v2 = bool(estado.get('guardado') == '417' and estado.get('revisado')
                      and estado.get('ventana') == 'fuente')
            if v2 != r['objetivo_logrado']:
                raise ValueError('El oráculo v2 reconstruido no coincide con ' + str(ruta))
            aceptado = bool(r['correcto'] or r['falso_exito_aceptado'])
            if bool(aceptado and v2) != r['correcto']:
                raise ValueError('El cierre v2 reconstruido no coincide con ' + str(ruta))
            v3 = nota_y_regreso_v3(estado)
            filas.append({'fuente': str(ruta), 'semilla': r['semilla'],
                'estado_final': estado, 'cierre_aceptado_registrado': aceptado,
                'oraculo_v2': v2, 'oraculo_v3': v3,
                'acierto_v2': r['correcto'], 'acierto_v3': bool(aceptado and v3),
                'falso_exito_v2': r['falso_exito_aceptado'],
                'falso_exito_v3': bool(aceptado and not v3)})
    return filas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--datos', type=Path, required=True)
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    filas = repuntuar(args.datos)
    with args.salida.open('x', encoding='utf-8') as archivo:
        json.dump(filas, archivo, ensure_ascii=False, indent=2)
    print(json.dumps({'ejecuciones': len(filas),
        'aciertos_v2': sum(r['acierto_v2'] for r in filas),
        'aciertos_v3': sum(r['acierto_v3'] for r in filas)}, ensure_ascii=True))


if __name__ == '__main__':
    main()
