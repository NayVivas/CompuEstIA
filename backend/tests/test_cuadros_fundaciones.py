from dataclasses import replace
import unittest

from computos.fundaciones.armaduras import (
    extraer_textos_armadura,
    interpretar_armaduras,
    separar_niveles_armadura,
)
from computos.fundaciones.cuadros import (
    CAMPO_ARMADURA,
    CAMPO_H,
    CAMPO_PEDESTAL,
    CAMPO_X,
    CAMPO_Y,
    extraer_dimensiones_cuadro,
    localizar_estructura_cuadro,
)
from computos.documentos.modelos import Caja, PalabraNormalizada
from computos.referencias import descubrir_catalogo_referencias


def palabra(
    texto: str,
    x: float,
    y: float,
    *,
    ancho: float | None = None,
    indice: int = 0,
) -> PalabraNormalizada:
    ancho = ancho if ancho is not None else max(len(texto) * 2.2, 4)
    caja_visual = Caja(x, y, x + ancho, y + 6)
    # Las coordenadas PDF se dejan deliberadamente en otro orden. Si el lector
    # usara estas cajas en vez de las visuales, las columnas quedarían invertidas.
    caja_pdf = Caja(900 - x - ancho, 500 - y - 6, 900 - x, 500 - y)
    return PalabraNormalizada(
        pagina=1,
        texto=texto,
        caja_pdf=caja_pdf,
        caja_visual=caja_visual,
        numero_bloque=0,
        numero_linea=indice,
        numero_palabra=0,
    )


def cuadro_con_alias_y_unidades() -> list[PalabraNormalizada]:
    return [
        palabra("CUADRO", 10, 4),
        palabra("DE", 28, 4),
        palabra("ZAPATAS", 36, 4),
        palabra("REF.", 10, 20),
        palabra("LARGO(m)", 50, 20),
        palabra("ANCHO", 90, 20),
        palabra("(m)", 108, 20),
        palabra("ESPESOR(cm)", 130, 20),
        palabra("ACERO", 190, 20),
        palabra("Z-01", 10, 42),
        palabra("1,40", 55, 42),
        palabra("1,60", 95, 42),
        palabra("45", 140, 42),
        palabra('1Ø1/2"c/d15cm', 182, 42, ancho=36),
        palabra("Z-02", 10, 66),
        palabra("2,00", 55, 66),
        palabra("2,20", 95, 66),
        palabra("50", 140, 66),
        palabra('1Ø5/8"c/d10cm', 182, 66, ancho=36),
    ]


