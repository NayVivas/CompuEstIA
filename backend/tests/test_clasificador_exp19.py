"""Prueba de humo con los artefactos reales y sin usar internet."""

from pathlib import Path
import unittest

from computos.ia.clasificador_exp19 import ClasificadorExp19


class ClasificadorExp19Tests(unittest.TestCase):
    def test_clasifica_texto_con_modelos_reales(self):
        clasificador = ClasificadorExp19()
        resultado = clasificador.clasificar_texto(
            "PLANTA DE FUNDACIONES. COLUMNAS, VIGAS DE RIOSTRA, "
            "ARMADURAS Y CUADRO DE ZAPATAS F1 F2 F3."
        )

        self.assertEqual(resultado["estado"], "clasificado")
        self.assertEqual(resultado["modelo"], "EXP19")
        self.assertEqual(
            set(resultado["objetivos"]),
            {
                "disciplinas",
                "roles_documentales",
                "contenidos",
            },
        )
        for objetivo in resultado["objetivos"].values():
            self.assertIn("etiquetas", objetivo)
            self.assertIn("detalle", objetivo)


if __name__ == "__main__":
    unittest.main()

