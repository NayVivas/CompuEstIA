"""Pruebas de la limpieza de texto de la variante `palabras`."""

import unittest

from computos.ia.limpieza_contenidos import ROTULO_BLOQUE, limpiar_texto


class LimpiezaContenidosTests(unittest.TestCase):
    def test_elimina_bloque_de_rotulos(self):
        texto = "\n".join(
            [
                "PROYECTO: EDIFICIO CENTRAL",
                "PROPIETARIO: INMOBILIARIA",
                "FECHA: 2026-10-27",
                "ESCALA 1:100",
                "LÁMINA 04",
                "PLANTA DE FUNDACIONES",
            ]
        )

        self.assertEqual(limpiar_texto(texto), "planta fundaciones")

    def test_conserva_palabras_semanticas_y_normaliza_tildes(self):
        texto = "VIGAS DE HORMIGÓN ARMADO\nCOLUMNAS Y PILARES"

        self.assertEqual(
            limpiar_texto(texto),
            "vigas hormigon armado\ncolumnas pilares",
        )

    def test_elimina_numeros_cotas_y_puntuacion(self):
        texto = "C-1 30x30 @ 0.20\nMURO DE HORMIGÓN"

        self.assertEqual(limpiar_texto(texto), "muro hormigon")

    def test_descarta_palabras_cortas_y_stopwords(self):
        texto = "DE LA VIGA EN EL EJE 1"

        self.assertEqual(limpiar_texto(texto), "viga eje")

    def test_texto_vacio_o_solo_rotulos(self):
        self.assertEqual(limpiar_texto(""), "")
        self.assertEqual(limpiar_texto("PROYECTO: X\nFECHA: 2026"), "")

    def test_regex_detecta_rotulos_sin_distinguir_mayusculas(self):
        self.assertIsNotNone(ROTULO_BLOQUE.match("  proyecto: X"))
        self.assertIsNotNone(ROTULO_BLOQUE.match("Esc. 1:50"))
        self.assertIsNone(ROTULO_BLOQUE.match("PLANTA DE FUNDACIONES"))

    def test_limpieza_es_idempotente(self):
        texto = "VIGAS DE HORMIGÓN\nC-1 30x30"
        una_vez = limpiar_texto(texto)

        self.assertEqual(limpiar_texto(una_vez), una_vez)


if __name__ == "__main__":
    unittest.main()
