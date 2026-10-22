"""Pruebas del coordinador híbrido sin red ni consumo de API."""

from pathlib import Path
import tempfile
import unittest

from computos.ia.flujo_hibrido import procesar_archivos_hibrido
from computos.ia.proveedor import ProveedorIAError


class ClasificadorFalso:
    def __init__(self, requiere_revision=False):
        self.requiere_revision = requiere_revision

    def clasificar_pdf(self, ruta):
        return {
            "archivo": Path(ruta).name,
            "estado": "clasificado",
            "compatible_computo_estructural": True,
            "requiere_revision": self.requiere_revision,
            "advertencias": [],
        }


def procesador_falso(**_archivos):
    return {
        "cantidad_fundaciones": 61,
        "volumen_hormigon_m3": 194.72,
    }


class FlujoHibridoTests(unittest.TestCase):
    def _archivos(self, carpeta):
        rutas = {}
        for nombre in ("planta", "detalles", "columnas"):
            ruta = Path(carpeta) / f"{nombre}.pdf"
            ruta.write_bytes(b"%PDF-prueba")
            rutas[nombre] = ruta
        return rutas

    def test_sin_ia_conserva_resultado_del_motor(self):
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = procesar_archivos_hibrido(
                **self._archivos(carpeta),
                usar_ia_generativa=False,
                clasificador=ClasificadorFalso(),
                procesador_deterministico=procesador_falso,
            )

        self.assertEqual(resultado["cantidad_fundaciones"], 61)
        self.assertEqual(
            resultado["ia_generativa_opcional"]["estado"],
            "desactivada",
        )
        self.assertTrue(
            resultado["flujo_hibrido"]["funciona_sin_creditos_api"]
        )

    def test_error_del_proveedor_no_interrumpe_motor(self):
        def ia_fallida(_ruta):
            raise ProveedorIAError("Sin créditos.")

        with tempfile.TemporaryDirectory() as carpeta:
            resultado = procesar_archivos_hibrido(
                **self._archivos(carpeta),
                usar_ia_generativa=True,
                clasificador=ClasificadorFalso(
                    requiere_revision=True
                ),
                procesador_deterministico=procesador_falso,
                analizador_ia=ia_fallida,
            )

        self.assertEqual(resultado["cantidad_fundaciones"], 61)
        self.assertEqual(
            resultado["ia_generativa_opcional"]["estado"],
            "omitida_sin_interrumpir_motor",
        )
        self.assertEqual(
            len(
                resultado["ia_generativa_opcional"]["documentos"]
            ),
            3,
        )

    def test_ia_no_se_invoca_si_exp19_no_pide_revision(self):
        llamadas = []

        def ia_falsa(ruta):
            llamadas.append(ruta)
            return {"resultado": "no debería ejecutarse"}

        with tempfile.TemporaryDirectory() as carpeta:
            resultado = procesar_archivos_hibrido(
                **self._archivos(carpeta),
                usar_ia_generativa=True,
                clasificador=ClasificadorFalso(),
                procesador_deterministico=procesador_falso,
                analizador_ia=ia_falsa,
            )

        self.assertEqual(llamadas, [])
        self.assertEqual(
            resultado["ia_generativa_opcional"]["estado"],
            "no_necesaria",
        )


if __name__ == "__main__":
    unittest.main()

