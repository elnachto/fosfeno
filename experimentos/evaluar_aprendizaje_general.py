"""Referencias de demostración en apps simuladas; no usa el grabador ni opera la PC."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import sys
import tempfile
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import evaluacion
import memoria


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    sello = secrets.token_hex(2)
    ejemplos = [
        ('agenda', [('nombre', 'Nombre', 'Elena', 'Persona '+sello),
                    ('ciudad', 'Ciudad', 'Tarija', 'Ciudad '+sello)]),
        ('inventario', [('producto', 'Producto', 'Lapiceros', 'Carpeta '+sello),
                       ('cantidad', 'Cantidad', '4', str(10+secrets.randbelow(30)))]),
        ('biblioteca', [('titulo', 'Título', 'Libro anterior', 'Cuaderno '+sello),
                       ('autor', 'Autor', 'Autor anterior', 'Autor '+sello)]),
    ]
    resultados, fixtures = [], []
    with tempfile.TemporaryDirectory() as carpeta, patch.object(memoria, 'CONOCIMIENTO', carpeta), \
            patch.object(memoria, 'RECETAS', str(Path(carpeta)/'recetas.jsonl')):
        for nombre, campos in ejemplos:
            app = memoria.app_de('Aplicación de prueba: '+nombre)
            objetivo_demo = 'Crea un registro con '+', '.join(n+' «'+viejo+'»' for _,n,viejo,_ in campos)+' y guárdalo.'
            pasos = []
            for _, etiqueta, viejo, _ in campos:
                pasos.extend(['clic en «'+etiqueta+'»', 'escribí «'+viejo+'» en «'+etiqueta+'»'])
            pasos.append('clic en «Guardar registro»')
            memoria.guardar_receta(app, objetivo_demo, pasos, 'demostracion')
            objetivo = 'Crea un registro con '+', '.join(n+' «'+nuevo+'»' for _,n,_,nuevo in campos)+' y guárdalo.'
            rs = memoria.buscar_recetas(objetivo, app)
            assert rs and all(r['app']==app and 'plantilla' not in r for r in rs)
            refs = {'recetas': memoria.texto_recetas(rs, objetivo)}
            caso = {'id':nombre, 'modo':'guardar', 'objetivo':objetivo,
                    'campos':[(clave,'Edit',etiqueta,'') for clave,etiqueta,_,_ in campos],
                    'esperado':{clave:nuevo for clave,_,_,nuevo in campos}, 'boton':'Guardar registro'}
            fixtures.append({'caso':caso, 'demostracion':{'objetivo':objetivo_demo,'pasos':pasos}, 'referencias':refs})
            r = evaluacion.ejecutar_caso(caso, 'nemotron', 42, referencias=refs)
            resultados.append(r)
            (args.salida/'resultados.json').write_text(json.dumps(resultados,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps({k:r[k] for k in ('caso','correcto','motivo','valor_final','falso_exito_aceptado')},ensure_ascii=False),flush=True)
    manifiesto = {'tipo':'Apps simuladas con modelo real y memoria aislada temporal',
                  'alcance':'Se prueba guardar/recuperar referencias y adaptar valores. No grabador Mírame, voz, GUI real ni benchmark ciego.',
                  'semilla_modelo':42, 'fixture_sufijo':sello, 'fixtures':fixtures,
                  'codigo_sha256':{n:hashlib.sha256((BASE/n).read_bytes()).hexdigest()
                                   for n in ('agente.py','precondiciones.py','memoria.py','tareas.py','evaluacion.py')}}
    (args.salida/'manifiesto.json').write_text(json.dumps(manifiesto,ensure_ascii=False,indent=2),encoding='utf8')
    resumen = {'correctos':sum(r['correcto'] for r in resultados), 'total':len(resultados),
               'falsos_exitos':sum(r['falso_exito_aceptado'] for r in resultados)}
    (args.salida/'resumen.json').write_text(json.dumps(resumen,indent=2),encoding='utf8')
    print(json.dumps(resumen),flush=True)


if __name__=='__main__':
    main()
