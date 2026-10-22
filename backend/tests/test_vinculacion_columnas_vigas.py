import unittest

from computos.columnas.vinculacion_vigas import (
    vincular_columnas_pendientes_con_vigas,
)

from computos.columnas.vinculacion_vigas import (
    confirmar_vinculaciones_con_ejes,
    vincular_columnas_pendientes_con_vigas,
)


class VinculacionColumnasVigasTests(
    unittest.TestCase
):
    def test_vincula_c5_con_vr2(self):
        directas = [
            {
                "fundacion_id": "F10-01",
                "pagina": 1,
                "referencia_columna": "C3",
                "posicion_rotulo_columna_pdf": {
                    "x": 454.915,
                    "y": 177.726,
                },
            }
        ]

        pendientes = [
            {
                "fundacion_id": "F10-01",
                "pagina": 1,
                "referencia_columna": "C5",
                "posicion_rotulo_columna_pdf": {
                    "x": 477.355,
                    "y": 170.766,
                },
            }
        ]

        rotulos = [
            {
                "pagina": 1,
                "referencia": "VR2",
                "texto_original": (
                    "V.R. 2 (40 X 50)"
                ),
                "ancho_m": 0.40,
                "alto_m": 0.50,
                "centro_x": 456.36,
                "centro_y": 167.16,
            },
            {
                "pagina": 1,
                "referencia": "VR1",
                "texto_original": (
                    "V.R. 1 (40 X 50)"
                ),
                "ancho_m": 0.40,
                "alto_m": 0.50,
                "centro_x": 471.70,
                "centro_y": 189.42,
            },
        ]

        (
            vinculadas,
            sin_vincular,
            diagnostico,
        ) = vincular_columnas_pendientes_con_vigas(
            columnas_pendientes=pendientes,
            columnas_directas=directas,
            rotulos_vigas=rotulos,
        )

        self.assertEqual(
            len(vinculadas),
            1,
        )

        self.assertEqual(
            len(sin_vincular),
            0,
        )

        self.assertEqual(
            vinculadas[0]["referencia_viga"],
            "VR2",
        )

        self.assertEqual(
            vinculadas[0][
                "referencia_columna_directa"
            ],
            "C3",
        )

        self.assertEqual(
            vinculadas[0][
                "referencia_columna_vinculada"
            ],
            "C5",
        )

        self.assertEqual(
            diagnostico[
                "columnas_vinculadas_por_viga"
            ],
            1,
        )

    def test_confirma_vr2_con_eje_vectorial(self):
        vinculaciones = [
            {
                "fundacion_id": "F10-01",
                "pagina": 1,
                "referencia_viga": "VR2",
                "referencia_columna_directa": "C3",
                "referencia_columna_vinculada": "C5",
                "posicion_rotulo_columna_directa_pdf": {
                    "x": 454.915,
                    "y": 177.726,
                },
                "posicion_rotulo_columna_vinculada_pdf": {
                    "x": 477.355,
                    "y": 170.766,
                },
                "posicion_rotulo_viga_pdf": {
                    "x": 456.36,
                    "y": 167.16,
                },
            }
        ]

        ejes = [
            {
                "id_eje": 1,
                "pagina": 1,
                "x_inicial": 452.88,
                "y_inicial": 171.36,
                "x_final": 468.24,
                "y_final": 171.36,
                "longitud_pdf": 15.36,
                "angulo_pdf_grados": 0.0,
            },
            {
                "id_eje": 2,
                "pagina": 1,
                "x_inicial": 380.64,
                "y_inicial": 174.48,
                "x_final": 380.64,
                "y_final": 231.0,
                "longitud_pdf": 56.52,
                "angulo_pdf_grados": 90.0,
            },
        ]

        (
            confirmadas,
            sin_confirmar,
            diagnostico,
        ) = confirmar_vinculaciones_con_ejes(
            vinculaciones=vinculaciones,
            ejes_candidatos=ejes,
        )

        self.assertEqual(
            len(confirmadas),
            1,
        )

        self.assertEqual(
            len(sin_confirmar),
            0,
        )

        self.assertEqual(
            confirmadas[0]["id_eje_viga"],
            1,
        )

        self.assertEqual(
            confirmadas[0]["estado"],
            "confirmada_por_eje_vectorial",
        )

        self.assertFalse(
            confirmadas[0][
                "requiere_revision_geometrica"
            ]
        )

        self.assertEqual(
            diagnostico[
                "vinculaciones_confirmadas"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()