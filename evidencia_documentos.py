"""Inspección acotada y de solo lectura de documentos guardados."""
from zipfile import ZipFile
import xml.etree.ElementTree as ET

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'


def resumen_docx(ruta):
    def leer(zip_file, nombre):
        info = zip_file.getinfo(nombre)
        if info.file_size > 2_000_000:
            raise ValueError('XML demasiado grande para la verificación acotada')
        return ET.fromstring(zip_file.read(nombre))

    with ZipFile(ruta) as zip_file:
        documento = leer(zip_file, 'word/document.xml')
        estilos_xml = leer(zip_file, 'word/styles.xml') if 'word/styles.xml' in zip_file.namelist() else ET.Element('styles')
    estilos = {e.get(W + 'styleId'): e for e in estilos_xml.findall('w:style', NS)}

    def propiedades(elemento):
        if elemento is None:
            return {}
        salida = {}
        negrita = elemento.find('w:rPr/w:b', NS)
        if negrita is not None:
            salida['negrita'] = negrita.get(W + 'val', '1').lower() not in ('0', 'false', 'off')
        alineacion = elemento.find('w:pPr/w:jc', NS)
        if alineacion is not None:
            salida['alineacion'] = alineacion.get(W + 'val')
        return salida

    def resolver(ident, vistos=()):
        if ident not in estilos or ident in vistos:
            return {}
        estilo = estilos[ident]
        padre = estilo.find('w:basedOn', NS)
        return {**(resolver(padre.get(W + 'val'), vistos + (ident,)) if padre is not None else {}), **propiedades(estilo)}

    normal = next((e.get(W + 'styleId') for e in estilos.values()
                   if e.get(W + 'type') == 'paragraph' and e.get(W + 'default') == '1'), 'Normal')
    base = {'negrita': False, 'alineacion': 'left'}
    predeterminados = estilos_xml.find('w:docDefaults', NS)
    if predeterminados is not None:
        for origen in ('w:rPrDefault', 'w:pPrDefault'):
            base.update(propiedades(predeterminados.find(origen, NS)))
    parrafos = []
    nodos = documento.findall('.//w:body/w:p', NS)
    truncado = len(nodos) > 80
    for p in nodos[:80]:
        estilo = p.find('w:pPr/w:pStyle', NS)
        formato = {**base, **resolver(estilo.get(W + 'val') if estilo is not None else normal), **propiedades(p)}
        partes = []
        for r in p.findall('w:r', NS):
            texto = ''.join(t.text or '' for t in r.findall('.//w:t', NS))
            if not texto:
                continue
            truncado = truncado or len(texto) > 500
            estilo_r = r.find('w:rPr/w:rStyle', NS)
            fr = {**formato, **(resolver(estilo_r.get(W + 'val')) if estilo_r is not None else {}), **propiedades(r)}
            partes.append({'texto': texto[:500], 'negrita': fr['negrita']})
        texto = ''.join(r['texto'] for r in partes)
        if texto:
            truncado = truncado or len(texto) > 1600 or len(partes) > 20
            parrafos.append({'texto': texto[:1600], 'alineacion': formato['alineacion'],
                              'todo_en_negrita': all(r['negrita'] for r in partes), 'fragmentos': partes[:20]})
    return {'parrafos': parrafos, 'parrafos_truncados': truncado,
            'alcance': 'Texto, negrita y alineación en párrafos del cuerpo; no verifica diseño, tablas ni cuadros de texto'}
