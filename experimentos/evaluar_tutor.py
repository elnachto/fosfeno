"""Comparación exploratoria de explicaciones; no ejecuta acciones en aplicaciones."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import tutor_experimental as tutor
import marcas
import motor_ia

CASOS = [
    {'id': 'subredes', 'pregunta': 'Las dos computadoras están conectadas al mismo switch, pero la prueba entre ellas falla. Explícame el problema y una corrección mínima, sin añadir equipos. Después explica cómo comprobarías la corrección.',
     'observaciones': 'Caso de diagnóstico proporcionado para evaluación, no captura de la aplicación: PC-A IPv4 192.168.10.10 máscara 255.255.255.0; PC-B IPv4 192.168.20.20 máscara 255.255.255.0. Enlaces Up, mismo switch de capa 2 y misma VLAN. No hay router. PDU fallida.'},
    {'id': 'evidencia_insuficiente', 'pregunta': 'Veo los dos enlaces verdes. ¿Ya puedo afirmar que la red funciona? Explica qué comprobaciones faltan y cómo hacerlas gráficamente.',
     'observaciones': 'Caso de diagnóstico proporcionado para evaluación: dos PCs y un switch; enlaces verdes. No se han abierto las configuraciones IP, no conocemos las máscaras y no se ejecutó ninguna PDU.'},
    {'id': 'ip_duplicada', 'pregunta': 'La comunicación de estas computadoras es inestable. ¿Qué problema demuestra la configuración observada y cómo lo corregirías sin modificar la dirección de PC-A? Explica qué deberíamos probar después.',
     'observaciones': 'Caso de diagnóstico proporcionado para evaluación: mismo switch y misma VLAN, enlaces Up. PC-A IPv4 10.24.8.11 máscara 255.255.255.0; PC-B IPv4 10.24.8.11 máscara 255.255.255.0. No hay router ni servidor DHCP. La configuración es estática.'},
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manuales', required=True, type=Path)
    p.add_argument('--salida', required=True, type=Path)
    args = p.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    marcas.PERFIL = dict(motor_ia.PERFILES['nemotron'], semilla=42, cache_prompt=False)
    def consultar(instruccion, texto, schema):
        r = marcas._consultar_json(marcas.PERFIL['url'], marcas.PERFIL['modelo_api'], instruccion, texto, schema)
        assert marcas.PETICIONES[-1]['modelo_servidor'] == 'fosfeno-nemotron'
        return r
    manifiesto = {'tipo': 'Casos de diagnóstico textuales; no redes ejecutadas', 'semilla': 42, 'casos': CASOS,
                   'codigo_sha256': {n: hashlib.sha256((BASE / n).read_bytes()).hexdigest() for n in ('tutor_experimental.py', 'experimentos/evaluar_tutor.py')},
                   'orden': 'Por caso, alternando orden de condiciones para no agrupar todo el contexto documental al final.',
                   'criterios': {
                       'subredes': ['Detecta distintas subredes', 'Propone PC-B única en 192.168.10.0/24 sin alterar PC-A', 'Repite prueba de conectividad', 'No afirma haber corregido ni probado'],
                       'evidencia_insuficiente': ['Enlaces verdes no prueban IP', 'Pide revisar IP y máscara', 'Propone PDU y leer resultado', 'No declara red verificada'],
                       'ip_duplicada': ['Identifica IP duplicada', 'Mantiene PC-A y propone IP-B única en 10.24.8.0/24', 'Verifica conectividad después', 'No declara reparación aplicada']}}
    (args.salida / 'manifiesto-diagnosticos.json').write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding='utf-8')
    for i, caso in enumerate(CASOS):
        for documentos in ((False, True) if i % 2 == 0 else (True, False)):
            etiqueta = caso['id'] + ('-documentado' if documentos else '-sin-manuales')
            start, nreq = time.monotonic(), len(marcas.PETICIONES)
            try:
                r = tutor.crear_leccion('Cisco Packet Tracer 8.2.2', caso['pregunta'], [], consultar,
                                       caso['observaciones'], documentos, args.manuales)
            except Exception as e:
                r = {'error': str(e)}
            r.update(segundos=round(time.monotonic() - start, 3), peticiones=marcas.PETICIONES[nreq:])
            (args.salida / (etiqueta + '.json')).write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
            print(etiqueta, 'guardado', round(time.monotonic() - start, 1), flush=True)


if __name__ == '__main__':
    main()
