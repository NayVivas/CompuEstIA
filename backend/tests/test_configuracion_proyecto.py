from copy import deepcopy
import unittest

from computos.configuracion.proyecto import interpretar_configuracion_proyecto
from computos.fundaciones import aplicar_correcciones, referencias_duplicadas


class ConfiguracionProyectoTests(unittest.TestCase):
    def test_carga_correccion_auditable_y_normaliza_referencias(self):
        configuracion = interpretar_configuracion_proyecto(
            {
                "nombre": "Plano de prueba",
                "archivos_esperados": {
                    "planta": "planta.pdf",
                    "detalles": "detalles.pdf",
                },
                "correcciones_referencias_cuadro": [
                    {
                        "referencia_original": "Z-01",
                        "aparicion": 2,
                        "referencia_correcta": "Z-02",
                        "motivo": "Rótulo repetido en el documento.",
                    }
                ],
            }
        )

        filas = [
            {"numero_fila": 1, "referencia": "Z1"},
            {"numero_fila": 2, "referencia": "Z1"},
        ]
        corregidas = aplicar_correcciones(
            filas,
            configuracion.correcciones_referencias_cuadro,
            configuracion.motivos_referencias_cuadro,
        )

        self.assertEqual(
            [fila["referencia"] for fila in corregidas],
            ["Z1", "Z2"],
        )
        self.assertEqual(referencias_duplicadas(corregidas), {})
        self.assertEqual(
            corregidas[1]["motivo_correccion"],
            "Rótulo repetido en el documento.",
        )

    def test_rechaza_una_correccion_sin_motivo(self):
        with self.assertRaisesRegex(ValueError, "motivo"):
            interpretar_configuracion_proyecto(
                {
                    "correcciones_referencias_cuadro": [
                        {
                            "referencia_original": "F1",
                            "aparicion": 2,
                            "referencia_correcta": "F2",
                        }
                    ]
                }
            )

    def test_impide_usar_la_configuracion_con_otro_archivo(self):
        configuracion = interpretar_configuracion_proyecto(
            {
                "archivos_esperados": {
                    "planta": "planta_a.pdf",
                    "detalles": "detalles_a.pdf",
                }
            }
        )

        with self.assertRaisesRegex(ValueError, "no corresponde"):
            configuracion.validar_archivos(
                planta="planta_b.pdf",
                detalles="detalles_a.pdf",
            )

    def test_no_modifica_el_diccionario_recibido(self):
        datos = {
            "archivos_esperados": {
                "planta": "carpeta/planta.pdf",
                "detalles": "otra_carpeta/detalles.pdf",
            }
        }
        original = deepcopy(datos)

        interpretar_configuracion_proyecto(datos)

        self.assertEqual(datos, original)


if __name__ == "__main__":
    unittest.main()
