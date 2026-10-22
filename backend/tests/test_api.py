import unittest
from unittest.mock import patch
from computos.configuracion.proyecto import cargar_configuracion_proyecto
from computos.configuracion.parametros import BASE_DIR

from fastapi.testclient import TestClient

from computos.api import app
from computos.configuracion.parametros import PDF_DIR


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_estado(self):
        respuesta = self.client.get(
            "/api/estado"
        )

        self.assertEqual(
            respuesta.status_code,
            200,
        )
        self.assertEqual(
            respuesta.json()["estado"],
            "disponible",
        )

    def test_rechaza_archivos_que_no_son_pdf(self):
        archivos = {
            "planta": (
                "planta.txt",
                b"texto",
                "text/plain",
            ),
            "detalles": (
                "detalles.pdf",
                b"%PDF-prueba",
                "application/pdf",
            ),
            "columnas": (
                "columnas.pdf",
                b"%PDF-prueba",
                "application/pdf",
            ),
        }

        respuesta = self.client.post(
            "/api/analisis/",
            files=archivos,
        )

        self.assertEqual(
            respuesta.status_code,
            422,
        )
        self.assertIn(
            "planta",
            respuesta.json()["detail"],
        )

    def test_procesa_los_pdf_incluidos_y_permite_consultar_resultado(
        self,
    ):
        rutas = {
            "planta": (
                PDF_DIR
                / "Fundaciones"
                / "Fundaciones_1.pdf"
            ),
            "detalles": (
                PDF_DIR
                / "Fundaciones"
                / "Fundaciones_2.pdf"
            ),
            "columnas": (
                PDF_DIR
                / "Columnas"
                / "Columnas.pdf"
            ),
        }

        if not all(r.is_file() for r in rutas.values()):
            self.skipTest("Faltan los PDF externos de regresión del cómputo.")
        configuracion = cargar_configuracion_proyecto(BASE_DIR / "configuraciones" / "proyecto_actual.json")
        with (
            patch("computos.api.servicio._seleccionar_configuracion", return_value=(configuracion, False)),
            rutas["planta"].open("rb") as planta,
            rutas["detalles"].open("rb") as detalles,
            rutas["columnas"].open("rb") as columnas,
        ):
            respuesta = self.client.post(
                "/api/analisis/",
                files={
                    "planta": (
                        rutas["planta"].name,
                        planta,
                        "application/pdf",
                    ),
                    "detalles": (
                        rutas["detalles"].name,
                        detalles,
                        "application/pdf",
                    ),
                    "columnas": (
                        rutas["columnas"].name,
                        columnas,
                        "application/pdf",
                    ),
                },
            )

        self.assertEqual(
            respuesta.status_code,
            200,
            respuesta.text,
        )

        cuerpo = respuesta.json()
        resultado = cuerpo["resultado"]

        # -------------------------------------------------
        # RESULTADOS GENERALES
        # -------------------------------------------------

        self.assertEqual(
            resultado["cantidad_fundaciones"],
            61,
        )
        self.assertEqual(
            resultado["cantidad_tipos"],
            13,
        )
        self.assertAlmostEqual(
            resultado["volumen_hormigon_m3"],
            194.71975,
        )
        self.assertEqual(
            len(resultado["fundaciones"]),
            13,
        )
        self.assertFalse(
            resultado["configuracion_automatica"]
        )

        # -------------------------------------------------
        # UBICACIONES
        # -------------------------------------------------

        ubicaciones = resultado[
            "ubicaciones_fundaciones"
        ]

        validacion = resultado[
            "validacion_ubicaciones"
        ]

        self.assertEqual(
            len(ubicaciones),
            61,
        )

        self.assertEqual(
            validacion["cantidad_esperada"],
            61,
        )

        self.assertEqual(
            validacion["cantidad_detectada"],
            61,
        )

        self.assertTrue(
            validacion["coincide_con_resumen"]
        )

        # Todos los identificadores deben ser únicos.

        identificadores = [
            ubicacion["identificador"]
            for ubicacion in ubicaciones
        ]

        self.assertEqual(
            len(identificadores),
            len(set(identificadores)),
        )

        # F1 debe tener cuatro ubicaciones.

        ubicaciones_f1 = [
            ubicacion
            for ubicacion in ubicaciones
            if ubicacion["referencia"] == "F1"
        ]

        self.assertEqual(
            len(ubicaciones_f1),
            4,
        )

        self.assertEqual(
            [
                ubicacion["identificador"]
                for ubicacion in ubicaciones_f1
            ],
            [
                "F1-01",
                "F1-02",
                "F1-03",
                "F1-04",
            ],
        )

        # Las coordenadas pertenecen al PDF.
        # Los ejes estructurales siguen pendientes.

        self.assertTrue(
            all(
                ubicacion[
                    "ubicacion_pdf_detectada"
                ]
                for ubicacion in ubicaciones
            )
        )

        self.assertTrue(
            all(
                not ubicacion[
                    "ejes_confirmados"
                ]
                for ubicacion in ubicaciones
            )
        )

        # -------------------------------------------------
        # CONSULTA POSTERIOR DEL RESULTADO
        # -------------------------------------------------

        consulta = self.client.get(
            (
                "/api/analisis/"
                f"{cuerpo['analisis_id']}"
                "/resultados/"
            )
        )

        self.assertEqual(
            consulta.status_code,
            200,
        )
        self.assertEqual(
            consulta.json(),
            cuerpo,
        )

    def test_cors_permite_el_servidor_de_vite(self):
        respuesta = self.client.options(
            "/api/estado",
            headers={
                "Origin": (
                    "http://localhost:5173"
                ),
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(
            respuesta.status_code,
            200,
        )
        self.assertEqual(
            respuesta.headers[
                "access-control-allow-origin"
            ],
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()