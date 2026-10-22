"""Contrato de revisión anterior al cómputo, con PDF reales y persistencia."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pymupdf
from fastapi.testclient import TestClient

from computos.api import app
from computos.configuracion.parametros import PDF_DIR


class RevisionCuadroApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all((PDF_DIR / ruta).is_file() for ruta in ("Fundaciones/Fundaciones_1.pdf", "Fundaciones/Fundaciones_2.pdf", "Columnas/Columnas.pdf")):
            raise unittest.SkipTest("Faltan los PDF externos de regresión del cuadro.")
        cls.client = TestClient(app)
        cls.planta = (PDF_DIR / "Fundaciones" / "Fundaciones_1.pdf").read_bytes()
        cls.columnas = (PDF_DIR / "Columnas" / "Columnas.pdf").read_bytes()
        # Mismo cuadro con F12 repetida, fuera de la excepción del ejemplo por SHA.
        with pymupdf.open(PDF_DIR / "Fundaciones" / "Fundaciones_2.pdf") as pdf:
            pdf.set_metadata({"title": "Juego nuevo para revisión profesional"})
            cls.detalles = pdf.tobytes()

    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.registros = Path(temporal.name)
        parche = patch("computos.fundaciones.revision_cuadro.DIRECTORIO_REVISIONES", self.registros)
        parche.start()
        self.addCleanup(parche.stop)
        self.addCleanup(patch.stopall)

    def enviar(self, revision=None, proyecto="proyecto-prueba", sufijo="", detalles=None):
        data = {"ejecutar_computo": "true", "proyecto_id": proyecto, "asignaciones": json.dumps({"planta": "doc-001", "detalles": "doc-002", "columnas": "doc-003"})}
        if revision is not None:
            data["revision_cuadro"] = json.dumps(revision)
        return self.client.post("/api/analisis/automatico/", data=data, files=[
            ("archivos", (f"planta{sufijo}.pdf", self.planta, "application/pdf")),
            ("archivos", (f"cuadro{sufijo}.pdf", detalles or self.detalles, "application/pdf")),
            ("archivos", (f"columnas{sufijo}.pdf", self.columnas, "application/pdf")),
        ])

    def obtener_decision(self):
        respuesta = self.enviar()
        self.assertEqual(respuesta.status_code, 200, respuesta.text[:1000])
        body = respuesta.json()
        self.assertEqual(body["estado"], "requiere_revision_cuadro")
        self.assertNotIn("resultado", body)
        revision = body["revision_cuadro"]
        self.assertEqual(revision["duplicadas"], {"F12": 2})
        self.assertEqual([r["aparicion_original"] for r in revision["filas"]], [1, 2])
        self.assertTrue(revision["paginas"][0]["imagen"].startswith("data:image/png;base64,"))
        self.assertIn("F13", revision["referencias_planta_sin_cuadro"])
        self.assertFalse(list(self.registros.iterdir()))
        return {
            "huellas_archivos": revision["huellas_archivos"],
            "revisor": "Profesional de prueba",
            "correcciones_referencias_cuadro": [{
                "referencia_original": "F12",
                "aparicion": 2,
                "referencia_correcta": "F13",
                "motivo": "La planta identifica F13; la segunda aparición del cuadro está repetida.",
            }],
        }

    def test_revisa_reprocesa_y_reutiliza_solo_para_mismo_proyecto_y_contenido(self):
        decision = self.obtener_decision()
        respuesta = self.enviar(decision)
        self.assertEqual(respuesta.status_code, 200, respuesta.text[:1000])
        body = respuesta.json()
        self.assertEqual(body["estado"], "completado")
        resultado = body["resultado"]
        self.assertEqual(resultado["cantidad_fundaciones"], 61)
        self.assertEqual(resultado["cantidad_tipos"], 13)
        self.assertEqual(resultado["revisiones_cuadro"][0]["revisor"], decision["revisor"])
        self.assertEqual(len(list(self.registros.glob("*.json"))), 1)
        reutilizado = self.enviar(sufijo="-renombrado").json()
        self.assertEqual(reutilizado["estado"], "completado")
        self.assertEqual(reutilizado["resultado"]["revisiones_cuadro"], resultado["revisiones_cuadro"])
        self.assertEqual(self.enviar(proyecto="otro").json()["estado"], "requiere_revision_cuadro")
        with pymupdf.open(stream=self.detalles, filetype="pdf") as pdf:
            pdf.set_metadata({"title": "Otra revisión de los planos"})
            nueva_version = pdf.tobytes()
        self.assertEqual(self.enviar(detalles=nueva_version).json()["estado"], "requiere_revision_cuadro")

    def test_rechaza_huellas_motivo_aparicion_y_colisiones(self):
        decision = self.obtener_decision()
        casos = []
        for campo, valor in [("aparicion", 3), ("referencia_correcta", "F11"), ("motivo", ""), ("referencia_original", "F1")]:
            cambio = deepcopy(decision)
            cambio["correcciones_referencias_cuadro"][0][campo] = valor
            casos.append(cambio)
        cambio = deepcopy(decision)
        cambio["huellas_archivos"]["detalles"] = "otro-pdf"
        casos.append(cambio)
        cambio = deepcopy(decision)
        cambio["revisor"] = ""
        casos.append(cambio)
        for cambio in casos:
            with self.subTest(cambio=cambio):
                respuesta = self.enviar(cambio)
                self.assertEqual(respuesta.json()["estado"], "requiere_revision", respuesta.text[:1000])
                self.assertFalse(list(self.registros.iterdir()))

    def test_no_guarda_correccion_si_falla_motor(self):
        decision = self.obtener_decision()
        with patch("computos.api.servicio.procesar_fundaciones", side_effect=ValueError("Falta una armadura")):
            respuesta = self.enviar(decision)
        self.assertEqual(respuesta.json()["estado"], "requiere_revision")
        self.assertFalse(list(self.registros.iterdir()))

    def test_rechaza_revision_que_no_es_objeto(self):
        self.assertEqual(self.enviar([]).status_code, 422)
