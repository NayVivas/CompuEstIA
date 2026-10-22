import unittest

from computos.columnas.armaduras import (
    consolidar_armaduras_columnas,
    extraer_armaduras_columnas,
)


def palabra(texto, x0, y0, x1=None, y1=None):
    return {
        "texto": texto,
        "pagina": 1,
        "x0": float(x0),
        "y0": float(y0),
        "x1": float(x1 if x1 is not None else x0 + 3),
        "y1": float(y1 if y1 is not None else y0 + 2),
    }


class ArmadurasColumnasTests(unittest.TestCase):
    def test_extrae_detalle_vertical_de_pagina_rotada(self):
        palabras = [
            palabra("DETALLE", 10, 10),
            palabra("COLUMNA", 10, 15),
            palabra("4", 10, 20),
            palabra("(C4)", 10, 25),
            palabra("EST.", 18, 0),
            palabra("Ø", 18, 5),
            palabra('3/8"', 18, 8),
            palabra("c/d", 18, 13),
            palabra("12", 18, 17),
            palabra("cms.", 18, 21),
            palabra("L", 18, 26),
            palabra("=", 18, 29),
            palabra("2.20", 18, 32),
            palabra("m.", 18, 38),
            palabra("=", 55, 20),
            palabra("10", 55, 23),
            palabra("Ø", 55, 27),
            palabra('1"', 55, 30),
            palabra("=", 59, 20),
            palabra("6", 59, 23),
            palabra("Ø", 59, 27),
            palabra('3/4"', 59, 30),
        ]

        resultado = extraer_armaduras_columnas(
            palabras,
            "Columnas.pdf",
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["referencia"], "C4")
        self.assertEqual(resultado[0]["estado"], "CORRECTO")
        self.assertEqual(
            resultado[0]["cantidad_barras_longitudinales"],
            16,
        )
        self.assertEqual(
            {
                grupo["diametro_pulgadas"]
                for grupo in resultado[0]["grupos_longitudinales"]
            },
            {"1", "3/4"},
        )
        self.assertEqual(
            resultado[0]["estribo"]["diametro_pulgadas"],
            "3/8",
        )
        self.assertAlmostEqual(
            resultado[0]["estribo"]["separacion_m"],
            0.12,
        )
        self.assertAlmostEqual(
            resultado[0]["estribo"]["longitud_indicada_m"],
            2.20,
        )
        self.assertFalse(
            resultado[0]["uso_en_pedestal_confirmado"]
        )

    def test_extrae_detalle_horizontal(self):
        palabras = [
            palabra("DETALLE", 0, 20, 8, 23),
            palabra("COLUMNA", 10, 20, 20, 23),
            palabra("8", 22, 20, 24, 23),
            palabra("(C8)", 26, 20, 32, 23),
            palabra("=", 30, 45, 32, 48),
            palabra("10", 34, 45, 38, 48),
            palabra("Ø", 40, 45, 42, 48),
            palabra('3/4"', 44, 45, 50, 48),
            palabra("EST.", 5, 5, 11, 8),
            palabra("Ø", 13, 5, 15, 8),
            palabra('3/8"', 17, 5, 23, 8),
            palabra("c/d", 25, 5, 30, 8),
            palabra("10", 32, 5, 36, 8),
            palabra("cm", 38, 5, 42, 8),
        ]

        resultado = extraer_armaduras_columnas(
            palabras,
            "Columnas.pdf",
        )

        self.assertEqual(resultado[0]["estado"], "CORRECTO")
        self.assertEqual(
            resultado[0]["cantidad_barras_longitudinales"],
            10,
        )
        self.assertEqual(
            resultado[0]["estribo"]["separacion_m"],
            0.10,
        )

    def test_no_confunde_barras_distribuidas_con_longitudinales(self):
        palabras = [
            palabra("DETALLE", 10, 10),
            palabra("COLUMNA", 10, 15),
            palabra("1", 10, 20),
            palabra("(C1)", 10, 25),
            palabra("1", 50, 20),
            palabra("Ø", 50, 23),
            palabra('1/2"', 50, 27),
            palabra("c/d", 50, 32),
            palabra("15", 50, 36),
            palabra("cm", 50, 40),
        ]

        resultado = extraer_armaduras_columnas(
            palabras,
            "Fundaciones_2.pdf",
        )

        self.assertEqual(resultado[0]["estado"], "REVISAR")
        self.assertEqual(
            resultado[0]["cantidad_barras_longitudinales"],
            0,
        )

    def test_aplica_correccion_sin_confirmar_uso_en_pedestal(self):
        palabras = [
            palabra("DETALLE", 10, 10),
            palabra("COLUMNA", 10, 15),
            palabra("4", 10, 20),
            palabra("(C4)", 10, 25),
            palabra("=", 50, 20),
            palabra("8", 50, 23),
            palabra("Ø", 50, 27),
            palabra('1"', 50, 30),
            palabra("EST.", 18, 0),
            palabra("Ø", 18, 5),
            palabra('3/8"', 18, 8),
            palabra("c/d", 18, 13),
            palabra("10", 18, 17),
            palabra("cm", 18, 21),
        ]

        resultado = extraer_armaduras_columnas(
            palabras,
            "Fundaciones_2.pdf",
            correcciones={"C4": "C3"},
        )

        self.assertEqual(resultado[0]["referencia_original"], "C4")
        self.assertEqual(resultado[0]["referencia"], "C3")
        self.assertTrue(resultado[0]["fue_corregida"])
        self.assertEqual(
            resultado[0]["estado_uso_pedestal"],
            "PENDIENTE_CONFIRMACION_PROFESIONAL",
        )

    def test_consolidacion_informa_conflicto_entre_planos(self):
        base = {
            "referencia": "C4",
            "estado": "CORRECTO",
            "grupos_longitudinales": [
                {
                    "cantidad": 8,
                    "diametro_pulgadas": "1",
                }
            ],
            "estribo": {
                "diametro_pulgadas": "3/8",
                "separacion_m": 0.10,
                "longitud_indicada_m": 2.0,
            },
            "advertencias": [],
        }
        columnas = {
            **base,
            "origen": "Columnas.pdf",
        }
        detalles = {
            **base,
            "origen": "Fundaciones_2.pdf",
            "grupos_longitudinales": [
                {
                    "cantidad": 10,
                    "diametro_pulgadas": "1",
                }
            ],
        }

        resultado = consolidar_armaduras_columnas(
            [columnas],
            [detalles],
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["estado"], "REVISAR")
        self.assertTrue(
            resultado[0]["conflicto_entre_fuentes"]
        )
        self.assertEqual(
            resultado[0]["fuentes_detectadas"],
            ["Columnas.pdf", "Fundaciones_2.pdf"],
        )

        columnas["pagina"] = 1
        detalles["pagina"] = 1
        seleccion = consolidar_armaduras_columnas(
            [columnas], [detalles],
            selecciones={("armadura", "C4"): {
                "origen": "Fundaciones_2.pdf", "pagina": 1,
                "revisor": "Ingeniera", "motivo": "Corresponde al nivel revisado.",
            }},
        )[0]
        self.assertFalse(seleccion["conflicto_entre_fuentes"])
        self.assertEqual(seleccion["estado"], "CORRECTO")
        self.assertEqual(seleccion["origen"], "Fundaciones_2.pdf")


if __name__ == "__main__":
    unittest.main()
