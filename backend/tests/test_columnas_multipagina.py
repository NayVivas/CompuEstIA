import unittest

from computos.columnas.deteccion import extraer_secciones_columnas


def palabra(texto, pagina, x, y):
    return {
        "texto": texto, "pagina": pagina,
        "x0": x, "y0": y, "x1": x + 5, "y1": y + 3,
    }


class ColumnasMultipaginaTests(unittest.TestCase):
    def test_no_mezcla_cotas_de_paginas_distintas(self):
        palabras = [
            palabra("C1", 1, 10, 100),
            palabra("0.30", 1, 15, 50),
            palabra("0.40", 1, 15, 60),
            palabra("0.50", 2, 15, 50),
        ]
        resultado = extraer_secciones_columnas(palabras, "multipagina.pdf")
        self.assertEqual(resultado[0]["estado"], "CORRECTO")
        self.assertEqual(resultado[0]["pagina"], 1)
        self.assertEqual(resultado[0]["cantidad_cotas"], 2)

    def test_reasigna_solo_la_referencia_de_la_pagina_indicada(self):
        palabras = [
            palabra("C4", 1, 10, 100),
            palabra("0.30", 1, 15, 50),
            palabra("0.40", 1, 15, 60),
            palabra("C4", 2, 10, 100),
            palabra("0.45", 2, 15, 50),
            palabra("0.60", 2, 15, 60),
        ]

        resultado = extraer_secciones_columnas(
            palabras,
            "multipagina.pdf",
            correcciones={(1, "C4"): "C3"},
        )

        self.assertEqual(
            [(fila["pagina"], fila["referencia"]) for fila in resultado],
            [(1, "C3"), (2, "C4")],
        )


if __name__ == "__main__":
    unittest.main()
