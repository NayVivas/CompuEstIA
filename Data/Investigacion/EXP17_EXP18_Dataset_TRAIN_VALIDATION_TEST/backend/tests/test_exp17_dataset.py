"""Pruebas de integración del manifiesto EXP17."""

import ast
import json
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from experimentos import preparar_exp17 as exp17


def _taxonomy(name):
    path = Path(__file__).resolve().parents[1] / "computos" / "api" / "exp02_anotador.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError(f"No se encontró {name}.")


class Exp17DatasetTests(unittest.TestCase):
    def test_taxonomia_ampliada(self):
        self.assertIn("vialidad_infraestructura", _taxonomy("DISCIPLINAS"))
        contents = _taxonomy("CONTENIDOS")
        self.assertIn("trazado_vial", contents)
        self.assertIn("perfil_longitudinal_red", contents)
        self.assertIn("puertas_cortafuego", contents)

    def test_fuente_compartida_exp02(self):
        expected = "EXP02::fuente_compartida_proyectos_7_y_9_a_37"
        self.assertEqual(exp17._exp02_group("Proyecto_7"), expected)
        self.assertEqual(exp17._exp02_group("Proyecto_9"), expected)
        self.assertEqual(exp17._exp02_group("Proyecto_37"), expected)
        self.assertNotEqual(exp17._exp02_group("Proyecto_8"), expected)

    def test_split_sin_fuga(self):
        with tempfile.TemporaryDirectory() as temporary:
            summary = exp17.build(output=Path(temporary), attempts=1_000)
            self.assertEqual(summary["registros_utilizables"], 976)
            self.assertEqual(summary["etiquetas_sin_ejemplos_en_train"], [])
            self.assertEqual(summary["archivos_faltantes_por_origen"], {"EXP02": 0, "EXP11": 0, "EXP16": 0})
            records = [json.loads(line) for line in (Path(temporary) / exp17.DATASET_JSONL.name).read_text(encoding="utf-8").splitlines()]
            splits = defaultdict(set)
            for row in records:
                splits[row["grupo_independencia"]].add(row["split"])
            self.assertTrue(all(len(value) == 1 for value in splits.values()))


if __name__ == "__main__":
    unittest.main()
