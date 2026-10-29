"""Importa exclusivamente la demostración ficticia registrada por el simulador propio."""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import memoria


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    with urllib.request.urlopen('http://127.0.0.1:8108/estado', timeout=5) as respuesta:
        observado = json.load(respuesta)
    assert observado['estado']['caso'] == 'demo' and observado['estado']['guardados'] == 1
    pasos = []
    for ev in observado['demostracion']:
        assert ev['caso'] == 'demo'
        if ev['tipo'] == 'escritura':
            pasos.append('escribí «' + ev['valor'] + '» en «' + ev['campo'] + '»')
        elif ev['tipo'] == 'seleccion_servidor':
            pasos.append('clic en «' + ev['etiqueta'] + '»')
        elif ev['tipo'] == 'aplicar':
            pasos.append('clic en «' + ev['boton'] + '»')
    assert len(pasos) == 5
    args.salida.mkdir(parents=True, exist_ok=True)
    memoria.CONOCIMIENTO = str(args.salida / 'aprendizaje')
    memoria.RECETAS = str(args.salida / 'aprendizaje/recetas.jsonl')
    if Path(memoria.RECETAS).exists():
        raise ValueError('La receta de este ensayo ya existe: no duplicarla')
    objetivo = 'Crea una reserva DHCP para MAC AA:BB:CC:DD:EE:01, IP 192.168.20.83, VLAN 20'
    app = memoria.app_de('Laboratorio MikroTik — Fosfeno')
    memoria.guardar_receta(app, objetivo, pasos, 'demostracion')
    (args.salida / 'demostracion-observada.json').write_text(json.dumps({
        'metodo': 'Entradas reales sobre la GUI ficticia mediante Sky; señales del simulador registradas e importadas con memoria.guardar_receta. No grabador de voz/hotkeys ni mirame.py.',
        'observado': observado, 'pasos': pasos, 'objetivo': objetivo, 'app': app}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'receta': memoria.leer_recetas()[0], 'archivo': memoria.RECETAS}, ensure_ascii=True))


if __name__ == '__main__':
    main()
