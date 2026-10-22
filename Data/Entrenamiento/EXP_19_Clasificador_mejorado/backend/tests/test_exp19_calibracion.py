"""Pruebas de las reglas de selección y calibración de EXP19."""

import unittest

import numpy as np

from experimentos.entrenar_exp19 import _calibrate_per_label, _select_candidate


class Exp19CalibracionTests(unittest.TestCase):
    def test_no_calibra_etiqueta_sin_soporte_minimo(self):
        y_true = np.array(
            [[1, 0], [1, 0], [1, 0], [1, 1], [1, 0]]
        )
        scores = np.array(
            [[0.8, 0.1], [0.7, 0.2], [0.6, 0.3], [0.5, 0.4], [0.4, 0.2]]
        )

        thresholds, supports, calibrated = _calibrate_per_label(
            y_true,
            scores,
            global_threshold=0.5,
            score_kind="probability",
            minimum_support=5,
            shrinkage=10,
        )

        self.assertEqual(supports.tolist(), [5, 1])
        self.assertTrue(calibrated[0])
        self.assertFalse(calibrated[1])
        self.assertEqual(thresholds[1], 0.5)

    def test_seleccion_prioriza_macro_dentro_de_tolerancia_micro(self):
        base = {
            "split": "validation",
            "micro_precision": 0.7,
            "cardinalidad_predicha": 1.0,
            "cardinalidad_real": 1.0,
        }
        rows = [
            {
                **base,
                "model_id": "micro",
                "threshold_strategy": "global",
                "micro_f1": 0.80,
                "macro_f1_etiquetas_presentes": 0.40,
            },
            {
                **base,
                "model_id": "balanceado",
                "threshold_strategy": "por_etiqueta",
                "micro_f1": 0.785,
                "macro_f1_etiquetas_presentes": 0.55,
            },
            {
                **base,
                "model_id": "fuera",
                "threshold_strategy": "por_etiqueta",
                "micro_f1": 0.77,
                "macro_f1_etiquetas_presentes": 0.90,
            },
        ]

        selected = _select_candidate(rows, tolerance=0.02)

        self.assertEqual(selected["model_id"], "balanceado")

    def test_seleccion_rechaza_resultados_de_test(self):
        with self.assertRaisesRegex(ValueError, "VALIDATION"):
            _select_candidate([{"split": "test", "micro_f1": 1.0}])


if __name__ == "__main__":
    unittest.main()
