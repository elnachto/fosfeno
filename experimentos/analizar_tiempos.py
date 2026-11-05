import argparse
import json
from pathlib import Path
import statistics


def analizar(filas):
    con_consulta = [r for r in filas if r.get('consultas', 0)]
    def resumen(grupo):
        media = lambda funcion: statistics.mean(funcion(r) for r in grupo) if grupo else None
        campos = ('segundos', 'captura_percepcion_s', 'prompt_local_s', 'prompt_servidor_s', 'generacion_s', 'consulta_http_s')
        fases = sorted({k for r in grupo for k in r.get('fases_exclusivas_s', {})})
        return {'pasos': len(grupo), 'medias_s': {k: media(lambda r, k=k: r.get(k, 0)) for k in campos},
                'residuo_tras_servidor_s': media(lambda r: r['segundos'] - sum(r.get(k, 0) for k in campos[1:5])),
                'residuo_tras_http_s': media(lambda r: r['segundos'] - sum(r.get(k, 0) for k in ('captura_percepcion_s', 'prompt_local_s', 'consulta_http_s'))),
                'fases_exclusivas_medias_s': {k: media(lambda r, k=k: r.get('fases_exclusivas_s', {}).get(k, 0)) for k in fases},
                'pasos_sin_desglose': sum('fases_exclusivas_s' not in r for r in grupo),
                'primeros_pasos_sin_captura_inicial_separada': sum(r.get('paso') == 1 and 'captura_inicial_fuera_paso_s' not in r for r in grupo)}
    tipos = sorted({(r.get('accion') or {}).get('tipo', 'sin_accion') for r in con_consulta})
    return {'criterio': 'solo pasos con consultas; medias de registros, no estimaciones de fases ausentes',
            'total_registros': len(filas), 'con_consulta': resumen(con_consulta),
            'por_accion': {tipo: resumen([r for r in con_consulta if (r.get('accion') or {}).get('tipo', 'sin_accion') == tipo]) for tipo in tipos}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--entrada', type=Path, default=Path('salidas/prueba-nativa/pasos.jsonl'))
    parser.add_argument('--salida', type=Path, default=Path('salidas/arnes-ampliado/analisis-tiempos.json'))
    args = parser.parse_args()
    filas = [json.loads(s) for s in args.entrada.read_text(encoding='utf-8').splitlines() if s.strip()]
    resultado = analizar(filas)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resultado, ensure_ascii=True))


if __name__ == '__main__':
    main()
