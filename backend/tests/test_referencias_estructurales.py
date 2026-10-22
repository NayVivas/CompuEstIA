import unittest

from computos.fundaciones import detectar_fundaciones
from computos.documentos.modelos import Caja, PalabraNormalizada
from computos.referencias import (
    descubrir_catalogo_referencias,
    detectar_referencias_del_catalogo,
    interpretar_referencia,
)


def palabra(
    texto: str,
    x: float,
    y: float,
    *,
    pagina: int = 1,
    indice: int = 0,
) -> PalabraNormalizada:
    caja = Caja(x, y, x + max(len(texto) * 4, 4), y + 6)
    return PalabraNormalizada(
        pagina=pagina,
        texto=texto,
        caja_pdf=caja,
        caja_visual=caja,
        numero_bloque=0,
        numero_linea=indice,
        numero_palabra=0,
    )


class ReferenciasEstructuralesTests(unittest.TestCase):
    def test_normaliza_distintas_nomenclaturas(self):
        casos = {
            "F1": "F1",
            "Z-01": "Z1",
            "ZA.002": "ZA2",
            "PF_03": "PF3",
            "P-1A": "P1A",
        }

        for original, esperada in casos.items():
            with self.subTest(original=original):
                resultado = interpretar_referencia(original)
                self.assertIsNotNone(resultado)
                self.assertEqual(resultado.canonica, esperada)

    def test_no_acepta_textos_ni_numeros_sueltos(self):
        for texto in ("FUNDACION", "12", "3.50", "VR-2/36"):
            with self.subTest(texto=texto):
                self.assertIsNone(interpretar_referencia(texto))

    def test_descubre_referencias_z_desde_el_cuadro(self):
        palabras = [
            palabra("CUADRO", 10, 5),
            palabra("DE", 42, 5),
            palabra("ZAPATAS", 55, 5),
            palabra("TIPO", 10, 20),
            palabra("X", 60, 20),
            palabra("Y", 90, 20),
            palabra("H", 120, 20),
            palabra("Z-01", 10, 35),
            palabra("Z-02", 10, 50),
            palabra("Z-03", 10, 65),
            palabra("C1", 180, 35),
            palabra("VR1", 180, 50),
        ]

        catalogo = descubrir_catalogo_referencias(palabras)

        self.assertEqual(catalogo.canonicas, ["Z1", "Z2", "Z3"])
        self.assertEqual(catalogo.confianza, "alta")

    def test_informa_referencias_duplicadas_sin_corregirlas(self):
        palabras = [
            palabra("CUADRO", 10, 5),
            palabra("DE", 42, 5),
            palabra("ZAPATAS", 55, 5),
            palabra("TIPO", 10, 20),
            palabra("X", 60, 20),
            palabra("Y", 90, 20),
            palabra("Z-01", 10, 35),
            palabra("Z-01", 10, 50),
        ]

        catalogo = descubrir_catalogo_referencias(palabras)

        self.assertEqual(catalogo.canonicas, ["Z1", "Z1"])
        self.assertIn(
            "Z1 (2 apariciones)",
            " ".join(catalogo.advertencias),
        )

    def test_detecta_solo_referencias_autorizadas_en_la_planta(self):
        palabras = [
            palabra("Z-01", 10, 10),
            palabra("C1", 30, 10),
            palabra("VR1", 50, 10),
            palabra("Z-02", 70, 10),
            palabra("Z-01", 90, 10),
            palabra("F1", 110, 10),
        ]

        resultado = detectar_referencias_del_catalogo(
            palabras,
            ["Z1", "Z2"],
        )

        self.assertEqual(
            [deteccion["referencia"] for deteccion in resultado],
            ["Z1", "Z2", "Z1"],
        )

    def test_reconstruye_referencia_dividida_por_el_pdf(self):
        palabras = [
            palabra("ZA-", 10, 10),
            palabra("03", 24, 10),
            palabra("C1", 50, 10),
        ]

        resultado = detectar_referencias_del_catalogo(palabras, ["ZA3"])

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["referencia"], "ZA3")
        self.assertEqual(resultado[0]["texto_original"], "ZA-03")

    def test_detector_compatible_tambien_exige_catalogo(self):
        palabras = [
            {
                "texto": "Z-01",
                "pagina": 1,
                "x0": 10,
                "y0": 20,
                "x1": 18,
                "y1": 26,
            },
            {
                "texto": "F1",
                "pagina": 1,
                "x0": 30,
                "y0": 20,
                "x1": 38,
                "y1": 26,
            },
        ]

        resultado = detectar_fundaciones(palabras, ["Z1"])

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["referencia"], "Z1")
        with self.assertRaisesRegex(ValueError, "catálogo"):
            detectar_fundaciones(palabras, [])


if __name__ == "__main__":
    unittest.main()
