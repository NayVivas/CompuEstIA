from pathlib import Path
import importlib
import unittest

from computos.configuracion.parametros import BASE_DIR, PDF_DIR
from computos.configuracion.proyecto import cargar_configuracion_proyecto


class EstructuraProyectoTests(unittest.TestCase):
    def test_rutas_se_resuelven_desde_la_raiz_del_proyecto(self):
        raiz_esperada = Path(__file__).resolve().parents[1]

        self.assertEqual(BASE_DIR, raiz_esperada)
        self.assertEqual(PDF_DIR, raiz_esperada / "data" / "pdf")
        self.assertTrue((BASE_DIR / "app.py").is_file())

    def test_paquetes_principales_se_pueden_importar(self):
        modulos = (
            "computos.documentos.analisis",
            "computos.fundaciones.armaduras",
            "computos.columnas.deteccion",
            "computos.vigas.riostra",
            "computos.salida.reportes",
            "computos.flujos.principal",
            "computos.api",
        )

        for modulo in modulos:
            with self.subTest(modulo=modulo):
                self.assertIsNotNone(importlib.import_module(modulo))

    def test_configuracion_incluida_corresponde_a_los_pdf(self):
        configuracion = cargar_configuracion_proyecto(
            BASE_DIR / "configuraciones" / "proyecto_actual.json"
        )

        configuracion.validar_archivos(
            planta=PDF_DIR / "Fundaciones" / "Fundaciones_1.pdf",
            detalles=PDF_DIR / "Fundaciones" / "Fundaciones_2.pdf",
            columnas=PDF_DIR / "Columnas" / "Columnas.pdf",
        )
        self.assertEqual(
            configuracion.correcciones_referencias_cuadro[("F12", 2)],
            "F13",
        )


if __name__ == "__main__":
    unittest.main()
