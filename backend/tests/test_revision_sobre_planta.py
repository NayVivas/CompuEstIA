"""La corrección profesional conserva el origen y no inventa geometría."""

import unittest

from computos.fundaciones.geometria_distribuida import calcular_geometria_revisada
from computos.fundaciones.cimientos_corridos import calcular_cimientos_corridos_revisados


UUID = "12345678-1234-1234-1234-123456789012"
FUENTE = {"archivo": "planta.pdf", "sha256": "a" * 64, "pagina": 2}
PAGINA = {"pagina_motor": 1, "ancho_visual_pt": 600, "alto_visual_pt": 400, "fuente": FUENTE}


class RevisionSobrePlantaTests(unittest.TestCase):
    def test_zapata_omitida_y_reubicada_generan_ocurrencias_reales(self):
        propuesta = {
            "identidad_fuentes": "b" * 64, "paginas": [PAGINA],
            "elementos": [{
                "id": "Z1-001-p001", "pagina_motor": 1, "centro_visual": {"x": 100, "y": 100},
                "referencia_propuesta": "Z1", "caja_visual": {"x0": 90, "y0": 90, "x1": 110, "y1": 110},
                "fuente": FUENTE,
            }],
        }
        decision = {
            "identidad_fuentes": propuesta["identidad_fuentes"],
            "revisor": "Ingeniera civil", "motivo": "Se revisaron cotas y ubicaciones sobre la planta.",
            "elementos": [
                {"id": "Z1-001-p001", "incluir": True, "referencia": "Z1", "pagina_motor": 1,
                 "centro_visual": {"x": 120, "y": 110}, "x_m": 1, "y_m": 1, "h_m": .5},
                {"id": f"manual-{UUID}", "incluir": True, "referencia": "Z2", "pagina_motor": 1,
                 "centro_visual": {"x": 300, "y": 220}, "x_m": 2, "y_m": 2, "h_m": .4},
            ],
        }
        resultado = calcular_geometria_revisada(propuesta, decision)
        self.assertEqual(resultado["cantidad_fundaciones"], 2)
        self.assertEqual(resultado["volumen_hormigon_m3"], 2.1)
        self.assertEqual(resultado["encofrado_zapatas_m2"], 5.2)
        self.assertEqual([r["posicion"] for r in resultado["fundaciones_planta"]],
                         [{"x": 120, "y": 110}, {"x": 300, "y": 220}])
        self.assertEqual(resultado["fundaciones_planta"][1]["fuente"], FUENTE)
        self.assertEqual(resultado["fundaciones_planta"][1]["origen_ubicacion"], "manual")

        decision["elementos"][1]["centro_visual"]["x"] = 900
        with self.assertRaisesRegex(ValueError, "fuera de la planta"):
            calcular_geometria_revisada(propuesta, decision)

    def test_cimientos_confirma_tramo_y_rechaza_longitud_que_no_coincide(self):
        candidato = {
            "id": "tramo-p1-1", "referencia": "C-2", "pagina_motor": 1,
            "inicio": {"x": 100, "y": 200}, "fin": {"x": 200, "y": 200},
            "longitud_m": 10, "puntos_por_metro": 10, "fuente": FUENTE,
        }
        propuesta = {
            "version": 4, "identidad_fuentes": "c" * 64,
            "paginas": [PAGINA], "diagnostico_medicion": {"paginas": [{"pagina_motor": 1,
                "calibracion": {"estado": "calibrado", "puntos_por_metro": 10}}]},
            "elementos": [{"id": "cimiento-corrido-C-2", "origen_referencia": "planta",
                           "tramos_propuestos": [candidato]}],
        }
        item = {
            "id": "cimiento-corrido-C-2", "incluir": True, "referencia": "C-2",
            "ancho_superior_m": .3, "ancho_base_m": .7, "altura_m": .4,
            "longitud_m": 10, "tramos": [{"id": "tramo-p1-1"}], "material": "hormigon_armado",
        }
        decision = {"version": 4, "identidad_fuentes": propuesta["identidad_fuentes"],
                    "revisor": "Ingeniera civil", "motivo": "Recorrido y sección revisados en planta.",
                    "elementos": [item]}
        resultado = calcular_cimientos_corridos_revisados(propuesta, decision)
        self.assertEqual(resultado["volumen_cimientos_corridos_m3"], 2)
        self.assertEqual(len(resultado["cimientos_corridos_tramos"]), 1)
        self.assertEqual(resultado["cimientos_corridos_tramos"][0]["fuente"], FUENTE)

        item["longitud_m"] = 11
        with self.assertRaisesRegex(ValueError, "no coincide"):
            calcular_cimientos_corridos_revisados(propuesta, decision)

        item["longitud_m"] = 15
        item["tramos"].append({"id": f"manual-{UUID}", "pagina_motor": 1,
                               "inicio": {"x": 200, "y": 200}, "fin": {"x": 250, "y": 200}})
        resultado = calcular_cimientos_corridos_revisados(propuesta, decision)
        self.assertEqual(resultado["volumen_cimientos_corridos_m3"], 3)
        self.assertEqual(resultado["cimientos_corridos_tramos"][1]["longitud_m"], 5)

        item["tramos"][1]["fin"]["x"] = 700
        with self.assertRaisesRegex(ValueError, "fuera de la planta"):
            calcular_cimientos_corridos_revisados(propuesta, decision)


if __name__ == "__main__":
    unittest.main()
