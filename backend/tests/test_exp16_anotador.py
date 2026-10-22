"""Pruebas del flujo de clasificación EXP16."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz
from fastapi import FastAPI
from fastapi.testclient import TestClient

import computos.api.exp16_anotador as exp16


class Exp16AnnotadorTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.dataset = Path(self.temporal.name)
        self.inventory = self.dataset / "EXP16_paginas_inventario.csv"
        self.annotations = self.dataset / "EXP16_anotaciones.json"
        pdf_path = (
            self.dataset
            / "documentos"
            / "Nuevos"
            / "Topogrefia"
            / "Proyecto01"
            / "corte_topografico.pdf"
        )
        pdf_path.parent.mkdir(parents=True)
        with fitz.open() as document:
            page = document.new_page(width=600, height=400)
            page.insert_text((72, 72), "CORTE A-A LEVANTAMIENTO TOPOGRAFICO")
            document.save(pdf_path)

        row = {
            "proyecto_id": "Topografia_Proyecto01",
            "grupo_fuente": "Topogrefia/Proyecto01",
            "documento": pdf_path.name,
            "ruta_relativa": pdf_path.relative_to(self.dataset).as_posix(),
            "pagina": 1,
            "cantidad_palabras": 4,
            "cantidad_caracteres": 36,
            "cantidad_imagenes": 0,
            "cantidad_objetos_vectoriales": 0,
            "tiene_texto": False,
            "tiene_imagenes": False,
            "requiere_ocr": True,
            "tipo_contenido": "contenido_escaso",
            "es_topografia_origen": True,
            "rotacion_grados": 0,
            "ancho_pt": 600,
            "alto_pt": 400,
            "sha256_archivo": "prueba",
            "pistas_texto": "CORTE A-A LEVANTAMIENTO TOPOGRAFICO",
            "grupo_revision_duplicado": "revision_prueba",
        }
        with self.inventory.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        self.annotations.write_text("{}\n", encoding="utf-8")

        self.original_dataset = exp16.DATASET_DIR
        self.original_inventory = exp16.INVENTARIO
        self.original_annotations = exp16.ANOTACIONES
        exp16.DATASET_DIR = self.dataset
        exp16.INVENTARIO = self.inventory
        exp16.ANOTACIONES = self.annotations

        app = FastAPI()
        app.include_router(exp16.router)
        self.client = TestClient(app)

    def tearDown(self):
        exp16.DATASET_DIR = self.original_dataset
        exp16.INVENTARIO = self.original_inventory
        exp16.ANOTACIONES = self.original_annotations
        self.temporal.cleanup()

    def test_lista_paginas_con_sugerencias_sin_preseleccionar(self):
        response = self.client.get(
            "/api/exp16/paginas",
            params={"proyecto_id": "Topografia_Proyecto01"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        page = response.json()[0]
        suggestion_values = {
            suggestion["valor"]
            for suggestion in page["sugerencias"]
        }
        self.assertIn("implantacion_topografia", suggestion_values)
        self.assertIn("corte", suggestion_values)
        self.assertIn("ocr_asistido", suggestion_values)
        self.assertEqual(page["anotacion"], {})

    def test_renderiza_la_pagina(self):
        response = self.client.get(
            "/api/exp16/pagina-imagen",
            params={
                "proyecto_id": "Topografia_Proyecto01",
                "documento": "corte_topografico.pdf",
                "pagina": 1,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertGreater(len(response.content), 100)

    def test_guarda_decision_y_exporta_json(self):
        payload = {
            "proyecto_id": "Topografia_Proyecto01",
            "documento": "corte_topografico.pdf",
            "pagina": 1,
            "disciplinas": ["implantacion_topografia"],
            "roles_documentales": ["corte"],
            "contenidos": ["terreno", "niveles"],
            "revisor": "Ingeniero de prueba",
            "decision": "confirmada",
            "ambiguo": "no",
            "motivo_ambiguedad": "",
            "evidencia_profesional": "Rótulo CORTE A-A y curvas de nivel.",
            "observaciones": "",
            "incluir_en_metricas": False,
        }
        saved = self.client.post("/api/exp16/anotaciones", json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertFalse(saved.json()["anotacion"]["incluir_en_metricas"])

        summary = self.client.get("/api/exp16/resumen")
        self.assertEqual(summary.status_code, 200, summary.text)
        self.assertEqual(summary.json()["confirmadas"], 1)
        self.assertEqual(summary.json()["excluidas_metricas"], 1)

        exported = self.client.get("/api/exp16/exportar")
        self.assertEqual(exported.status_code, 200, exported.text)
        data = json.loads(exported.content.decode("utf-8"))
        self.assertEqual(data["dataset"], "EXP16")
        self.assertEqual(len(data["filas"]), 1)
        self.assertEqual(data["filas"][0]["roles_documentales"], ["corte"])


if __name__ == "__main__":
    unittest.main()
