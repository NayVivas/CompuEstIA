"""Pruebas de geometría y asociación espacial entre referencias y cotas."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from computos.documentos.asociacion_espacial import (
    CajaTexto,
    Contorno,
    TipoToken,
    asociar_cajas,
    asociar_pdf,
    clasificar_token,
    distancia_entre_cajas,
    extraer_contornos,
    fusionar_tokens_dimension,
)
from computos.documentos.modelos import Caja


def texto(
    contenido: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    pagina: int = 1,
    bloque: int = 0,
    linea: int = 0,
    palabra: int = 0,
) -> CajaTexto:
    return CajaTexto(
        pagina=pagina,
        texto=contenido,
        caja=Caja(x0, y0, x1, y1),
        bloque=bloque,
        linea=linea,
        palabra=palabra,
        tipo=clasificar_token(contenido),
    )


class GeometriaAsociacionTests(unittest.TestCase):
    def test_distancia_euclidiana_borde_a_borde(self):
        self.assertEqual(
            distancia_entre_cajas(Caja(0, 0, 10, 10), Caja(20, 0, 30, 10)),
            10.0,
        )
        self.assertEqual(
            distancia_entre_cajas(Caja(0, 0, 10, 10), Caja(5, 5, 15, 15)),
            0.0,
        )
        self.assertAlmostEqual(
            distancia_entre_cajas(Caja(0, 0, 10, 10), Caja(30, 40, 40, 50)),
            36.0555,
            places=4,
        )

    def test_clasifica_tokens_por_forma_y_no_por_proyecto(self):
        self.assertEqual(clasificar_token("C-1"), TipoToken.REFERENCIA)
        self.assertEqual(clasificar_token("Z-01"), TipoToken.REFERENCIA)
        self.assertEqual(clasificar_token("PILOTE-1"), TipoToken.REFERENCIA)
        self.assertEqual(clasificar_token("C/1"), TipoToken.REFERENCIA)
        self.assertEqual(clasificar_token("30x30"), TipoToken.DIMENSION)
        self.assertEqual(clasificar_token("0.30 x 0.30"), TipoToken.DIMENSION)
        self.assertEqual(clasificar_token("0.30 m"), TipoToken.DIMENSION_LINEAL)
        self.assertEqual(clasificar_token("Ø 1/2 @ 0.20"), TipoToken.ARMADURA)
        self.assertEqual(clasificar_token("NPT +3.50"), TipoToken.ELEVACION)
        self.assertEqual(clasificar_token("30"), TipoToken.NUMERO)
        self.assertEqual(clasificar_token("PLANTA"), TipoToken.ROTULO)

    def test_fusiona_dimension_partida_por_cad(self):
        cajas = [
            texto("C-1", 80, 100, 95, 110),
            texto("30", 100, 100, 110, 110),
            texto("x", 112, 100, 116, 110),
            texto("30", 118, 100, 128, 110),
        ]

        fusionadas = fusionar_tokens_dimension(cajas)

        self.assertEqual(len(fusionadas), 2)
        referencia = next(item for item in fusionadas if item.texto == "C-1")
        dimension = next(item for item in fusionadas if item.texto == "30 x 30")
        self.assertEqual(referencia.tipo, TipoToken.REFERENCIA)
        self.assertEqual(dimension.tipo, TipoToken.DIMENSION)
        self.assertEqual(
            (dimension.caja.x0, dimension.caja.y0, dimension.caja.x1, dimension.caja.y1),
            (100.0, 100.0, 128.0, 110.0),
        )

    def test_no_fusiona_referencia_con_dimension(self):
        cajas = [
            texto("C-1", 100, 100, 120, 110),
            texto("30x30", 125, 100, 155, 110),
        ]

        fusionadas = fusionar_tokens_dimension(cajas)

        self.assertEqual([item.texto for item in fusionadas], ["C-1", "30x30"])
        self.assertEqual(fusionadas[0].tipo, TipoToken.REFERENCIA)
        self.assertEqual(fusionadas[1].tipo, TipoToken.DIMENSION)


class AsociacionEspacialTests(unittest.TestCase):
    def test_asocia_referencia_con_dimension_cercana(self):
        cajas = [
            texto("C-1", 100, 100, 120, 110),
            texto("30x30", 130, 100, 160, 110, linea=1),
            texto("C-2", 300, 300, 320, 310, bloque=1),
        ]

        resultado = asociar_cajas(cajas, ancho_pagina=600, alto_pagina=400)

        self.assertEqual(len(resultado.asociaciones), 1)
        asociacion = resultado.asociaciones[0]
        self.assertEqual(asociacion.referencia, "C-1")
        self.assertEqual(asociacion.dimension, "30x30")
        self.assertEqual(asociacion.distancia_px, 10.0)
        self.assertEqual(asociacion.confianza, "alta")
        self.assertFalse(asociacion.requiere_revision)
        self.assertEqual(resultado.no_asociados, ())

    def test_no_inventa_asociacion_cuando_hay_empate(self):
        cajas = [
            texto("C-1", 80, 100, 100, 110),
            texto("C-2", 140, 100, 160, 110),
            texto("30x30", 110, 100, 130, 110),
        ]

        resultado = asociar_cajas(cajas, ancho_pagina=600, alto_pagina=400)

        self.assertEqual(resultado.asociaciones, ())
        self.assertEqual(len(resultado.no_asociados), 1)
        no_asociado = resultado.no_asociados[0]
        self.assertEqual(no_asociado.motivo, "asociacion_ambigua")
        self.assertEqual(no_asociado.margen, 0.0)

    def test_asocia_por_contorno_si_hay_una_sola_referencia(self):
        cajas = [
            texto("C-1", 110, 110, 130, 120),
            texto("30x30", 235, 190, 265, 200),
        ]
        contornos = [Contorno(1, 0, Caja(100, 100, 230, 210))]

        resultado = asociar_cajas(
            cajas,
            contornos=contornos,
            ancho_pagina=600,
            alto_pagina=400,
        )

        self.assertEqual(len(resultado.asociaciones), 1)
        asociacion = resultado.asociaciones[0]
        self.assertEqual(asociacion.referencia, "C-1")
        self.assertEqual(asociacion.confianza, "media")
        self.assertTrue(asociacion.requiere_revision)
        self.assertTrue(asociacion.evidencia["asociacion_por_contorno"])
        self.assertEqual(asociacion.contorno_id, 0)

    def test_no_asocia_por_contorno_con_dos_referencias(self):
        cajas = [
            texto("C-1", 110, 110, 130, 120),
            texto("C-2", 110, 130, 130, 140),
            texto("30x30", 290, 200, 320, 210),
        ]
        contornos = [Contorno(1, 0, Caja(100, 100, 300, 300))]

        resultado = asociar_cajas(
            cajas,
            contornos=contornos,
            ancho_pagina=600,
            alto_pagina=400,
        )

        self.assertEqual(resultado.asociaciones, ())
        self.assertEqual(len(resultado.no_asociados), 1)
        self.assertEqual(
            resultado.no_asociados[0].motivo,
            "sin_referencia_en_radio",
        )

    def test_prefiere_el_contorno_que_contiene_ambos_centros(self):
        cajas = [
            texto("C-1", 100, 100, 120, 110),
            texto("30x30", 130, 100, 160, 110, linea=1),
        ]
        contornos = [
            Contorno(1, 0, Caja(90, 90, 125, 115)),
            Contorno(1, 1, Caja(50, 50, 300, 200)),
        ]

        resultado = asociar_cajas(
            cajas,
            contornos=contornos,
            ancho_pagina=600,
            alto_pagina=400,
        )

        asociacion = resultado.asociaciones[0]
        self.assertEqual(asociacion.evidencia["contencion"], 1.0)
        self.assertEqual(asociacion.contorno_id, 1)

    def test_resultado_es_determinista(self):
        cajas = [
            texto("C-1", 100, 100, 120, 110),
            texto("30x30", 130, 100, 160, 110, linea=1),
            texto("C-2", 300, 300, 320, 310, bloque=1),
        ]

        primero = asociar_cajas(cajas, ancho_pagina=600, alto_pagina=400)
        segundo = asociar_cajas(cajas, ancho_pagina=600, alto_pagina=400)

        self.assertEqual(primero, segundo)


class AsociacionPdfTests(unittest.TestCase):
    def test_asociar_pdf_extrae_texto_y_contornos(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ruta = Path(temporal.name) / "plano-sin-nombre-especial.pdf"

        with pymupdf.open() as documento:
            pagina = documento.new_page(width=600, height=400)
            pagina.insert_text((100, 100), "C-1", fontsize=10)
            pagina.insert_text((150, 100), "30x30", fontsize=10)
            pagina.draw_rect(pymupdf.Rect(90, 80, 230, 120))
            documento.save(ruta)

        resultados = asociar_pdf(ruta)

        self.assertEqual(len(resultados), 1)
        resultado = resultados[0]
        self.assertEqual(resultado.pagina, 1)
        self.assertEqual(len(resultado.contornos), 1)
        self.assertEqual(len(resultado.asociaciones), 1)
        self.assertEqual(resultado.asociaciones[0].referencia, "C-1")
        self.assertEqual(resultado.asociaciones[0].dimension, "30x30")

    def test_contornos_ignoran_lineas_abiertas(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ruta = Path(temporal.name) / "trazos.pdf"

        with pymupdf.open() as documento:
            pagina = documento.new_page(width=400, height=300)
            pagina.draw_rect(pymupdf.Rect(20, 20, 120, 80))
            pagina.draw_line(pymupdf.Point(150, 20), pymupdf.Point(250, 80))
            pagina.draw_circle(pymupdf.Point(320, 50), 30)
            documento.save(ruta)

        with pymupdf.open(ruta) as documento:
            contornos = extraer_contornos(documento[0])

        self.assertEqual(len(contornos), 2)
        self.assertEqual(
            [contorno.caja for contorno in contornos],
            [Caja(20, 20, 120, 80), Caja(290, 20, 350, 80)],
        )

    def test_pagina_rotada_usa_coordenadas_visuales(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ruta = Path(temporal.name) / "plano-rotado.pdf"

        with pymupdf.open() as documento:
            pagina = documento.new_page(width=600, height=400)
            pagina.insert_text((100, 100), "C-1", fontsize=10)
            pagina.insert_text((150, 100), "30x30", fontsize=10)
            pagina.draw_rect(pymupdf.Rect(90, 80, 230, 120))
            pagina.set_rotation(90)
            documento.save(ruta)

        resultado = asociar_pdf(ruta)[0]

        self.assertEqual(resultado.ancho_pagina, 400.0)
        self.assertEqual(resultado.alto_pagina, 600.0)
        referencia = next(
            caja for caja in resultado.cajas if caja.texto == "C-1"
        )
        self.assertAlmostEqual(referencia.caja.x0, 297.01, places=2)
        self.assertAlmostEqual(referencia.caja.y0, 100.0, places=2)
        self.assertEqual(len(resultado.asociaciones), 1)
        self.assertEqual(resultado.asociaciones[0].referencia, "C-1")
        for caja in resultado.cajas:
            self.assertGreaterEqual(caja.caja.x0, 0.0)
            self.assertLessEqual(caja.caja.x1, resultado.ancho_pagina)
            self.assertGreaterEqual(caja.caja.y0, 0.0)
            self.assertLessEqual(caja.caja.y1, resultado.alto_pagina)


if __name__ == "__main__":
    unittest.main()
