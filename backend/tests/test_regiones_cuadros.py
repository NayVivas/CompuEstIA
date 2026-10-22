"""Regresiones independientes de nombres, prefijos y planos del caso original."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from computos.documentos.analisis import extraer_palabras_normalizadas
from computos.documentos.auditoria_tecnica import auditar_documentos
from computos.fundaciones.cuadros import localizar_estructura_cuadro, extraer_dimensiones_cuadro
from computos.referencias import descubrir_catalogo_referencias


class RegionesCuadrosTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "nombre-arbitrario.pdf"

    def crear(self, sin_ref=False, prefijo="BA", duplicadas=False):
        with pymupdf.open() as pdf:
            p = pdf.new_page(width=1200, height=700)
            p.insert_text((30, 30), "CUADRO DE ZAPATAS")
            for x, texto in [(30, "REF"), (100, "X"), (160, "Y"), (220, "H"), (280, "ARMADURA")]:
                if not (sin_ref and texto == "REF"):
                    p.insert_text((x, 60), texto)
            for y, ref in [(90, f"{prefijo}-7"), (120, f"{prefijo}-8")]:
                for x, texto in [(30, ref), (100, "1.20"), (160, "1.40"), (220, "0.45"), (280, '1/2 c/15')]:
                    p.insert_text((x, y), texto)
            p.insert_text((650, 30), "CUADRO DE COLUMNAS")
            for x, texto in [(650, "TIPO"), (750, "X"), (810, "Y"), (870, "H")]:
                p.insert_text((x, 60), texto)
            for i in range(8):
                p.insert_text((650, 90 + i * 30), "L4" if duplicadas else f"C{i+1}")
                p.insert_text((750, 90 + i * 30), "0.25")
                p.insert_text((810, 90 + i * 30), "0.30")
            pdf.save(self.path)

    def test_no_elige_cuadro_mas_grande_de_otra_familia(self):
        self.crear(duplicadas=True)
        palabras = extraer_palabras_normalizadas(self.path)
        catalogo = descubrir_catalogo_referencias(palabras)
        self.assertEqual(catalogo.canonicas, ["BA7", "BA8"])
        self.assertTrue(catalogo.contexto_local_confirmado)
        self.assertNotIn("L4", " ".join(catalogo.advertencias))
        cuadro = localizar_estructura_cuadro(palabras, catalogo)
        dimensiones = extraer_dimensiones_cuadro(cuadro)
        self.assertEqual(dimensiones[0]["x"], "1.20")
        self.assertEqual(dimensiones[0]["y"], "1.40")

    def test_recupera_ref_vacia_sin_asignar_prefijo_fijo(self):
        self.crear(sin_ref=True, prefijo="APOYO")
        palabras = extraer_palabras_normalizadas(self.path)
        catalogo = descubrir_catalogo_referencias(palabras)
        self.assertEqual(catalogo.canonicas, ["APOYO7", "APOYO8"])
        cuadro = localizar_estructura_cuadro(palabras, catalogo)
        self.assertEqual(extraer_dimensiones_cuadro(cuadro)[1]["h"], "0.45")

    def test_auditoria_no_inventa_duplicidad_en_tabla_ajena(self):
        self.crear(duplicadas=True)
        diagnostico = {"documentos": [{"documento_id": "d", "nombre": self.path.name,
            "sha256": "a" * 64, "paginas": [{"pagina": 1, "caracteres": 200,
                "clasificacion": {"objetivos": {
                    "contenidos": {"etiquetas": ["fundaciones", "columnas_pilares"]},
                    "roles_documentales": {"etiquetas": ["cuadro_planilla"]}}}}]}]}
        resultado = auditar_documentos({"d": self.path}, diagnostico)
        self.assertFalse(any(i["codigo"] == "referencia_duplicada_cuadro" for i in resultado["incidencias"]))
        self.assertTrue(resultado["politica_calculo"]["permite_calculo_parcial"])

    def test_rechaza_tabla_ajena_aunque_la_pagina_mencione_cimientos(self):
        with pymupdf.open() as pdf:
            p = pdf.new_page()
            p.insert_text((30, 25), "NOTA: REVISAR CIMIENTOS EN OTRA LAMINA")
            p.insert_text((30, 100), "CUADRO DE COLUMNAS")
            p.insert_text((30, 130), "TIPO                 X          Y")
            p.insert_text((30, 160), "C1")
            p.insert_text((30, 190), "C2")
            pdf.save(self.path)
        with self.assertRaisesRegex(ValueError, "atribuible a fundaciones"):
            descubrir_catalogo_referencias(extraer_palabras_normalizadas(self.path))
