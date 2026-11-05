import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jarvis
import rendimiento
from entornos_evaluacion import sin_entrada_nativa


class Reloj:
    def __init__(self):
        self.valor = 0.0

    def ahora(self):
        return self.valor

    def avanzar(self, segundos):
        self.valor += segundos


def medir():
    reloj = Reloj()
    estado = {'ventana': 'Panel simulado', 'hwnd': 10, 'foco': {}, 'detalles': {}, 'texto_visible': 'Botón Seleccionar'}
    elementos = [('Button', 'Seleccionar', 0, 0, 100, 30)]
    imagen = MagicMock(size=(500, 400))
    imagen.save.side_effect = lambda *a, **k: reloj.avanzar(.03)
    propuestas = iter([{'tipo': 'clic', 'n': 1}, {'tipo': 'nada'}])
    def consulta():
        with rendimiento.actividad('consulta_modelo_s'):
            reloj.avanzar(2.2)
            rendimiento.registrar_consulta({'uso': {'completion_tokens': 100}, 'segundos': 2.2,
                                            'timings': {'prompt_ms': 200, 'predicted_ms': 2000}})
    def decidir(*a, **k):
        consulta()
        return next(propuestas), '{}', '', imagen, 2.2
    def verificar(*a, **k):
        consulta()
        return {'cumplido': False, 'evidencia': '', 'pendiente': 'Fin de la simulación'}
    def escanear():
        reloj.avanzar(.7)
        return imagen, estado['ventana'], elementos
    def reobservar(*a, **k):
        reloj.avanzar(.04)
        return estado
    def validar(*a, **k):
        reloj.avanzar(.03)
        return True
    def accion(segundos):
        def ejecutar(*a, **k):
            reloj.avanzar(segundos)
            return True
        return ejecutar
    def esperar(segundos):
        reloj.avanzar(segundos)
        return False
    with tempfile.TemporaryDirectory() as carpeta, sin_entrada_nativa(), ExitStack() as pila:
        ruta = Path(carpeta) / 'pasos.jsonl'
        pila.enter_context(patch.dict('os.environ', {'FOSFENO_TIEMPOS_LOG': str(ruta)}))
        pila.enter_context(patch.object(rendimiento.time, 'perf_counter', side_effect=reloj.ahora))
        pila.enter_context(patch.object(jarvis.time, 'monotonic', side_effect=reloj.ahora))
        pila.enter_context(patch.object(jarvis.time, 'sleep', side_effect=reloj.avanzar))
        pila.enter_context(patch.dict(rendimiento.ULTIMOS, {'captura_percepcion_s': .7}, clear=True))
        for nombre, valor in [('OUT', carpeta), ('ESTADO_UI', estado), ('PERFIL', {'agente_estado': True, 'nombre': 'Simulación'})]:
            pila.enter_context(patch.object(jarvis.marcas, nombre, valor))
        for modulo, nombre, funcion in [
            (jarvis.marcas, 'partir_objetivo', lambda *a: []),
            (jarvis.marcas, 'decidir_accion', decidir),
            (jarvis.marcas, 'capturar_estado', reobservar),
            (jarvis.marcas, 'nombre_ventana', lambda: estado['ventana']),
            (jarvis.marcas, 'validar_destino', validar),
            (jarvis.marcas, 'evidencia_archivos', lambda *a: []),
            (jarvis.marcas, 'evidencia_copias', lambda *a: []),
            (jarvis, 'escanear', escanear),
            (jarvis, 'es_mi_consola', lambda *a: False),
            (jarvis, 'esperar_cancelacion', esperar),
            (jarvis.agente, 'verificar', verificar),
            (jarvis.memoria, 'buscar_recetas', lambda *a: []),
            (jarvis.acciones, 'mover_suave', accion(.42)),
            (jarvis.acciones, 'clic', accion(.13)),
        ]:
            pila.enter_context(patch.object(modulo, nombre, side_effect=funcion))
        for nombre in ('avisar', 'control', 'guardar_exito'):
            pila.enter_context(patch.object(jarvis, nombre))
        capa = MagicMock()
        capa.activa.return_value = True
        pila.enter_context(patch.object(jarvis, 'capa', capa))
        jarvis.ejecutar('Selecciona el control observado', (imagen, estado['ventana'], elementos), 'reloj-virtual')
        filas = [json.loads(s) for s in ruta.read_text(encoding='utf-8').splitlines()]
    return {'tipo': 'reloj virtual; percepción, modelo, cancelación y acciones sustituidos; cero entrada nativa',
            'valores_inyectados_s': {'captura': .7, 'consulta': 2.2, 'movimiento': .42, 'clic': .13, 'reobservacion': .04, 'validacion': .03, 'persistencia': .03},
            'pasos': filas}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--salida', type=Path, default=Path('salidas/arnes-ampliado/tiempos-simulados.json'))
    args = parser.parse_args()
    resultado = medir()
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resultado, ensure_ascii=True))


if __name__ == '__main__':
    main()
