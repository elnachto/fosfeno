import tempfile
from pathlib import Path
import unittest
from zipfile import ZipFile
from evidencia_documentos import resumen_docx


class DocumentoTests(unittest.TestCase):
    def test_declara_texto_recortado_aunque_solo_haya_un_parrafo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'largo.docx'
            with ZipFile(ruta, 'w') as z:
                z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                           '<w:p><w:r><w:t>' + 'x' * 501 + '</w:t></w:r></w:p></w:body></w:document>')
            dato = resumen_docx(ruta)
            self.assertTrue(dato['parrafos_truncados'])
            self.assertEqual(len(dato['parrafos'][0]['texto']), 500)

    def test_distingue_formato_real_del_estado_de_la_barra(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'prueba.docx'
            with ZipFile(ruta, 'w') as z:
                z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                           '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t>Título</w:t></w:r></w:p>'
                           '<w:p><w:r><w:t>Párrafo normal</w:t></w:r></w:p></w:body></w:document>')
            parrafos = resumen_docx(ruta)['parrafos']
            self.assertEqual(parrafos[0]['alineacion'], 'center')
            self.assertTrue(parrafos[0]['todo_en_negrita'])
            self.assertFalse(parrafos[1]['todo_en_negrita'])
            self.assertEqual(parrafos[1]['alineacion'], 'left')

    def test_resuelve_estilo_heredado_y_desactivacion_explicita(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / 'estilos.docx'
            ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
            with ZipFile(ruta, 'w') as z:
                z.writestr('word/styles.xml', '<w:styles ' + ns + '><w:style w:styleId="Base"><w:rPr><w:b/></w:rPr><w:pPr><w:jc w:val="center"/></w:pPr></w:style>'
                           '<w:style w:styleId="Titulo"><w:basedOn w:val="Base"/></w:style></w:styles>')
                z.writestr('word/document.xml', '<w:document ' + ns + '><w:body><w:p><w:pPr><w:pStyle w:val="Titulo"/></w:pPr>'
                           '<w:r><w:t>Hereda</w:t></w:r><w:r><w:rPr><w:b w:val="0"/></w:rPr><w:t> normal</w:t></w:r></w:p></w:body></w:document>')
            p = resumen_docx(ruta)['parrafos'][0]
            self.assertEqual(p['alineacion'], 'center')
            self.assertFalse(p['todo_en_negrita'])
            self.assertTrue(p['fragmentos'][0]['negrita'])


if __name__ == '__main__':
    unittest.main()
