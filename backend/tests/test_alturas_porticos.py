"""Pruebas generales de alturas por tramo en pórticos ortogonales."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from computos.columnas.porticos import (
    asociar_secciones_porticos,
    extraer_alturas_porticos,
)


class AlturasPorticosTests(unittest.TestCase):
    def _pdf(self, carpeta, segunda_referencia="C1", segundo_eje_x=50):
        ruta = Path(carpeta) / "porticos.pdf"
        with pymupdf.open() as pdf:
            for indice, (portico, eje, referencia) in enumerate((
                ("A", "1", "C1"),
                ("1", "A", segunda_referencia),
            )):
                eje_x = segundo_eje_x if indice == 1 else 50
                pagina = pdf.new_page(width=300, height=200)
                pagina.insert_text((200, 55), "N1 (+5.20)", fontsize=8)
                pagina.insert_text((200, 105), "NPB (+1.20)", fontsize=8)
                pagina.insert_text((20, 80), "4,00", fontsize=8)
                pagina.insert_text((50, 80), referencia, fontsize=8)
                pagina.insert_text((eje_x, 122.5), eje, fontsize=8)
                pagina.insert_text(
                    (50, 135),
                    f"Portico {portico}",
                    fontsize=8,
                )
            pdf.save(ruta)
        return ruta

    def test_deduplica_vistas_ortogonales_por_eje_y_niveles(self):
        with TemporaryDirectory() as carpeta:
            resultado = extraer_alturas_porticos(
                self._pdf(carpeta),
                paginas_origen=[11, 12],
            )

        self.assertEqual(resultado["cantidad_observaciones"], 2)
        self.assertEqual(resultado["cantidad_tramos"], 1)
        self.assertEqual(resultado["cantidad_tramos_confirmables"], 1)
        tramo = resultado["tramos"][0]
        self.assertEqual(tramo["eje_global"], "A-1")
        self.assertEqual(tramo["nivel_inferior"], "NPB")
        self.assertEqual(tramo["nivel_superior"], "N1")
        self.assertEqual(tramo["altura_detectada_m"], 4.0)
        self.assertEqual(tramo["paginas"], [11, 12])

    def test_conserva_conflicto_de_referencia_sin_adivinar(self):
        with TemporaryDirectory() as carpeta:
            resultado = extraer_alturas_porticos(
                self._pdf(carpeta, segunda_referencia="C2")
            )

        self.assertEqual(resultado["cantidad_conflictos"], 1)
        tramo = resultado["tramos"][0]
        self.assertEqual(
            tramo["estado_extraccion"],
            "conflicto_entre_vistas",
        )
        self.assertEqual(tramo["referencias_candidatas"], ["C1", "C2"])
        self.assertIsNone(tramo["referencia"])

    def test_no_bloquea_una_diferencia_con_asociacion_geometrica_debil(self):
        with TemporaryDirectory() as carpeta:
            resultado = extraer_alturas_porticos(
                self._pdf(
                    carpeta,
                    segunda_referencia="C2",
                    segundo_eje_x=60,
                )
            )

        self.assertEqual(resultado["cantidad_conflictos"], 0)
        self.assertEqual(
            resultado["cantidad_discrepancias_no_confirmadas"],
            1,
        )
        tramo = resultado["tramos"][0]
        self.assertEqual(
            tramo["estado_extraccion"],
            "detectado_confirmable",
        )
        self.assertEqual(tramo["referencia"], "C1")
        self.assertEqual(tramo["conflictos"], [])
        self.assertEqual(
            tramo["discrepancias_no_confirmadas"],
            ["referencia"],
        )

    def test_asocia_solo_una_seccion_inequivoca(self):
        with TemporaryDirectory() as carpeta:
            analisis = extraer_alturas_porticos(self._pdf(carpeta))
        resultado = asociar_secciones_porticos(
            analisis,
            [
                {
                    "referencia": "C1",
                    "dimension_1_m": 0.40,
                    "dimension_2_m": 0.50,
                    "estado": "CORRECTO",
                    "origen": "columnas.pdf",
                    "pagina": 1,
                }
            ],
        )

        tramo = resultado["tramos"][0]
        self.assertEqual(tramo["estado_seccion"], "detectada")
        self.assertEqual((tramo["ancho_m"], tramo["largo_m"]), (0.4, 0.5))


if __name__ == "__main__":
    unittest.main()
