from pathlib import Path
import tempfile
import unittest

import pymupdf

from computos.documentos.analisis import (
    analizar_documento_pdf,
    detectar_roles_pagina,
    extraer_palabras_normalizadas,
    resolver_rutas_pdf,
)
from computos.documentos.modelos import (
    OrientacionPagina,
    RolPagina,
    TipoContenidoPagina,
)


class AnalisisDocumentosTests(unittest.TestCase):
    def crear_pdf_vectorial(self, ruta: Path, rotacion: int = 0) -> None:
        documento = pymupdf.open()
        pagina = documento.new_page(width=200, height=100)
        pagina.insert_text((20, 30), "PLANTA DE FUNDACIONES F1 F2")
        pagina.draw_line((10, 60), (190, 60), width=0.8)
        pagina.set_rotation(rotacion)
        documento.save(ruta)
        documento.close()

    def crear_pdf_escaneado(self, ruta: Path) -> None:
        with tempfile.TemporaryDirectory() as temporal:
            temporal = Path(temporal)
            original = temporal / "original.pdf"
            imagen = temporal / "pagina.png"

            documento = pymupdf.open()
            pagina = documento.new_page(width=200, height=100)
            pagina.insert_text((20, 30), "PLANO ESCANEADO")
            documento.save(original)
            documento.close()

            with pymupdf.open(original) as fuente:
                pixmap = fuente[0].get_pixmap()
                pixmap.save(imagen)

            escaneado = pymupdf.open()
            pagina_escaneada = escaneado.new_page(width=200, height=100)
            pagina_escaneada.insert_image(pagina_escaneada.rect, filename=imagen)
            escaneado.save(ruta)
            escaneado.close()

    def test_detecta_pdf_vectorial(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "planta.pdf"
            self.crear_pdf_vectorial(ruta)

            resultado = analizar_documento_pdf(ruta)

            self.assertEqual(resultado.tipo_contenido, TipoContenidoPagina.VECTORIAL)
            self.assertEqual(resultado.paginas[0].orientacion, OrientacionPagina.HORIZONTAL)
            self.assertIn(RolPagina.PLANTA, resultado.paginas[0].roles_candidatos)
            self.assertFalse(resultado.requiere_modo_asistido)

    def test_documento_vectorial_desconocido_no_exige_modo_asistido(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "vectorial_sin_rol.pdf"
            documento = pymupdf.open()
            pagina = documento.new_page(width=200, height=100)
            pagina.insert_text((20, 30), "LAMINA TECNICA 01")
            pagina.draw_line((10, 60), (190, 60), width=0.8)
            documento.save(ruta)
            documento.close()

            resultado = analizar_documento_pdf(ruta)

            self.assertEqual(
                resultado.paginas[0].roles_candidatos,
                [RolPagina.DESCONOCIDO],
            )
            self.assertTrue(resultado.paginas[0].requiere_revision)
            self.assertFalse(resultado.requiere_modo_asistido)

    def test_detecta_pdf_escaneado(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "escaneado.pdf"
            self.crear_pdf_escaneado(ruta)

            resultado = analizar_documento_pdf(ruta)

            self.assertEqual(resultado.tipo_contenido, TipoContenidoPagina.ESCANEADA)
            self.assertTrue(resultado.requiere_modo_asistido)

    def test_normaliza_coordenadas_de_pagina_rotada(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "rotado.pdf"
            self.crear_pdf_vectorial(ruta, rotacion=90)

            resultado = analizar_documento_pdf(ruta)
            palabras = extraer_palabras_normalizadas(ruta)

            self.assertEqual(resultado.paginas[0].rotacion_grados, 90)
            self.assertEqual(resultado.paginas[0].orientacion, OrientacionPagina.VERTICAL)
            self.assertTrue(palabras)
            for palabra in palabras:
                self.assertGreaterEqual(palabra.caja_visual.x0, 0)
                self.assertGreaterEqual(palabra.caja_visual.y0, 0)
                self.assertLessEqual(
                    palabra.caja_visual.x1,
                    resultado.paginas[0].ancho_visual_pt,
                )
                self.assertLessEqual(
                    palabra.caja_visual.y1,
                    resultado.paginas[0].alto_visual_pt,
                )

    def test_roles_pueden_ser_multiples(self):
        roles, evidencias = detectar_roles_pagina(
            "Planta de fundaciones - cuadro de fundaciones y detalles"
        )

        self.assertIn(RolPagina.PLANTA, roles)
        self.assertIn(RolPagina.CUADRO, roles)
        self.assertIn(RolPagina.DETALLE, roles)
        self.assertIn("planta", evidencias)

    def test_detecta_porticos_como_rol_documental(self):
        roles, evidencias = detectar_roles_pagina(
            "ELEVACION DE PORTICO A - COLUMNAS C1 C2"
        )

        self.assertIn(RolPagina.PORTICO, roles)
        self.assertIn("portico", evidencias)

    def test_detecta_titulos_exportados_con_letras_separadas(self):
        roles, evidencias = detectar_roles_pagina(
            "C U A D R O     D E     F U N D A C I O N E S"
        )

        self.assertIn(RolPagina.CUADRO, roles)
        self.assertIn("CUADRO", evidencias["cuadro"])

    def test_resuelve_carpetas_y_elimina_duplicados(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            ruta = carpeta / "PLANO.PDF"
            self.crear_pdf_vectorial(ruta)

            encontrados = resolver_rutas_pdf([carpeta, ruta])

            self.assertEqual(encontrados, [ruta.resolve()])


if __name__ == "__main__":
    unittest.main()
