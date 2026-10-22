"""Carga multipágina independiente de las entradas del motor de fundaciones."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import pymupdf
from fastapi.testclient import TestClient
from computos.api import aplicacion
from computos.ia.enrutador_documentos import (
    _analizar_fuente_tecnica,
    enrutar_documentos,
)


class ModeloNoDisponible:
    def __init__(self): self.llamadas = 0
    def clasificar_texto(self, texto):
        self.llamadas += 1
        raise RuntimeError("Artefacto de modelo de prueba no disponible")


class ClasificacionPaginasTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.raiz = Path(temp.name)
        self.client = TestClient(aplicacion.app)

    def pdf(self, nombre, textos):
        ruta = self.raiz / nombre
        with pymupdf.open() as pdf:
            for i, texto in enumerate(textos):
                pagina = pdf.new_page()
                if texto: pagina.insert_text((40, 60), texto)
                if i % 2: pagina.set_rotation(270)
            pdf.save(ruta)
        return ruta

    def test_22_paginas_con_modelo_caido_y_una_vacia(self):
        textos = ["PLANTA ARQUITECTURA COCINA", "INSTALACION SANITARIA DESAGUES", "INSTALACION ELECTRICA ILUMINACION", "GAS NATURAL PLANTA"] * 5 + ["", "MEMORIA GENERAL DEL PROYECTO"]
        ruta = self.pdf("cualquier-nombre.pdf", textos)
        modelo = ModeloNoDisponible()
        d = enrutar_documentos({"doc-001": ruta}, clasificador=modelo).a_diccionario()
        self.assertEqual(d["resumen"]["paginas"], 22)
        self.assertEqual(d["resumen"]["paginas_clasificadas"], 20)
        self.assertEqual(modelo.llamadas, 1)
        paginas = d["documentos"][0]["paginas"]
        self.assertEqual(paginas[20]["estado"], "sin_texto_nativo")
        self.assertEqual(paginas[21]["estado"], "sin_clasificacion")
        self.assertIn("sanitaria", paginas[1]["clasificacion"]["objetivos"]["disciplinas"]["etiquetas"])
        self.assertNotIn("roles_requeridos", d)
        self.assertFalse(d["motor"]["disponible"])

    def test_pdf_unido_y_sueltos_clasifican_igual(self):
        textos = ["PLANTA ARQUITECTURA COCINA", "INSTALACION SANITARIA DESAGUES", "GAS NATURAL PLANTA"]
        unido = self.pdf("unido.pdf", textos)
        sueltos = {str(i): self.pdf(f"{i}.pdf", [t]) for i, t in enumerate(textos)}
        a = enrutar_documentos({"unido": unido}, clasificador=ModeloNoDisponible())
        b = enrutar_documentos(sueltos, clasificador=ModeloNoDisponible())
        self.assertEqual([p["clasificacion"] for p in a.documentos[0]["paginas"]], [d["paginas"][0]["clasificacion"] for d in b.documentos])

    def test_fuentes_por_pagina_y_extraccion_reproducible(self):
        ruta = self.pdf("proyecto.pdf", ["PLANTA DE FUNDACIONES", "CUADRO DE FUNDACIONES", "DETALLE COLUMNA 9"])
        r = enrutar_documentos({"doc-001": ruta}, clasificador=ModeloNoDisponible())
        self.assertTrue(r.listo)
        fuentes = r.rutas_por_rol(); original = {k: v.read_bytes() for k, v in fuentes.items()}
        for rol, numero in [("planta", 1), ("detalles", 2), ("columnas", 3)]:
            self.assertEqual(r.fuentes_por_rol[rol]["pagina"], numero)
            with pymupdf.open(fuentes[rol]) as pdf:
                self.assertEqual(len(pdf), 1)
                self.assertEqual(pdf[0].rotation, 270 if numero == 2 else 0)
        self.assertEqual(original, {k: v.read_bytes() for k, v in r.rutas_por_rol().items()})

    def test_una_lamina_puede_contener_cuadro_zapatas_y_columnas(self):
        fuente = _analizar_fuente_tecnica(
            "CUADRO DE ZAPATAS\nZ-1 1.20 X 1.20\n"
            "CUADRO DE COLUMNAS\nC-1 0.25 X 0.30"
        )

        self.assertIn("detalles", fuente["roles"])
        self.assertIn("columnas", fuente["roles"])
        self.assertIn("zapatas_aisladas", fuente["tipologias"])

    def test_dos_plantas_no_se_mezclan(self):
        ruta = self.pdf("niveles.pdf", ["PLANTA DE FUNDACIONES", "PLANTA DE FUNDACIONES", "CUADRO DE FUNDACIONES", "DETALLE COLUMNA 9"])
        r = enrutar_documentos({"doc-001": ruta}, clasificador=ModeloNoDisponible())
        self.assertFalse(r.listo)
        self.assertNotIn("planta", r.fuentes_por_rol)
        self.assertEqual(len(r.documentos[0]["paginas"]), 4)

    def test_varias_paginas_de_columnas_se_conservan_como_conjunto(self):
        ruta = self.pdf("niveles.pdf", ["PLANTA DE FUNDACIONES", "CUADRO DE FUNDACIONES", "DETALLE COLUMNA 9", "PLANO DE COLUMNAS NIVEL 2"])
        r = enrutar_documentos({"doc-001": ruta}, clasificador=ModeloNoDisponible())
        self.assertTrue(r.listo)
        self.assertEqual(r.fuentes_por_rol["columnas"]["paginas"], [3, 4])
        self.assertEqual(r.fuentes_por_rol["columnas"]["modo"], "conjunto_complementario")
        with pymupdf.open(r.rutas_por_rol()["columnas"]) as pdf:
            self.assertEqual(len(pdf), 2)

    def test_porticos_son_fuente_opcional_y_no_bloquean_el_motor(self):
        ruta = self.pdf(
            "proyecto.pdf",
            [
                "PLANTA DE FUNDACIONES",
                "CUADRO DE FUNDACIONES",
                "DETALLE COLUMNA 9",
                "PORTICO 1 C1 3,50",
                "PORTICO A C1 3,50",
            ],
        )
        r = enrutar_documentos(
            {"doc-001": ruta},
            clasificador=ModeloNoDisponible(),
        )

        self.assertTrue(r.listo)
        self.assertEqual(
            r.fuentes_por_rol["porticos"]["paginas"],
            [4, 5],
        )
        with pymupdf.open(r.rutas_por_rol()["porticos"]) as pdf:
            self.assertEqual(len(pdf), 2)

    def test_api_clasifica_sin_asignacion_y_no_calcula_silenciosamente(self):
        ruta = self.pdf("proyecto.pdf", ["PLANTA DE FUNDACIONES", "CUADRO DE FUNDACIONES", "DETALLE COLUMNA 9"])
        files = [("archivos", (ruta.name, ruta.read_bytes(), "application/pdf"))]
        with patch.object(aplicacion, "procesar_archivos_hibrido", return_value={"cantidad_fundaciones": 1}) as motor:
            respuesta = self.client.post("/api/analisis/automatico/", files=files)
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta.json()["estado"], "clasificacion_documental")
            self.assertNotIn("resultado", respuesta.json())
            motor.assert_not_called()
            calculo = self.client.post("/api/analisis/automatico/", files=files, data={"ejecutar_computo": "true"})
            self.assertEqual(calculo.json()["estado"], "completado")
            motor.assert_called_once()

    def test_documento_roto_no_invalida_otro(self):
        ruta = self.pdf("arquitectura.pdf", ["PLANTA ARQUITECTURA COCINA"])
        roto = self.raiz / "roto.pdf"; roto.write_bytes(b"%PDF-danado")
        d = enrutar_documentos({"uno": roto, "dos": ruta}, clasificador=ModeloNoDisponible()).a_diccionario()
        self.assertTrue(d["documentos"][0]["advertencias"])
        self.assertEqual(d["documentos"][1]["paginas"][0]["estado"], "clasificado_multimodal")
