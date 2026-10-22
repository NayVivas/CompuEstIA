"""Pruebas de segmentación de vigas entre apoyos para el caso incluido."""

from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from computos.columnas.deteccion import detectar_columnas
from computos.configuracion.parametros import PDF_DIR
from computos.documentos.procesamiento_pdf import extraer_palabras
from computos.vigas.computos import calcular_computos_vigas_riostra
from computos.vigas.riostra import (
    detectar_apoyos_columnas_vectoriales,
    detectar_vigas_riostra,
    eliminar_rotulos_duplicados,
    reconstruir_tramos_vigas_entre_apoyos,
)


class TramosVigasRiostraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ruta_planta = (
            PDF_DIR
            / "Fundaciones"
            / "Fundaciones_1.pdf"
        )
        if not cls.ruta_planta.is_file():
            raise unittest.SkipTest("Falta el PDF externo de regresión de vigas.")
        cls.palabras = extraer_palabras(
            cls.ruta_planta
        )
        cls.rotulos_columnas = detectar_columnas(
            cls.palabras
        )
        rotulos_vigas = detectar_vigas_riostra(
            cls.palabras
        )
        (
            cls.rotulos_vigas,
            cls.rotulos_duplicados,
        ) = eliminar_rotulos_duplicados(
            rotulos_vigas
        )

    def test_localiza_el_centro_vectorial_de_los_apoyos(self):
        resultado = detectar_apoyos_columnas_vectoriales(
            self.ruta_planta,
            self.rotulos_columnas,
        )

        self.assertEqual(
            len(resultado["apoyos"]),
            62,
        )
        self.assertEqual(
            resultado["diagnostico"][
                "rotulos_sin_simbolo_vectorial"
            ],
            0,
        )
        self.assertEqual(
            len(
                {
                    apoyo["apoyo_id"]
                    for apoyo in resultado["apoyos"]
                }
            ),
            62,
        )

    def test_reconstruye_un_tramo_por_par_de_apoyos(self):
        apoyos = detectar_apoyos_columnas_vectoriales(
            self.ruta_planta,
            self.rotulos_columnas,
        )["apoyos"]
        resultado = reconstruir_tramos_vigas_entre_apoyos(
            self.ruta_planta,
            apoyos,
            self.rotulos_vigas,
        )
        conteo = Counter(
            tramo["referencia"]
            for tramo in resultado["tramos"]
        )

        self.assertEqual(len(resultado["tramos"]), 94)
        self.assertEqual(
            conteo,
            Counter(
                {
                    "VR1": 30,
                    "VR2": 16,
                    "VR3": 5,
                    "VR4": 43,
                }
            ),
        )
        self.assertEqual(
            resultado["rotulos_sin_tramo"],
            [],
        )

        pares = {
            frozenset(
                (
                    tramo["apoyo_inicial_id"],
                    tramo["apoyo_final_id"],
                )
            )
            for tramo in resultado["tramos"]
        }
        self.assertEqual(len(pares), 94)

    def test_calcula_longitud_entre_ejes_y_longitud_libre(self):
        resultado = calcular_computos_vigas_riostra(
            ruta_planta=self.ruta_planta,
            palabras_planta=self.palabras,
            ejes_vigas=[],
            rotulos_vigas=self.rotulos_vigas,
            rotulos_columnas=self.rotulos_columnas,
            criterio_longitud="entre_ejes",
        )

        validacion = resultado[
            "validacion_computo_vigas_riostra"
        ]
        self.assertTrue(validacion["resultado_completo"])
        self.assertEqual(validacion["tramos_computados"], 94)
        self.assertEqual(
            validacion["cobertura_rotulos_porcentaje"],
            100.0,
        )

        for tramo in resultado[
            "vigas_riostra_computo_detalle"
        ]:
            self.assertLess(
                tramo["longitud_libre_entre_caras_m"],
                tramo["longitud_entre_ejes_m"],
            )
            self.assertEqual(tramo["estado"], "computado")

        resumen_vr1 = next(
            fila
            for fila in resultado[
                "resumen_vigas_riostra_por_tipo"
            ]
            if fila["referencia"] == "VR1"
        )
        self.assertEqual(
            resumen_vr1["cantidad_tramos"],
            30,
        )

    def test_un_apoyo_intermedio_divide_una_linea_continua(self):
        with TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "tres_apoyos.pdf"
            documento = pymupdf.open()
            pagina = documento.new_page(
                width=200,
                height=100,
            )
            forma = pagina.new_shape()
            forma.draw_line(
                pymupdf.Point(20, 45),
                pymupdf.Point(180, 45),
            )
            forma.draw_line(
                pymupdf.Point(20, 55),
                pymupdf.Point(180, 55),
            )
            forma.finish(color=(0, 0, 0), width=0.6)
            forma.commit()
            documento.save(ruta)
            documento.close()

            apoyos = [
                {
                    "apoyo_id": identificador,
                    "referencia": identificador,
                    "pagina": 1,
                    "centro_x": centro_x,
                    "centro_y": 50.0,
                    "ancho_pdf": 10.0,
                    "alto_pdf": 10.0,
                }
                for identificador, centro_x in (
                    ("C1-01", 20.0),
                    ("C2-01", 100.0),
                    ("C3-01", 180.0),
                )
            ]
            rotulos = [
                {
                    "referencia": "VR1",
                    "texto_original": "V.R. 1 (40 X 50)",
                    "pagina": 1,
                    "ancho_m": 0.40,
                    "alto_m": 0.50,
                    "x0": centro_x - 8,
                    "y0": 47,
                    "x1": centro_x + 8,
                    "y1": 53,
                    "centro_x": centro_x,
                    "centro_y": 50.0,
                }
                for centro_x in (60.0, 140.0)
            ]

            resultado = reconstruir_tramos_vigas_entre_apoyos(
                ruta,
                apoyos,
                rotulos,
            )
            pares = {
                frozenset(
                    (
                        tramo["apoyo_inicial_id"],
                        tramo["apoyo_final_id"],
                    )
                )
                for tramo in resultado["tramos"]
            }

            self.assertEqual(
                pares,
                {
                    frozenset(("C1-01", "C2-01")),
                    frozenset(("C2-01", "C3-01")),
                },
            )


if __name__ == "__main__":
    unittest.main()
