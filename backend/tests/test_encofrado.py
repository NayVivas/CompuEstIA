from decimal import Decimal
import unittest

from computos.fundaciones.encofrado import (
    calcular_encofrado_zapatas,
)


class EncofradoTests(unittest.TestCase):
    def test_detalla_las_cuatro_caras_de_f1(self):
        dimensiones = [
            {
                "referencia": "F1",
                "x": Decimal("1.40"),
                "y": Decimal("1.40"),
                "h": Decimal("0.35"),
            }
        ]
        conteo = {"F1": 4}

        detalle, total = calcular_encofrado_zapatas(
            dimensiones,
            conteo,
        )

        f1 = detalle[0]

        self.assertEqual(
            f1["area_unitaria_m2"],
            Decimal("1.9600"),
        )
        self.assertEqual(
            f1["area_total_m2"],
            Decimal("7.8400"),
        )
        self.assertEqual(total, Decimal("7.8400"))

        self.assertEqual(len(f1["caras"]), 4)
        self.assertEqual(
            [cara["cara"] for cara in f1["caras"]],
            ["X1", "X2", "Y1", "Y2"],
        )

        for cara in f1["caras"]:
            self.assertEqual(
                cara["area_m2"],
                Decimal("0.4900"),
            )

        self.assertEqual(len(f1["elementos"]), 4)
        self.assertEqual(
            f1["elementos"][0]["identificador"],
            "F1-01",
        )
        self.assertEqual(
            f1["elementos"][3]["identificador"],
            "F1-04",
        )

        self.assertEqual(
            f1["comprobaciones"]["estado"],
            "verificado",
        )
        self.assertTrue(
            f1["comprobaciones"][
                "formula_coincide_con_caras"
            ]
        )
        self.assertTrue(
            f1["comprobaciones"][
                "elementos_coinciden_con_total"
            ]
        )

    def test_encofrado_desactivado_devuelve_cero(self):
        dimensiones = [
            {
                "referencia": "Z-01",
                "x": Decimal("2.00"),
                "y": Decimal("1.50"),
                "h": Decimal("0.40"),
            }
        ]
        conteo = {"Z-01": 2}

        detalle, total = calcular_encofrado_zapatas(
            dimensiones,
            conteo,
            usar_encofrado=False,
        )

        self.assertEqual(total, Decimal("0"))
        self.assertEqual(
            detalle[0]["area_unitaria_m2"],
            Decimal("0"),
        )
        self.assertEqual(
            detalle[0]["area_total_m2"],
            Decimal("0"),
        )
        self.assertEqual(
            detalle[0]["comprobaciones"]["estado"],
            "verificado",
        )


if __name__ == "__main__":
    unittest.main()