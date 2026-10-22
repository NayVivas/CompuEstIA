import unittest

from computos.flujos.principal import (
    construir_alertas_analisis,
    separar_advertencias_referencias_resueltas,
)


class ClasesAlertasTests(unittest.TestCase):
    def test_no_reabre_duplicidad_corregida_como_advertencia(self):
        repetida = (
            "El cuadro contiene referencias repetidas: F12 "
            "(2 apariciones). Revise las correcciones del proyecto."
        )
        otra = "El cuadro no contiene una columna de pedestal."

        vigentes, resueltas = (
            separar_advertencias_referencias_resueltas(
                [repetida, otra],
                [{"referencia_original": "F12"}],
            )
        )

        self.assertEqual(vigentes, [otra])
        self.assertEqual(resueltas, [repetida])

    def test_separa_inconsistencias_de_datos_requeridos(self):
        resultado = {
            "vigas_riostra_computo_detalle": [
                {
                    "tramo_id": "VR1-01",
                    "referencia": "VR1",
                    "estado": "computado",
                    "estado_acero": "seccion_no_coincide_con_detalle",
                    "ancho_m": 0.30,
                    "alto_m": 0.40,
                    "armadura_viga": {
                        "ancho_m": 0.30,
                        "alto_m": 0.50,
                    },
                }
            ],
            "relaciones_columnas_fundaciones": [],
            "columnas_fundaciones": [
                {"referencia_columna": "C1"}
            ],
            "columnas_vinculadas_por_viga": [],
            "validacion_columnas": {
                "altura_real_disponible": False,
            },
            "acero_columnas_kg": None,
            "armaduras_columnas": [
                {"referencia": "C1", "estado": "CORRECTO"}
            ],
        }

        sistema = construir_alertas_analisis(resultado)
        clases = {
            alerta["categoria"]: alerta["clase_alerta"]
            for alerta in sistema["alertas"]
        }

        self.assertEqual(
            clases["inconsistencia_seccion"],
            "inconsistencia",
        )
        self.assertEqual(
            clases["alturas_reales_no_disponibles"],
            "dato_requerido",
        )
        self.assertEqual(
            clases["armadura_no_disponible"],
            "dato_requerido",
        )
        self.assertEqual(
            sistema["resumen"]["por_clase"],
            {"dato_requerido": 2, "inconsistencia": 1},
        )


if __name__ == "__main__":
    unittest.main()
