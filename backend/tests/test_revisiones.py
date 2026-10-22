"""Pruebas del flujo de revisión profesional de secciones de vigas."""

from copy import deepcopy
import unittest

from computos.api.revisiones import (
    aplicar_revision_ingeniero,
    aplicar_revision_seccion_viga,
)


class RevisionesIngenieroTests(unittest.TestCase):
    def setUp(self):
        self.alerta_id = (
            "vigas-acero-VR2-12-inconsistencia_seccion"
        )
        self.resultado = {
            "vigas_riostra_computo_detalle": [
                {
                    "tramo_id": "VR2-12",
                    "referencia": "VR2",
                    "texto_original": "V.R. 2 (40 X 40)",
                    "estado": "computado",
                    "estado_acero": (
                        "seccion_no_coincide_con_detalle"
                    ),
                    "ancho_m": 0.40,
                    "alto_m": 0.40,
                    "longitud_m": 4.496,
                    "longitud_entre_ejes_m": 4.496,
                    "longitud_libre_entre_caras_m": 4.047,
                    "volumen_hormigon_m3": 0.719,
                    "encofrado_laterales_m2": 3.597,
                    "encofrado_fondo_m2": 1.798,
                    "encofrado_total_m2": 3.597,
                    "encofrado_incluye_fondo": False,
                    "armadura_viga": {
                        "referencia": "VR2",
                        "estado": "CORRECTO",
                        "ancho_m": 0.40,
                        "alto_m": 0.50,
                        "armadura_longitudinal": [
                            {
                                "cantidad": 4,
                                "diametro_pulgadas": "3/4",
                                "peso_unitario_kg_m": 2.238,
                            }
                        ],
                        "estribo": {
                            "diametro_pulgadas": "3/8",
                            "separacion_m": 0.20,
                            "longitud_unidad_m": 1.40,
                            "peso_unitario_kg_m": 0.560,
                        },
                    },
                    "acero_por_diametro": [],
                }
            ],
            "alertas_analisis": [
                {
                    "id": self.alerta_id,
                    "familia": "vigas",
                    "categoria": "inconsistencia_seccion",
                    "elemento_id": "VR2-12",
                    "severidad": "advertencia",
                    "excluido_del_computo": True,
                }
            ],
            "alertas_resueltas": [],
            "validacion_acero_vigas_riostra": {
                "tolerancia_seccion_m": 0.025,
                "longitud_adicional_por_extremo_m": 0.0,
                "tramos_geometria_computada": 1,
                "tramos_acero_computado": 0,
                "tramos_acero_pendiente": 1,
                "resultado_completo": False,
            },
            "validacion_computo_vigas_riostra": {
                "tramos_computados": 1,
                "resultado_completo": True,
                "acero_resultado_completo": False,
            },
            "computos_por_elemento": {
                "vigas_riostra": {
                    "estado": "parcial",
                    "hormigon": {
                        "valor": 0.719,
                        "estado": "calculado",
                    },
                    "acero": {
                        "valor": None,
                        "estado": "parcial",
                    },
                    "encofrado": {
                        "valor": 3.597,
                        "estado": "calculado",
                    },
                }
            },
        }

    def test_valida_recalcula_y_conserva_auditoria(self):
        original = deepcopy(self.resultado)

        actualizado = aplicar_revision_seccion_viga(
            self.resultado,
            alerta_id=self.alerta_id,
            tramo_id="VR2-12",
            fuente_seleccionada="detalle",
            motivo=(
                "Se validó contra el detalle estructural vigente."
            ),
            revisor="Ing. Responsable",
            confirmar_armadura_detalle=True,
        )

        tramo = actualizado[
            "vigas_riostra_computo_detalle"
        ][0]

        self.assertEqual(self.resultado, original)
        self.assertEqual(tramo["ancho_m"], 0.40)
        self.assertEqual(tramo["alto_m"], 0.50)
        self.assertEqual(
            tramo["volumen_hormigon_m3"],
            0.899,
        )
        self.assertEqual(
            tramo["encofrado_total_m2"],
            4.496,
        )
        self.assertEqual(
            tramo["estado_acero"],
            "computado",
        )
        self.assertGreater(
            tramo["peso_acero_total_kg"],
            0,
        )
        self.assertEqual(
            tramo["armadura_viga"]["alto_m"],
            0.50,
        )
        self.assertTrue(
            tramo["seccion_validada_manualmente"]
        )
        self.assertEqual(
            actualizado["alertas_analisis"],
            [],
        )
        self.assertEqual(
            len(actualizado["alertas_resueltas"]),
            1,
        )
        self.assertEqual(
            len(actualizado["revisiones_ingeniero"]),
            1,
        )
        self.assertTrue(
            actualizado[
                "validacion_acero_vigas_riostra"
            ]["resultado_completo"]
        )
        self.assertEqual(
            actualizado["resumen_alertas"]["total"],
            0,
        )

    def test_impide_resolver_dos_veces_la_misma_alerta(self):
        actualizado = aplicar_revision_seccion_viga(
            self.resultado,
            alerta_id=self.alerta_id,
            tramo_id="VR2-12",
            fuente_seleccionada="planta",
            motivo="Se verificó la sección indicada en planta.",
            revisor="Ing. Responsable",
            confirmar_armadura_detalle=True,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "ya fue resuelta",
        ):
            aplicar_revision_seccion_viga(
                actualizado,
                alerta_id=self.alerta_id,
                tramo_id="VR2-12",
                fuente_seleccionada="planta",
                motivo=(
                    "Se intenta repetir la misma revisión."
                ),
                revisor="Ing. Responsable",
                confirmar_armadura_detalle=True,
            )

    def test_exige_confirmacion_explicita_de_la_armadura(self):
        with self.assertRaisesRegex(
            ValueError,
            "confirmarse explícitamente",
        ):
            aplicar_revision_seccion_viga(
                self.resultado,
                alerta_id=self.alerta_id,
                tramo_id="VR2-12",
                fuente_seleccionada="manual",
                ancho_m=0.40,
                alto_m=0.45,
                motivo=(
                    "Se adoptó la sección informada por el proyectista."
                ),
                revisor="Ing. Responsable",
                confirmar_armadura_detalle=False,
            )

    def test_valida_alturas_de_columnas_y_recalcula(self):
        alerta_id = (
            "columnas-alturas-reales-no-disponibles"
        )
        resultado = {
            "columnas_fundaciones": [
                {
                    "fundacion_id": "F1-01",
                    "referencia_columna": "C1",
                    "pagina": 1,
                    "ancho_m": 0.40,
                    "largo_m": 0.50,
                    "posicion_rotulo_columna_pdf": {
                        "x": 10,
                        "y": 20,
                    },
                },
                {
                    "fundacion_id": "F1-02",
                    "referencia_columna": "C1",
                    "pagina": 1,
                    "ancho_m": 0.40,
                    "largo_m": 0.50,
                    "posicion_rotulo_columna_pdf": {
                        "x": 30,
                        "y": 20,
                    },
                },
            ],
            "columnas_vinculadas_por_viga": [],
            "validacion_columnas": {
                "altura_real_disponible": False,
            },
            "computos_por_elemento": {
                "columnas": {
                    "acero": {
                        "valor": None,
                        "estado": "pendiente_armadura",
                    }
                }
            },
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "columnas",
                    "categoria": (
                        "alturas_reales_no_disponibles"
                    ),
                    "excluido_del_computo": True,
                }
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="validar_alturas",
            motivo=(
                "Alturas verificadas contra los cortes estructurales."
            ),
            revisor="Ing. Responsable",
            valores={
                "alturas_por_referencia": {
                    "C1": "3,0",
                }
            },
        )

        self.assertEqual(
            actualizado["hormigon_columnas_m3"],
            1.2,
        )
        self.assertEqual(
            actualizado["encofrado_columnas_m2"],
            10.8,
        )
        self.assertTrue(
            actualizado["validacion_columnas"][
                "altura_real_disponible"
            ]
        )
        self.assertEqual(
            actualizado["alertas_analisis"],
            [],
        )
        self.assertEqual(
            len(actualizado["columnas_computo_detalle"]),
            2,
        )

    def test_valida_altura_por_tramo_de_portico(self):
        alerta_id = "columnas-alturas-reales-no-disponibles"
        resultado = {
            "columnas_porticos_segmentos": [
                {
                    "tramo_id": "COL-A-1-NPB-N1",
                    "referencia": "C1",
                    "eje_global": "A-1",
                    "nivel_inferior": "NPB",
                    "nivel_superior": "N1",
                    "altura_detectada_m": 4.0,
                    "ancho_m": 0.40,
                    "largo_m": 0.50,
                    "apto_revision_altura": True,
                    "paginas": [11, 12],
                }
            ],
            "validacion_columnas": {"altura_real_disponible": False},
            "computos_por_elemento": {
                "columnas": {
                    "acero": {"valor": None, "estado": "pendiente_armadura"}
                }
            },
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "columnas",
                    "categoria": "alturas_reales_no_disponibles",
                    "excluido_del_computo": True,
                }
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="validar_alturas",
            motivo="Cota revisada contra ambos pórticos estructurales.",
            revisor="Ing. Responsable",
            valores={
                "alturas_por_tramo": {"COL-A-1-NPB-N1": "4,00"}
            },
        )

        self.assertEqual(actualizado["hormigon_columnas_m3"], 0.8)
        self.assertEqual(actualizado["encofrado_columnas_m2"], 7.2)
        detalle = actualizado["columnas_computo_detalle"][0]
        self.assertEqual(detalle["eje_global"], "A-1")
        self.assertEqual(detalle["altura_m"], 4.0)
        self.assertTrue(
            actualizado["validacion_columnas"][
                "alturas_obtenidas_de_porticos"
            ]
        )

    def test_resuelve_conflicto_de_porticos_antes_de_alturas(self):
        alerta_id = "columnas-portico-conflicto-COL-A-1"
        resultado = {
            "columnas_porticos_segmentos": [
                {
                    "tramo_id": "COL-A-1",
                    "eje_global": "A-1",
                    "nivel_inferior": "NPB",
                    "nivel_superior": "N1",
                    "referencia": None,
                    "referencias_candidatas": ["C1", "C2"],
                    "alturas_candidatas_m": [4.0],
                    "estado_extraccion": "conflicto_entre_vistas",
                    "apto_revision_altura": False,
                }
            ],
            "secciones_columnas": [
                {
                    "referencia": "C2",
                    "dimension_1_m": 0.30,
                    "dimension_2_m": 0.40,
                    "estado": "CORRECTO",
                }
            ],
            "validacion_columnas": {
                "tramos_porticos_con_conflicto": 1,
                "tramos_porticos_listos_revision": 0,
            },
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "columnas",
                    "categoria": "inconsistencia_portico_columna",
                    "elemento_id": "COL-A-1",
                    "excluido_del_computo": True,
                }
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="resolver_inconsistencia_portico",
            motivo="Se verificó la intersección A-1 en los dos pórticos.",
            revisor="Ing. Responsable",
            valores={
                "referencia_columna": "C2",
                "altura_m": 4.0,
                "ancho_m": 0.30,
                "largo_m": 0.40,
            },
            confirmaciones={"confirmar_conflicto_portico": True},
        )

        tramo = actualizado["columnas_porticos_segmentos"][0]
        self.assertEqual(tramo["referencia"], "C2")
        self.assertTrue(tramo["apto_revision_altura"])
        self.assertEqual(
            actualizado["validacion_columnas"][
                "tramos_porticos_con_conflicto"
            ],
            0,
        )
        self.assertEqual(actualizado["alertas_analisis"], [])

    def test_valida_seccion_para_todos_los_tramos_de_una_referencia(self):
        alerta_id = "columnas-portico-seccion-C3"
        resultado = {
            "columnas_porticos_segmentos": [
                {
                    "tramo_id": "COL-F-2-NS2-NS1",
                    "referencia": "C3",
                    "altura_detectada_m": 3.5,
                    "estado_extraccion": "detectado_confirmable",
                    "estado_seccion": "sin_seccion",
                    "apto_revision_altura": False,
                },
                {
                    "tramo_id": "COL-F-2-NS1-NPB",
                    "referencia": "C3",
                    "altura_detectada_m": 3.7,
                    "estado_extraccion": "detectado_confirmable",
                    "estado_seccion": "sin_seccion",
                    "apto_revision_altura": False,
                },
            ],
            "secciones_columnas": [],
            "validacion_columnas": {
                "tramos_porticos_listos_revision": 0,
            },
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "columnas",
                    "categoria": "seccion_columna_portico_pendiente",
                    "elemento_id": "C3",
                    "referencia": "C3",
                    "excluido_del_computo": True,
                }
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="validar_seccion_portico",
            motivo="Sección verificada contra el detalle estructural de C3.",
            revisor="Ing. Responsable",
            valores={
                "referencia_columna": "C3",
                "ancho_m": 0.50,
                "largo_m": 0.60,
            },
            confirmaciones={"confirmar_seccion_portico": True},
        )

        self.assertTrue(
            all(
                tramo["apto_revision_altura"]
                for tramo in actualizado["columnas_porticos_segmentos"]
            )
        )
        self.assertEqual(
            actualizado["validacion_columnas"][
                "tramos_porticos_listos_revision"
            ],
            2,
        )
        self.assertEqual(actualizado["alertas_analisis"], [])

    def test_confirma_armaduras_de_columnas_y_calcula_acero(self):
        alerta_id = "columnas-armadura-no-disponible"
        resultado = {
            "columnas_fundaciones": [
                {
                    "fundacion_id": "F1-01",
                    "referencia_columna": "C1",
                    "altura_m": 3.0,
                }
            ],
            "columnas_vinculadas_por_viga": [],
            "columnas_computo_detalle": [
                {
                    "columna_id": "C1-01",
                    "fundacion_id": "F1-01",
                    "referencia": "C1",
                    "ancho_m": 0.40,
                    "largo_m": 0.50,
                    "altura_m": 3.0,
                    "volumen_total_m3": 0.60,
                    "encofrado_total_m2": 5.40,
                }
            ],
            "armaduras_columnas": [
                {
                    "referencia": "C1",
                    "estado": "CORRECTO",
                    "grupos_longitudinales": [
                        {
                            "cantidad": 4,
                            "diametro_pulgadas": "1/2",
                        }
                    ],
                    "estribo": {
                        "diametro_pulgadas": "3/8",
                        "separacion_m": 0.20,
                        "longitud_indicada_m": 1.20,
                    },
                }
            ],
            "validacion_columnas": {
                "altura_real_disponible": True,
                "armaduras_columnas_confirmadas": False,
            },
            "estado_computo_columnas": {
                "hormigon": "calculado",
                "acero": "pendiente_armadura",
                "encofrado": "calculado",
            },
            "computos_por_elemento": {
                "columnas": {
                    "cantidad": 1,
                    "estado": "parcial_sin_acero",
                }
            },
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "columnas",
                    "categoria": "armadura_no_disponible",
                    "excluido_del_computo": True,
                }
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="asignar_armadura",
            motivo=(
                "Armaduras verificadas contra los detalles estructurales."
            ),
            revisor="Ing. Responsable",
            valores={
                "referencias_confirmadas": ["C1"],
                "longitud_adicional_por_extremo_m": 0,
            },
            confirmaciones={
                "confirmar_armaduras": True,
            },
        )

        self.assertAlmostEqual(
            actualizado["acero_columnas_kg"],
            22.704,
            places=3,
        )
        self.assertEqual(
            actualizado["columnas_computo_detalle"][0][
                "cantidad_estribos"
            ],
            16,
        )
        self.assertTrue(
            actualizado["validacion_columnas"][
                "armaduras_columnas_confirmadas"
            ]
        )
        self.assertEqual(
            actualizado["estado_computo_columnas"]["acero"],
            "calculado",
        )
        self.assertEqual(
            actualizado["alertas_analisis"],
            [],
        )

    def test_armadura_columnas_exige_alturas_validadas(self):
        alerta_id = "columnas-armadura-no-disponible"
        resultado = {
            "validacion_columnas": {
                "altura_real_disponible": False,
            },
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "columnas",
                    "categoria": "armadura_no_disponible",
                    "excluido_del_computo": True,
                }
            ],
        }

        with self.assertRaisesRegex(
            ValueError,
            "Primero deben validarse las alturas",
        ):
            aplicar_revision_ingeniero(
                resultado,
                alerta_id=alerta_id,
                accion="asignar_armadura",
                motivo=(
                    "Armaduras verificadas contra el plano estructural."
                ),
                revisor="Ing. Responsable",
                valores={
                    "referencias_confirmadas": ["C1"],
                },
                confirmaciones={
                    "confirmar_armaduras": True,
                },
            )

    def test_armadura_columna_confirmada_se_aplica_al_pedestal(self):
        resultado = {
            "columnas_fundaciones": [
                {
                    "fundacion_id": "F1-01",
                    "referencia_columna": "C1",
                    "altura_m": 3.0,
                }
            ],
            "columnas_vinculadas_por_viga": [],
            "columnas_computo_detalle": [
                {
                    "columna_id": "C1-01",
                    "fundacion_id": "F1-01",
                    "referencia": "C1",
                    "ancho_m": 0.40,
                    "largo_m": 0.50,
                    "altura_m": 3.0,
                    "volumen_total_m3": 0.60,
                    "encofrado_total_m2": 5.40,
                }
            ],
            "armaduras_columnas": [
                {
                    "referencia": "C1",
                    "estado": "CORRECTO",
                    "grupos_longitudinales": [
                        {
                            "cantidad": 4,
                            "diametro_pulgadas": "1/2",
                        }
                    ],
                    "estribo": {
                        "diametro_pulgadas": "3/8",
                        "separacion_m": 0.20,
                        "longitud_indicada_m": 1.20,
                    },
                }
            ],
            "validacion_columnas": {
                "altura_real_disponible": True,
                "armaduras_columnas_confirmadas": False,
            },
            "pedestales_computo_detalle": [
                {
                    "referencia_columna": "C1",
                    "cantidad": 2,
                    "altura_real_m": 1.0,
                    "dimension_pedestal_1_m": 0.60,
                    "dimension_pedestal_2_m": 0.70,
                }
            ],
            "validacion_pedestales": {
                "altura_real_disponible": True,
            },
            "estado_computo_columnas": {
                "hormigon": "calculado",
                "acero": "pendiente_armadura",
                "encofrado": "calculado",
            },
            "computos_por_elemento": {
                "columnas": {
                    "cantidad": 1,
                    "estado": "parcial_sin_acero",
                },
                "pedestales": {
                    "cantidad": 2,
                    "estado": "parcial_sin_acero",
                    "acero": {
                        "valor": None,
                        "unidad": "kg",
                        "estado": "pendiente_armadura",
                    },
                },
            },
            "alertas_analisis": [
                {
                    "id": "columnas-armadura-no-disponible",
                    "familia": "columnas",
                    "categoria": "armadura_no_disponible",
                    "excluido_del_computo": True,
                },
                {
                    "id": "pedestales-armadura-no-disponible",
                    "familia": "pedestales",
                    "categoria": "armadura_no_disponible",
                    "excluido_del_computo": True,
                },
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id="columnas-armadura-no-disponible",
            accion="asignar_armadura",
            motivo="Armadura verificada en el detalle estructural.",
            revisor="Ing. Responsable",
            valores={
                "referencias_confirmadas": ["C1"],
                "longitud_adicional_por_extremo_m": 0,
            },
            confirmaciones={
                "confirmar_armaduras": True,
            },
        )

        self.assertAlmostEqual(
            actualizado["acero_pedestales_kg"],
            16.032,
            places=3,
        )
        self.assertEqual(
            actualizado["pedestales_computo_detalle"][0][
                "origen_armadura_pedestal"
            ],
            "heredada_de_columna",
        )
        self.assertTrue(
            actualizado["validacion_pedestales"][
                "armaduras_pedestales_confirmadas"
            ]
        )
        self.assertFalse(
            any(
                alerta.get("id")
                == "pedestales-armadura-no-disponible"
                for alerta in actualizado["alertas_analisis"]
            )
        )

    def test_valida_alturas_de_pedestales(self):
        alerta_id = (
            "pedestales-alturas-reales-no-disponibles"
        )
        resultado = {
            "pedestales_computo_detalle": [
                {
                    "referencia_columna": "C1",
                    "cantidad": 2,
                    "dimension_pedestal_1_m": 0.60,
                    "dimension_pedestal_2_m": 0.70,
                    "altura_minima_m": 0.50,
                    "volumen_unitario_m3": 0.21,
                    "volumen_total_m3": 0.42,
                    "encofrado_unitario_m2": 1.30,
                    "encofrado_total_m2": 2.60,
                }
            ],
            "validacion_pedestales": {
                "altura_real_disponible": False,
                "resultado_preliminar": True,
            },
            "computos_por_elemento": {
                "pedestales": {
                    "acero": {
                        "valor": None,
                        "estado": "pendiente_armadura",
                    }
                }
            },
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "pedestales",
                    "categoria": (
                        "alturas_reales_no_disponibles"
                    ),
                    "excluido_del_computo": False,
                }
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="validar_alturas",
            motivo=(
                "Altura real verificada contra el corte estructural."
            ),
            revisor="Ing. Responsable",
            valores={
                "alturas_por_referencia": {
                    "C1": 1.0,
                }
            },
        )

        self.assertEqual(
            actualizado["hormigon_pedestales_m3"],
            0.84,
        )
        self.assertEqual(
            actualizado["encofrado_pedestales_m2"],
            5.2,
        )
        self.assertFalse(
            actualizado["validacion_pedestales"][
                "resultado_preliminar"
            ]
        )
        self.assertEqual(
            actualizado["alertas_analisis"],
            [],
        )

    def test_altura_pedestal_recalcula_acero_heredado(self):
        resultado = {
            "armaduras_columnas": [
                {
                    "referencia": "C1",
                    "estado": "CORRECTO",
                    "grupos_longitudinales": [
                        {
                            "cantidad": 4,
                            "diametro_pulgadas": "1/2",
                        }
                    ],
                    "estribo": {
                        "diametro_pulgadas": "3/8",
                        "separacion_m": 0.20,
                        "longitud_indicada_m": 1.20,
                    },
                }
            ],
            "validacion_columnas": {
                "armaduras_columnas_confirmadas": True,
            },
            "pedestales_computo_detalle": [
                {
                    "referencia_columna": "C1",
                    "cantidad": 1,
                    "dimension_pedestal_1_m": 0.60,
                    "dimension_pedestal_2_m": 0.70,
                    "altura_minima_m": 0.50,
                    "volumen_unitario_m3": 0.21,
                    "volumen_total_m3": 0.21,
                    "encofrado_unitario_m2": 1.30,
                    "encofrado_total_m2": 1.30,
                }
            ],
            "validacion_pedestales": {
                "altura_real_disponible": False,
                "resultado_preliminar": True,
            },
            "computos_por_elemento": {
                "pedestales": {
                    "cantidad": 1,
                    "estado": "preliminar",
                    "acero": {
                        "valor": None,
                        "estado": "pendiente_armadura",
                    },
                }
            },
            "alertas_analisis": [
                {
                    "id": "pedestales-alturas-reales-no-disponibles",
                    "familia": "pedestales",
                    "categoria": "alturas_reales_no_disponibles",
                    "excluido_del_computo": False,
                },
                {
                    "id": "pedestales-armadura-no-disponible",
                    "familia": "pedestales",
                    "categoria": "armadura_no_disponible",
                    "excluido_del_computo": True,
                },
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id="pedestales-alturas-reales-no-disponibles",
            accion="validar_alturas",
            motivo="Altura revisada contra el corte de fundaciones.",
            revisor="Ing. Responsable",
            valores={
                "alturas_por_referencia": {
                    "C1": 1.0,
                }
            },
        )

        self.assertAlmostEqual(
            actualizado["acero_pedestales_kg"],
            8.016,
            places=3,
        )
        self.assertFalse(
            actualizado["validacion_pedestales"][
                "acero_resultado_preliminar"
            ]
        )
        self.assertEqual(
            actualizado["computos_por_elemento"]["pedestales"][
                "acero"
            ]["estado"],
            "calculado",
        )
        self.assertEqual(
            actualizado["alertas_analisis"],
            [],
        )

    def test_observacion_no_cierra_elemento_excluido(self):
        alerta_id = "fundaciones-ejemplo-excluido"
        resultado = {
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "fundaciones",
                    "categoria": "dato_faltante",
                    "excluido_del_computo": True,
                }
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="registrar_observacion",
            motivo=(
                "Se solicitó la información faltante al proyectista."
            ),
            revisor="Ing. Responsable",
        )

        self.assertEqual(
            len(actualizado["alertas_analisis"]),
            1,
        )
        self.assertEqual(
            actualizado["alertas_analisis"][0][
                "estado_revision"
            ],
            "revisada_sin_resolver",
        )
        self.assertFalse(
            actualizado["revisiones_ingeniero"][0][
                "resuelve_alerta"
            ]
        )

    def test_confirmacion_documentada_cierra_advertencia(self):
        alerta_id = "fundaciones-lectura-1"
        resultado = {
            "alertas_analisis": [
                {
                    "id": alerta_id,
                    "familia": "fundaciones",
                    "categoria": "advertencia_lectura",
                    "excluido_del_computo": False,
                }
            ],
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="confirmar_revision",
            motivo=(
                "La lectura fue contrastada con el plano firmado."
            ),
            revisor="Ing. Responsable",
        )

        self.assertEqual(
            actualizado["alertas_analisis"],
            [],
        )
        self.assertEqual(
            len(actualizado["alertas_resueltas"]),
            1,
        )

    def test_confirma_asociacion_de_columna(self):
        alerta_id = (
            "columnas-relacion-F10-01-C5-"
            "pendiente_clasificacion_estructural"
        )
        alerta = {
            "id": alerta_id,
            "familia": "columnas",
            "categoria": (
                "pendiente_clasificacion_estructural"
            ),
            "referencia": "C5",
            "elemento_id": "C5",
            "excluido_del_computo": True,
            "evidencia": [
                {
                    "etiqueta": "Fundación",
                    "valor": "F10-01",
                }
            ],
        }
        relacion = {
            "fundacion_id": "F10-01",
            "referencia_columna": "C5",
            "ancho_m": 0.45,
            "largo_m": 0.50,
            "tipo_asociacion": (
                "adicional_por_proximidad"
            ),
            "pagina": 1,
            "posicion_rotulo_columna_pdf": {
                "x": 1,
                "y": 2,
            },
        }
        resultado = {
            "alertas_analisis": [alerta],
            "relaciones_columnas_fundaciones": [
                deepcopy(relacion)
            ],
            "columnas_pendientes_clasificacion": [
                deepcopy(relacion)
            ],
            "columnas_fundaciones": [],
            "columnas_vinculadas_por_viga": [],
            "validacion_columnas": {},
        }

        actualizado = aplicar_revision_ingeniero(
            resultado,
            alerta_id=alerta_id,
            accion="confirmar_asociacion",
            motivo=(
                "La relación fue validada contra el eje estructural."
            ),
            revisor="Ing. Responsable",
            valores={
                "referencia_columna": "C5",
                "ancho_m": 0.45,
                "largo_m": 0.50,
                "tipo_apoyo": "vinculada_por_viga",
            },
        )

        self.assertEqual(
            len(
                actualizado[
                    "columnas_vinculadas_por_viga"
                ]
            ),
            1,
        )
        self.assertEqual(
            actualizado[
                "columnas_pendientes_clasificacion"
            ],
            [],
        )
        self.assertEqual(
            actualizado["alertas_analisis"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
