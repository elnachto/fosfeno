"""Revisión retrospectiva de respuestas guardadas; no controla la aplicación.

Los ejemplos son de desarrollo, conocidos durante la implementación.
No constituyen una evaluación independiente de generalización.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import marcas
import motor_ia
import tutor_experimental as tutor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entradas', required=True, type=Path)
    parser.add_argument('--salida', required=True, type=Path)
    args = parser.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    marcas.PERFIL = dict(motor_ia.PERFILES['nemotron'], semilla=42, cache_prompt=False)

    def consultar(instruccion, texto, schema):
        r = marcas._consultar_json(marcas.PERFIL['url'], marcas.PERFIL['modelo_api'], instruccion, texto, schema)
        if marcas.PETICIONES[-1]['modelo_servidor'] != marcas.PERFIL['modelo_api']:
            raise ValueError('El servidor informó otro modelo')
        return r

    restricciones = {'equipos_permitidos': ['PC0', 'PC1', 'Switch0'],
                      'configuracion_fija': {'PC0': {'ipv4': '192.168.1.1', 'mascara': '255.255.255.0', 'gateway': '0.0.0.0'}}}
    casos = [('leccion-red-v3.json', 'leccion-documentada', {}),
             ('diagnostico-real.json', 'diagnostico-documentado-critica', {}),
             ('diagnostico-real.json', 'diagnostico-documentado-reglas', restricciones),
             ('diagnostico-real-sin-manuales.json', 'diagnostico-sin-manuales', restricciones)]
    for archivo, etiqueta, limites in casos:
        ruta = args.entradas / archivo
        original = ruta.read_bytes()
        candidato = json.loads(original)
        inicio, n = time.monotonic(), len(marcas.PETICIONES)
        try:
            revision = tutor.revisar_leccion(candidato, consultar, limites)
        except Exception as exc:
            revision = {'estado': 'ERROR_REVISION', 'error': str(exc)}
        resultado = {'entrada': archivo, 'entrada_sha256': hashlib.sha256(original).hexdigest(),
                     'codigo_sha256': hashlib.sha256((BASE / 'tutor_experimental.py').read_bytes()).hexdigest(),
                     'tipo': 'Revisión retrospectiva de desarrollo, mismo modelo', 'semilla': 42,
                     'restricciones': limites, 'revision': revision,
                     'segundos': round(time.monotonic() - inicio, 3), 'peticiones': marcas.PETICIONES[n:]}
        (args.salida / (etiqueta + '.json')).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
        print(etiqueta, revision['estado'], flush=True)


if __name__ == '__main__':
    main()
