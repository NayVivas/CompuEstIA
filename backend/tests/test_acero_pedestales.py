import unittest

from computos.fundaciones.pedestales import (
    calcular_acero_pedestales,
)


def armadura(referencia, cantidad=4):
    return {
        "referencia": referencia,
        "estado": "CORRECTO",
        "grupos_longitudinales": [
            {
                "cantidad": cantidad,
                "diametro_pulgadas": "1/2",
            }
        ],
        "estribo": {
            "diametro_pulgadas": "3/8",
            "separacion_m": 0.20,
            "longitud_indicada_m": 1.20,
        },
    }


class AceroPedestalesTests(unittest.TestCase):
    def test_hereda_armadura_de_columna_y_multiplica_cantidad(self):
        resultado = calcular_acero_pedestales(
            [
                {
                    "referencia_columna": "C1",
                    "cantidad": 2,
                    "altura_real_m": 1.0,
                }
            ],
            [armadura("C1")],
        )

        fila = resultado["detalles"][0]
        self.assertEqual(
            fila["origen_armadura_pedestal"],
            "heredada_de_columna",
        )
        self.assertEqual(
            fila["estado_armadura_pedestal"],
            "computada_por_herencia_columna",
        )
        self.assertEqual(fila["cantidad_estribos_unitario"], 6)
        self.assertEqual(fila["cantidad_estribos"], 12)
        self.assertAlmostEqual(
            fila["peso_acero_unitario_kg"],
            8.016,
            places=3,
        )
        self.assertAlmostEqual(
            resultado["acero_total_kg"],
            16.032,
            places=3,
        )
        self.assertTrue(resultado["resultado_completo"])
        self.assertEqual(
            resultado["referencias_heredadas_de_columnas"],
            ["C1"],
        )

    def test_armadura_explicita_del_pedestal_tiene_prioridad(self):
        resultado = calcular_acero_pedestales(
            [
                {
                    "referencia_columna": "C2",
                    "cantidad": 1,
                    "altura_minima_m": 0.5,
                }
            ],
            [armadura("C2", cantidad=4)],
            [armadura("C2", cantidad=8)],
        )

        fila = resultado["detalles"][0]
        self.assertEqual(
            fila["origen_armadura_pedestal"],
            "especifica_pedestal",
        )
        self.assertEqual(
            fila["armadura_pedestal"][
                "grupos_longitudinales"
            ][0]["cantidad"],
            8,
        )
        self.assertTrue(fila["usa_altura_minima_para_acero"])
        self.assertEqual(
            resultado["referencias_con_armadura_explicita"],
            ["C2"],
        )

    def test_entrega_subtotal_y_solo_deja_pendiente_lo_invalido(self):
        resultado = calcular_acero_pedestales(
            [
                {
                    "referencia_columna": "C1",
                    "cantidad": 1,
                    "altura_minima_m": 1.0,
                },
                {
                    "referencia_columna": "C3",
                    "cantidad": 1,
                    "altura_minima_m": 1.0,
                },
            ],
            [armadura("C1")],
        )

        self.assertIsNotNone(resultado["acero_total_kg"])
        self.assertTrue(resultado["resultado_parcial"])
        self.assertFalse(resultado["resultado_completo"])
        self.assertEqual(
            resultado["referencias_computadas"],
            ["C1"],
        )
        self.assertEqual(
            resultado["referencias_pendientes"],
            ["C3"],
        )


if __name__ == "__main__":
    unittest.main()