class CuadrosFundacionesTests(unittest.TestCase):
    def test_reconoce_alias_y_convierte_unidades(self):
        palabras = cuadro_con_alias_y_unidades()
        catalogo = descubrir_catalogo_referencias(palabras)

        cuadro = localizar_estructura_cuadro(palabras, catalogo)
        dimensiones = extraer_dimensiones_cuadro(cuadro)

        self.assertEqual(cuadro.encabezados[CAMPO_X].texto_original, "LARGO(m)")
        self.assertEqual(cuadro.encabezados[CAMPO_Y].texto_original, "ANCHO (m)")
        self.assertEqual(cuadro.encabezados[CAMPO_H].texto_original, "ESPESOR(cm)")
        self.assertEqual(cuadro.encabezados[CAMPO_ARMADURA].texto_original, "ACERO")
        self.assertNotIn(CAMPO_PEDESTAL, cuadro.encabezados)
        self.assertEqual(dimensiones[0]["referencia"], "Z1")
        self.assertEqual(dimensiones[0]["x"], "1.40")
        self.assertEqual(dimensiones[0]["y"], "1.60")
        self.assertEqual(dimensiones[0]["h"], "0.45")
        self.assertEqual(dimensiones[0]["unidad_h"], "cm")

    def test_admite_l_b_altura_refuerzo_y_dado(self):
        palabras = [
            palabra("CIMENTACIONES", 10, 4),
            palabra("MARCA", 10, 20),
            palabra("L", 50, 20),
            palabra("B", 90, 20),
            palabra("ALTURA", 130, 20),
            palabra("REFUERZO", 175, 20),
            palabra("DADO", 225, 20),
            palabra("PF_01", 10, 42),
            palabra("140", 55, 42),
            palabra("160", 95, 42),
            palabra("45", 140, 42),
            palabra('1Ø1/2"c/d15cm', 177, 42, ancho=36),
            palabra("+10 cm", 225, 42, ancho=25),
            palabra("PF_02", 10, 66),
            palabra("200", 55, 66),
            palabra("220", 95, 66),
            palabra("50", 140, 66),
            palabra('1Ø5/8"c/d10cm', 177, 66, ancho=36),
            palabra("+10 cm", 225, 66, ancho=25),
        ]
        catalogo = descubrir_catalogo_referencias(palabras)

        cuadro = localizar_estructura_cuadro(palabras, catalogo)
        dimensiones = extraer_dimensiones_cuadro(
            cuadro,
            unidad_predeterminada="cm",
        )

        self.assertIn(CAMPO_PEDESTAL, cuadro.encabezados)
        self.assertEqual(dimensiones[0]["referencia"], "PF1")
        self.assertEqual(dimensiones[0]["x"], "1.4")
        self.assertEqual(dimensiones[0]["y"], "1.6")
        self.assertEqual(dimensiones[0]["h"], "0.45")
        self.assertIn("se asumió cm", " ".join(cuadro.advertencias))

    def test_admite_armadura_superior_e_inferior_en_columnas_separadas(self):
        palabras = [
            palabra("CUADRO", 10, 4),
            palabra("FUNDACIONES", 32, 4),
            palabra("CODIGO", 10, 20),
            palabra("X", 50, 20),
            palabra("Y", 80, 20),
            palabra("H", 110, 20),
            palabra("SUP", 145, 20),
            palabra("INF", 190, 20),
            palabra("ZA1", 10, 42),
            palabra("1.4", 50, 42),
            palabra("1.4", 80, 42),
            palabra("0.4", 110, 42),
            palabra('1Ø1/2"c/d20cm', 137, 42, ancho=38),
            palabra('1Ø1/2"c/d15cm', 182, 42, ancho=38),
            palabra("ZA2", 10, 66),
            palabra("1.8", 50, 66),
            palabra("1.8", 80, 66),
            palabra("0.5", 110, 66),
            palabra('1Ø5/8"c/d20cm', 137, 66, ancho=38),
            palabra('1Ø5/8"c/d15cm', 182, 66, ancho=38),
        ]
        catalogo = descubrir_catalogo_referencias(palabras)
        cuadro = localizar_estructura_cuadro(palabras, catalogo)
        dimensiones = extraer_dimensiones_cuadro(cuadro)

        textos = extraer_textos_armadura(cuadro, dimensiones)
        niveles = separar_niveles_armadura(textos)
        especificaciones = interpretar_armaduras(niveles)

        self.assertIn('c/d20cm', niveles[0]["superior"])
        self.assertIn('c/d15cm', niveles[0]["inferior"])
        self.assertEqual(len(especificaciones), 4)

    def test_rechaza_armadura_no_interpretable(self):
        with self.assertRaisesRegex(ValueError, "notación de armadura"):
            interpretar_armaduras(
                [
                    {
                        "referencia": "Z1",
                        "superior": "",
                        "inferior": "texto sin formato conocido",
                    }
                ]
            )

    def test_informa_campos_requeridos_faltantes(self):
        palabras = cuadro_con_alias_y_unidades()
        palabras = [
            palabra
            for palabra in palabras
            if palabra.texto != "ESPESOR(cm)"
            and palabra.caja_visual.x0 != 140
        ]
        catalogo = descubrir_catalogo_referencias(palabras)

        with self.assertRaisesRegex(ValueError, "Faltan: H"):
            localizar_estructura_cuadro(palabras, catalogo)

    def test_el_cuadro_informa_referencias_repetidas(self):
        palabras = [
            replace(elemento, texto="Z-01")
            if elemento.texto == "Z-02"
            else elemento
            for elemento in cuadro_con_alias_y_unidades()
        ]
        catalogo = descubrir_catalogo_referencias(palabras)

        cuadro = localizar_estructura_cuadro(palabras, catalogo)

        self.assertIn(
            "Z1 (2 apariciones)",
            " ".join(cuadro.advertencias),
        )


if __name__ == "__main__":
    unittest.main()
