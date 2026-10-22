"""El OCR debe devolver texto posicional, no solo una imagen clasificada."""

from pathlib import Path
import hashlib
import shutil
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from unittest.mock import patch
from computos.documentos.ocr import reconocer_pagina, diagnostico_ocr
from computos.ia.enrutador_documentos import enrutar_documentos


class SinModelo:
    def clasificar_texto(self, _texto):
        return {"objetivos": {}, "estado": "sin_modelo"}


@unittest.skipUnless(shutil.which("tesseract"), "Tesseract no está instalado")
class OCRLocalTests(unittest.TestCase):
    def test_capa_ocr_preserva_vectores_rotacion_y_texto_nativo(self):
        with TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            with pymupdf.open() as texto:
                p = texto.new_page(width=600, height=160)
                p.insert_text((20, 90), "COTA 1.25 FUNDACION", fontsize=32)
                p.set_rotation(90)
                imagen = p.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes('png')
            original = raiz / 'original.pdf'
            with pymupdf.open() as doc:
                p = doc.new_page(width=500, height=900)
                p.insert_text((60, 800), 'NATIVO-Z8', fontsize=18, rotate=90)
                p.insert_image(pymupdf.Rect(80, 100, 240, 700), stream=imagen)
                p.draw_rect(pymupdf.Rect(300, 100, 450, 300))
                p.set_rotation(270)
                doc.save(original)
            contenido = original.read_bytes()
            salida = raiz / 'ocr.pdf'
            repetida = raiz / 'ocr-otra.pdf'
            with pymupdf.open(original) as doc:
                original_nativo = [w[:4] for w in doc[0].get_text('words') if w[4] == 'NATIVO-Z8'][0]
                dibujos = doc[0].get_drawings()
                reconocer_pagina(doc[0], salida)
                reconocer_pagina(doc[0], repetida)
            self.assertEqual(original.read_bytes(), contenido)
            self.assertEqual(hashlib.sha256(salida.read_bytes()).hexdigest(), hashlib.sha256(repetida.read_bytes()).hexdigest())
            with pymupdf.open(salida) as doc:
                self.assertEqual(doc[0].rotation, 270)
                self.assertEqual(doc[0].get_drawings(), dibujos)
                nativo = [w for w in doc[0].get_text('words') if w[4] == 'NATIVO-Z8']
                self.assertEqual(len(nativo), 1)
                self.assertEqual(nativo[0][:4], original_nativo)
                self.assertIn('1.25', doc[0].get_text())

    def test_pagina_escaneada_se_vuelve_buscable_y_clasificable(self):
        with TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            origen_texto = raiz / "texto.pdf"
            with pymupdf.open() as documento:
                pagina = documento.new_page(width=900, height=500)
                pagina.insert_text(
                    (80, 170),
                    "PLANTA DE FUNDACIONES Z1",
                    fontsize=38,
                )
                documento.save(origen_texto)
            with pymupdf.open(origen_texto) as documento:
                imagen = documento[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")

            escaneado = raiz / "escaneado.pdf"
            with pymupdf.open() as documento:
                pagina = documento.new_page(width=900, height=500)
                pagina.insert_image(pagina.rect, stream=imagen)
                documento.save(escaneado)

            buscable = raiz / "ocr.pdf"
            with pymupdf.open(escaneado) as documento:
                resultado = reconocer_pagina(documento[0], buscable)
            self.assertIn("FUND", resultado.texto.upper())
            with pymupdf.open(buscable) as documento:
                self.assertGreater(len(documento[0].get_text("words")), 2)

            enrutamiento = enrutar_documentos(
                {"doc": escaneado}, clasificador=SinModelo()
            )
            ficha = enrutamiento.documentos[0]["paginas"][0]
            self.assertEqual(ficha["metodo_extraccion_texto"], "ocr_tesseract")
            self.assertTrue(ficha["requiere_revision"])
            self.assertIn("planta", ficha["roles_motor"])


class DiagnosticoOCRTests(unittest.TestCase):
    def test_solo_osd_no_es_un_idioma_utilizable_para_reconocimiento(self):
        with patch('computos.documentos.ocr.resolver_tesseract', return_value='tesseract'), \
             patch('computos.documentos.ocr.resolver_tessdata', return_value=Path('/datos')), \
             patch('computos.documentos.ocr._idiomas_disponibles', return_value={'osd'}):
            self.assertFalse(diagnostico_ocr()['listo'])

    def test_archivo_presente_pero_no_ejecutable_no_se_informa_listo(self):
        with patch('computos.documentos.ocr.resolver_tesseract', return_value='tesseract-invalido'), \
             patch('computos.documentos.ocr.subprocess.run', side_effect=OSError('no ejecutable')):
            self.assertFalse(diagnostico_ocr()['listo'])

    def test_sin_datos_de_idioma_no_se_informa_listo(self):
        with patch('computos.documentos.ocr.resolver_tesseract', return_value='tesseract'), \
             patch('computos.documentos.ocr.resolver_tessdata', return_value=None):
            self.assertFalse(diagnostico_ocr()['listo'])


if __name__ == "__main__":
    unittest.main()

