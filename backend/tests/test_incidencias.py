import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from computos.api import aplicacion
from computos.incidencias import Incidencia, IncidenciaBloqueante


class IncidenciasApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(aplicacion.app)

    def test_un_error_bloqueante_se_convierte_en_incidencia_revisable(self):
        incidencia = Incidencia(
            tipo="REFERENCIA_DUPLICADA",
            categoria="referencia_duplicada",
            severidad="error",
            titulo="Referencias duplicadas en el cuadro",
            mensaje="F12 aparece dos veces.",
            familia="fundaciones",
            evidencias=[
                {
                    "etiqueta": "F12 · aparición 1",
                    "valor": "Página 2",
                    "referencia": "F12",
                    "aparicion": 1,
                    "pagina": 2,
                }
            ],
            opciones=[
                {
                    "id": "corregir_referencia",
                    "titulo": "Corregir una aparición",
                }
            ],
        )

        with patch.object(
            aplicacion,
            "procesar_archivos_hibrido",
            side_effect=IncidenciaBloqueante(incidencia),
        ):
            respuesta = self.client.post(
                "/api/analisis/",
                files={
                    "planta": ("planta.pdf", b"%PDF-1.4\n", "application/pdf"),
                    "detalles": ("detalles.pdf", b"%PDF-1.4\n", "application/pdf"),
                    "columnas": ("columnas.pdf", b"%PDF-1.4\n", "application/pdf"),
                },
            )

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["estado"], "requiere_revision")
        self.assertEqual(
            cuerpo["resultado"]["incidencias"][0]["tipo"],
            "REFERENCIA_DUPLICADA",
        )

    def test_no_existe_resolucion_arbitraria_que_omita_validaciones(self):
        # La corrección de referencias tiene su contrato revision_cuadro con
        # huellas y evidencia. Una incidencia genérica no autoriza inventarla.
        respuesta = self.client.post(
            "/api/analisis/inexistente/incidencias/inexistente/resolver",
            json={"accion": "corregir_referencia"},
        )
        self.assertEqual(respuesta.status_code, 404)
