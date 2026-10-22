"""Regresiones generales para planos sin cuadro único de fundaciones."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pymupdf

from computos.fundaciones.geometria_distribuida import (
    calcular_geometria_revisada,
    preparar_revision_geometrica,
)
from computos.fundaciones.cimientos_corridos import (
    calcular_cimientos_corridos_revisados,
    preparar_revision_cimientos_corridos,
)
from computos.ia.enrutador_documentos import enrutar_documentos


class SinModelo:
    def clasificar_texto(self, _texto):
        return {"objetivos": {}, "estado": "sin_modelo"}


def crear_pdf(ruta: Path, textos, rotacion=0):
    with pymupdf.open() as documento:
        pagina = documento.new_page(width=600, height=400)
        for posicion, texto in textos:
            pagina.insert_text(posicion, texto, fontsize=12)
        pagina.set_rotation(rotacion)
        documento.save(ruta)


class GeometriaDistribuidaTests(unittest.TestCase):
    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)

    def juego_aislado(self):
        planta = self.raiz / "documento-a.pdf"
        detalles = self.raiz / "documento-b.pdf"
        columnas = self.raiz / "documento-c.pdf"
        crear_pdf(
            planta,
            [
                ((30, 30), "PLANTA DE FUNDACIONES"),
                ((100, 100), "Z1"),
                ((300, 200), "Z2"),
                ((400, 330), "DETALLE DE ZAPATAS"),
                ((520, 330), "Z1"),
            ],
            rotacion=270,
        )
        # Dos cotas exteriores y un contorno coherente, no números sueltos.
        with pymupdf.open(planta) as pdf:
            p = pdf[0]
            p.draw_rect(pymupdf.Rect(90, 80, 138, 140))
            p.insert_text((105, 77), "1.20", fontsize=6)
            p.insert_text((146, 125), "1.50", fontsize=6, rotate=90)
            p.draw_rect(pymupdf.Rect(290, 180, 370, 280))
            p.insert_text((315, 177), "2.00", fontsize=6)
            p.insert_text((378, 245), "2.50", fontsize=6, rotate=90)
            pdf.saveIncr()
        crear_pdf(
            detalles,
            [
                ((30, 30), "DETALLE DE ZAPATAS AISLADAS"),
                ((30, 80), "Z1 1.20 X 1.50"),
            ],
        )
        crear_pdf(
            columnas,
            [
                ((30, 30), "DETALLE DE COLUMNAS"),
                ((30, 80), "C1 0.30 X 0.30"),
            ],
        )
        return {"a": planta, "b": detalles, "c": columnas}

    def test_enruta_geometria_distribuida_sin_nombres_especiales(self):
        enrutamiento = enrutar_documentos(
            self.juego_aislado(), clasificador=SinModelo()
        )
        self.assertFalse(enrutamiento.listo)
        self.assertTrue(enrutamiento.requiere_revision_geometrica)
        self.assertEqual(enrutamiento.modo_detalles, "geometria_distribuida")
        self.assertIn("zapatas_aisladas", enrutamiento.tipologias)
        self.assertEqual(
            enrutamiento.a_diccionario()["capacidad_computo"]["estado"],
            "requiere_revision_geometrica",
        )

    def test_revision_exacta_y_computo_solo_de_datos_confirmados(self):
        enrutamiento = enrutar_documentos(
            self.juego_aislado(), clasificador=SinModelo()
        )
        rutas = enrutamiento.rutas_para_revision_geometrica()
        grupo = enrutamiento.fuentes_por_rol["planta"]
        propuesta = preparar_revision_geometrica(
            rutas["planta"],
            fuentes_planta=grupo["fuentes"],
            identidad_fuentes=enrutamiento.identidad_fuentes(),
        )
        self.assertEqual(len(propuesta["elementos"]), 2)
        self.assertTrue(all(item["x_m_propuesto"] for item in propuesta["elementos"]))
        self.assertTrue(all(item["y_m_propuesto"] for item in propuesta["elementos"]))
        for item in propuesta["elementos"]:
            pagina = propuesta["paginas"][item["pagina_motor"] - 1]
            self.assertLessEqual(item["caja_visual"]["x1"], pagina["ancho_visual_pt"])
            self.assertLessEqual(item["caja_visual"]["y1"], pagina["alto_visual_pt"])

        decision = {
            "identidad_fuentes": propuesta["identidad_fuentes"],
            "revisor": "Ingeniera de prueba",
            "motivo": "Dimensiones comprobadas sobre las cotas de la planta.",
            "elementos": [
                {
                    "id": item["id"],
                    "incluir": True,
                    "referencia": item["referencia_propuesta"],
                    "x_m": item["x_m_propuesto"],
                    "y_m": item["y_m_propuesto"],
                    "h_m": 0.40,
                }
                for item in propuesta["elementos"]
            ],
        }
        resultado = calcular_geometria_revisada(propuesta, decision)
        self.assertEqual(resultado["cantidad_fundaciones"], 2)
        self.assertGreater(resultado["volumen_hormigon_m3"], 0)
        self.assertGreater(resultado["encofrado_zapatas_m2"], 0)
        self.assertIsNone(resultado["peso_acero_kg"])
        self.assertEqual(
            resultado["alertas_analisis"][0]["categoria"],
            "armadura_no_disponible",
        )

        equivocada = {**decision, "identidad_fuentes": "0" * 64}
        with self.assertRaisesRegex(ValueError, "otra combinación"):
            calcular_geometria_revisada(propuesta, equivocada)

    def test_cimiento_corrido_se_enruta_a_su_propia_revision(self):
        ruta = self.raiz / "lamina.pdf"
        crear_pdf(
            ruta,
            [
                ((30, 30), "PLANO DE CIMENTACION"),
                ((30, 70), "TIPOS DE CIMIENTOS CORRIDOS"),
                ((30, 110), "TIPOS DE CASTILLOS"),
            ],
        )
        enrutamiento = enrutar_documentos(
            {"unico": ruta}, clasificador=SinModelo()
        )
        self.assertFalse(enrutamiento.listo)
        self.assertTrue(enrutamiento.requiere_revision_geometrica)
        self.assertEqual(enrutamiento.tipo_revision_geometrica, "cimientos_corridos")
        self.assertIsNone(enrutamiento.tipologia_no_implementada)
        self.assertEqual(
            enrutamiento.a_diccionario()["capacidad_computo"]["estado"],
            "requiere_revision_geometrica",
        )

    def test_cimiento_con_castillos_se_infiere_como_corrido(self):
        ruta = self.raiz / "sistema-mamposteria.pdf"
        crear_pdf(
            ruta,
            [
                ((30, 30), "PLANO DE CIMENTACION"),
                ((30, 70), "TIPOS DE CIMIENTOS"),
                ((30, 105), "C-1"),
                ((100, 105), "C-2"),
                ((30, 145), "TIPOS DE CASTILLOS"),
            ],
        )
        enrutamiento = enrutar_documentos(
            {"unico": ruta}, clasificador=SinModelo()
        )
        self.assertIsNone(enrutamiento.tipologia_no_implementada)
        self.assertTrue(enrutamiento.requiere_revision_geometrica)
        self.assertEqual(enrutamiento.tipo_revision_geometrica, "cimientos_corridos")

    def test_tipos_en_detalle_sin_trazo_en_planta_se_muestran_sin_sumar_volumen(self):
        planta = self.raiz / "planta.pdf"
        detalles = self.raiz / "detalles.pdf"
        crear_pdf(planta, [((20, 30), "PLANTA DE CIMENTACION"), ((100, 220), "C-2")])
        crear_pdf(detalles, [
            ((20, 30), "TIPOS DE CIMIENTOS"),
            ((50, 70), "C-1"), ((170, 70), "C-2"),
        ])
        with patch("computos.fundaciones.cimientos_corridos._dimensiones_ocr", return_value={}), \
             patch("computos.fundaciones.cimientos_corridos._medir_longitudes", return_value=({"C-2": 12.5}, {"paginas": []})), \
             patch("computos.fundaciones.cimientos_corridos.diagnostico_ocr", return_value={"listo": False}):
            propuesta = preparar_revision_cimientos_corridos(
                planta, detalles,
                fuentes_planta=[{"archivo": "planta.pdf", "sha256": "a" * 64, "pagina": 1}],
                fuentes_detalles=[{"archivo": "detalles.pdf", "sha256": "b" * 64, "pagina": 1}],
                identidad_fuentes={"sha256": "c" * 64, "fuentes": []},
            )
        por_ref = {item["referencia_propuesta"]: item for item in propuesta["elementos"]}
        self.assertEqual(set(por_ref), {"C-1", "C-2"})
        self.assertEqual(por_ref["C-1"]["origen_referencia"], "solo_detalle")
        self.assertEqual(por_ref["C-1"]["fuente"]["archivo"], "detalles.pdf")
        self.assertIsNone(por_ref["C-1"]["longitud_m_propuesta"])
        self.assertEqual(por_ref["C-2"]["longitud_m_propuesta"], 12.5)
        decision = {
            "version": propuesta["version"], "identidad_fuentes": propuesta["identidad_fuentes"],
            "revisor": "Ingeniera de prueba", "motivo": "Solo la referencia trazada fue verificada en planta.",
            "elementos": [
                {"id": por_ref["C-1"]["id"], "incluir": False, "referencia": "C-1",
                 "motivo_exclusion": por_ref["C-1"]["motivo_exclusion_propuesto"]},
                {"id": por_ref["C-2"]["id"], "incluir": True, "referencia": "C-2",
                 "ancho_superior_m": .3, "ancho_base_m": .6, "altura_m": .4,
                 "longitud_m": 12.5, "material": None},
            ],
        }
        resultado = calcular_cimientos_corridos_revisados(propuesta, decision)
        self.assertEqual(resultado["volumen_cimientos_corridos_m3"], 2.25)
        self.assertEqual(resultado["cantidad_tipos_fundacion"], 1)
        sin_justificar = {
            **decision,
            "elementos": [
                {**decision["elementos"][0], "incluir": True, "ancho_superior_m": .3,
                 "ancho_base_m": .7, "altura_m": .4, "longitud_m": 5.0},
                decision["elementos"][1],
            ],
        }
        with self.assertRaisesRegex(ValueError, "Documentá dónde verificaste"):
            calcular_cimientos_corridos_revisados(propuesta, sin_justificar)
        sin_justificar["elementos"][0]["motivo_inclusion"] = (
            "El tipo aparece en una planta complementaria y el recorrido se midió allí."
        )
        confirmado = calcular_cimientos_corridos_revisados(propuesta, sin_justificar)
        self.assertEqual(confirmado["cantidad_tipos_fundacion"], 2)

    def test_tipos_del_detalle_se_buscan_en_todas_las_plantas_seleccionadas(self):
        planta = self.raiz / "plantas-complementarias.pdf"
        detalles = self.raiz / "secciones.pdf"
        with pymupdf.open() as documento:
            for titulo, referencias in (
                ("PLANTA DE CIMENTACION 1", ("C-2",)),
                ("PLANTA DE CIMENTACION 2", ("C-1", "C-4")),
            ):
                pagina = documento.new_page(width=600, height=400)
                pagina.insert_text((20, 30), titulo, fontsize=12)
                for indice, referencia in enumerate(referencias):
                    pagina.insert_text((100 + indice * 150, 220), referencia, fontsize=12)
            documento.save(planta)
        crear_pdf(detalles, [
            ((20, 30), "TIPOS DE CIMIENTOS"),
            ((50, 70), "C-1"), ((170, 70), "C-2"), ((290, 70), "C-4"),
        ])
        with patch("computos.fundaciones.cimientos_corridos._dimensiones_ocr", return_value={}), \
             patch("computos.fundaciones.cimientos_corridos._medir_longitudes", return_value=({"C-1": 8.0, "C-2": 12.5, "C-4": 6.0}, {"paginas": []})), \
             patch("computos.fundaciones.cimientos_corridos.diagnostico_ocr", return_value={"listo": False}):
            propuesta = preparar_revision_cimientos_corridos(
                planta, detalles,
                fuentes_planta=[
                    {"archivo": "primera.pdf", "sha256": "a" * 64, "pagina": 1},
                    {"archivo": "segunda.pdf", "sha256": "b" * 64, "pagina": 1},
                ],
                fuentes_detalles=[{"archivo": "secciones.pdf", "sha256": "c" * 64, "pagina": 1}],
                identidad_fuentes={"sha256": "d" * 64, "fuentes": []},
            )
        por_ref = {item["referencia_propuesta"]: item for item in propuesta["elementos"]}
        self.assertEqual(set(por_ref), {"C-1", "C-2", "C-4"})
        self.assertEqual(propuesta["tipos_solo_detalle"], [])
        self.assertEqual(por_ref["C-1"]["fuente"]["archivo"], "segunda.pdf")
        self.assertEqual(por_ref["C-4"]["pagina_motor"], 2)
        self.assertEqual(por_ref["C-4"]["longitud_m_propuesta"], 6.0)

    def test_cimiento_corrido_calcula_volumen_aunque_material_quede_pendiente(self):
        propuesta = {
            "version": 3,
            "tipo": "cimientos_corridos_geometria_distribuida",
            "identidad_fuentes": "a" * 64,
            "elementos": [
                {"id": "cimiento-corrido-C-2"},
                {"id": "cimiento-corrido-C-3"},
            ],
        }
        decision = {
            "version": 3,
            "identidad_fuentes": "a" * 64,
            "revisor": "Ingeniera de prueba",
            "motivo": "Secciones y recorridos comprobados sobre la planta.",
            "elementos": [
                {
                    "id": "cimiento-corrido-C-2",
                    "incluir": True,
                    "referencia": "C-2",
                    "ancho_superior_m": 0.30,
                    "ancho_base_m": 0.60,
                    "altura_m": 0.40,
                    "longitud_m": 91.32,
                    "material": None,
                },
                {
                    "id": "cimiento-corrido-C-3",
                    "incluir": True,
                    "referencia": "C-3",
                    "ancho_superior_m": 0.30,
                    "ancho_base_m": 0.80,
                    "altura_m": 0.40,
                    "longitud_m": 96.59,
                    "material": None,
                },
            ],
        }
        resultado = calcular_cimientos_corridos_revisados(propuesta, decision)
        self.assertAlmostEqual(
            resultado["longitud_total_cimientos_corridos_m"], 187.91
        )
        self.assertAlmostEqual(
            resultado["volumen_cimientos_corridos_m3"], 37.6874
        )
        self.assertEqual(resultado["volumen_hormigon_m3"], 0)
        self.assertTrue(resultado["computos_disponibles"])
        self.assertEqual(
            resultado["alertas_analisis"][0]["categoria"],
            "material_no_confirmado",
        )

    def test_mencion_incidental_de_losa_no_bloquea_zapatas(self):
        ruta = self.raiz / "lamina-mixta.pdf"
        crear_pdf(
            ruta,
            [
                ((30, 30), "PLANTA DE CIMENTACION"),
                ((30, 70), "DETALLE TIPICO DE ZAPATA"),
                ((30, 110), "Z1 1.20 X 1.50"),
                ((30, 150), "Y LOSA DE CIMENTACION, COLUMNA O VIGA"),
                ((30, 190), "DETALLE DE COLUMNAS"),
            ],
        )
        enrutamiento = enrutar_documentos(
            {"unico": ruta}, clasificador=SinModelo()
        )
        self.assertIn("zapatas_aisladas", enrutamiento.tipologias)
        self.assertNotIn("losa_cimentacion", enrutamiento.tipologias)

    def test_conexion_viga_zapata_no_es_cuadro_de_fundaciones(self):
        ruta = self.raiz / "conexion.pdf"
        crear_pdf(
            ruta,
            [
                ((30, 30), "ESTRUCTURAS - CORTES DE VIGAS DE CIMENTACION"),
                ((30, 70), "DETALLE: CONEXION VIGA - ZAPATA EJES 4"),
            ],
        )
        enrutamiento = enrutar_documentos(
            {"unico": ruta}, clasificador=SinModelo()
        )
        self.assertNotIn("detalles", enrutamiento.fuentes_por_rol)


if __name__ == "__main__":
    unittest.main()

