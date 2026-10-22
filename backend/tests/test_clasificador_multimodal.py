"""Pruebas de la fusión multimodal EXP22 sin depender de planos históricos."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from computos.ia.clasificador_multimodal import (
    extraer_caracteristicas_multimodales,
    fusionar_clasificacion,
    motivos_ocr_adaptativo,
    proponer_roles_motor,
)


def evidencia_vacia():
    return {
        "objetivos": {
            objetivo: {"etiquetas": [], "detalle": []}
            for objetivo in ("disciplinas", "roles_documentales", "contenidos")
        },
        "evidencias": [],
        "requiere_revision": False,
    }


def caracteristicas_tecnicas():
    return {
        "pagina": {"imagenes": 0},
        "texto_espacial": {
            "palabras": 42,
            "terminos_tecnicos": 5,
            "fraccion_palabras_numericas": 0.16,
            "marcas_diametro": 1,
            "texto_por_zona": {
                "superior": "PLANTA DE FUNDACIONES",
                "central": "ZAPATA Z1 ARMADURA",
                "inferior": "ESTRUCTURA",
                "izquierda": "",
                "derecha": "DETALLE DE FUNDACION",
            },
        },
        "geometria_vectorial": {"objetos_vectoriales": 120, "segmentos": 260},
        "imagen_renderizada": {"densidad_tinta": 0.10},
    }


def modelo_estructural():
    return {
        "objetivos": {
            "disciplinas": {
                "detalle": [
                    {"etiqueta": "estructura", "seleccionada": True, "margen": 0.8}
                ]
            },
            "roles_documentales": {
                "detalle": [
                    {"etiqueta": "planta", "seleccionada": True, "margen": 0.7}
                ]
            },
            "contenidos": {
                "detalle": [
                    {"etiqueta": "fundaciones", "seleccionada": True, "margen": 0.9}
                ]
            },
        }
    }


class ClasificadorMultimodalTests(unittest.TestCase):
    def test_lamina_combinada_completa_roles_sin_perder_titulo_explicito(self):
        clasificacion = {
            "objetivos": {
                "disciplinas": {"etiquetas": ["estructura"]},
                "roles_documentales": {
                    "etiquetas": ["planta", "detalle", "cuadro_planilla"]
                },
                "contenidos": {
                    "etiquetas": ["fundaciones", "columnas_pilares"]
                },
            },
            "decisiones_multimodales": [
                {
                    "objetivo": objetivo,
                    "etiqueta": etiqueta,
                    "decision": "confirmada",
                    "fuerza": fuerza,
                }
                for objetivo, etiqueta, fuerza in (
                    ("disciplinas", "estructura", 0.92),
                    ("roles_documentales", "planta", 0.86),
                    ("roles_documentales", "detalle", 0.94),
                    ("roles_documentales", "cuadro_planilla", 0.94),
                    ("contenidos", "fundaciones", 0.94),
                    ("contenidos", "columnas_pilares", 0.94),
                )
            ],
        }
        fuente = {
            "roles": ["detalles", "columnas"],
            "tipologias": ["zapatas_aisladas"],
            "exclusiones_roles": [],
        }

        propuesta = proponer_roles_motor(clasificacion, fuente)

        self.assertEqual(
            set(propuesta["roles"]),
            {"planta", "detalles", "columnas"},
        )
        self.assertEqual(
            propuesta["origenes"]["planta"],
            "inferencia_multimodal_con_contexto_tecnico",
        )
        self.assertEqual(
            propuesta["origenes"]["detalles"],
            "titulo_tecnico_explicito",
        )

    def test_modelo_necesita_respaldo_de_la_pagina(self):
        resultado = fusionar_clasificacion(
            modelo_estructural(), evidencia_vacia(), caracteristicas_tecnicas(), {}
        )
        self.assertEqual(resultado["estado"], "clasificado_multimodal")
        self.assertIn(
            "estructura",
            resultado["objetivos"]["disciplinas"]["etiquetas"],
        )
        self.assertIn(
            "fundaciones",
            resultado["objetivos"]["contenidos"]["etiquetas"],
        )

        vacias = caracteristicas_tecnicas()
        vacias["texto_espacial"].update(
            palabras=0,
            terminos_tecnicos=0,
            fraccion_palabras_numericas=0,
            marcas_diametro=0,
            texto_por_zona={},
        )
        vacias["geometria_vectorial"] = {
            "objetos_vectoriales": 0,
            "segmentos": 0,
        }
        vacias["imagen_renderizada"] = {"densidad_tinta": 0}
        resultado = fusionar_clasificacion(
            modelo_estructural(), evidencia_vacia(), vacias, {}
        )
        self.assertEqual(resultado["estado"], "sin_clasificacion")
        self.assertIn(
            "fundaciones",
            resultado["propuestas_modelo_sin_evidencia"]["contenidos"],
        )

    def test_disciplina_no_estructural_dominante_evitar_falso_positivo(self):
        evidencia = evidencia_vacia()
        evidencia["objetivos"]["disciplinas"]["etiquetas"] = ["estructura"]
        evidencia["objetivos"]["contenidos"]["etiquetas"] = ["vigas"]
        modelo = {
            "objetivos": {
                "disciplinas": {
                    "detalle": [
                        {"etiqueta": "sanitaria", "seleccionada": True, "margen": 0.9},
                        {"etiqueta": "estructura", "seleccionada": False, "margen": -0.4},
                    ]
                },
                "roles_documentales": {"detalle": []},
                "contenidos": {"detalle": []},
            }
        }
        resultado = fusionar_clasificacion(
            modelo, evidencia, caracteristicas_tecnicas(), {}
        )
        disciplinas = resultado["objetivos"]["disciplinas"]["etiquetas"]
        contenidos = resultado["objetivos"]["contenidos"]["etiquetas"]
        self.assertIn("sanitaria", disciplinas)
        self.assertNotIn("estructura", disciplinas)
        self.assertNotIn("vigas", contenidos)

    def test_ocr_adaptativo_tambien_detecta_texto_parcial(self):
        caracteristicas = caracteristicas_tecnicas()
        caracteristicas["geometria_vectorial"]["objetos_vectoriales"] = 80
        self.assertIn(
            "texto_nativo_escaso_en_plano_vectorial",
            motivos_ocr_adaptativo("PLANTA C-1", caracteristicas),
        )

    def test_extrae_rasgos_de_un_pdf_real_generado(self):
        with TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "plano.pdf"
            with pymupdf.open() as pdf:
                pagina = pdf.new_page(width=800, height=500)
                pagina.insert_text((40, 40), "PLANTA DE FUNDACIONES Z1 1.20 x 1.20")
                pagina.draw_rect(pymupdf.Rect(100, 100, 300, 260))
                pagina.draw_line((100, 180), (300, 180))
                pdf.save(ruta)
            with pymupdf.open(ruta) as pdf:
                pagina = pdf[0]
                rasgos = extraer_caracteristicas_multimodales(
                    pagina, pagina.get_text("text")
                )
            self.assertGreater(rasgos["texto_espacial"]["palabras"], 3)
            self.assertGreater(rasgos["geometria_vectorial"]["objetos_vectoriales"], 0)
            self.assertGreater(rasgos["imagen_renderizada"]["densidad_tinta"], 0)


if __name__ == "__main__":
    unittest.main()
