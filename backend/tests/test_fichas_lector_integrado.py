"""El lector 1.5 propone secciones sin aprobar recorridos ni materiales."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pymupdf

from computos.documentos.fichas_lector_visual import integrar_fichas_cimientos


def ficha(referencia="C-2", *, superior=.3, base=.6, altura=.4, fuente_sha="a" * 64):
    return {
        "referencia_fuente": referencia,
        "familia_propuesta": "cimentacion_sin_subtipo",
        "unidad_propuesta": "m",
        "archivo": "lamina.pdf",
        "pagina": 1,
        "sha256_pdf": fuente_sha,
        "caja_documental_px": [10, 20, 120, 160],
        "ancho_px": 600,
        "alto_px": 400,
        "campos_propuestos": {
            clave: {"valor": valor, "lectura_id": f"lectura-{clave}"}
            for clave, valor in (
                ("horizontal_superior", superior),
                ("horizontal_inferior", base),
                ("vertical", altura),
            )
        },
    }


class IntegracionFichasTests(unittest.TestCase):
    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.ruta = Path(temporal.name) / "lamina.pdf"
        with pymupdf.open() as pdf:
            p = pdf.new_page(width=600, height=400)
            p.insert_text((30, 30), "TIPOS DE CIMIENTOS")
            pdf.save(self.ruta)
        self.fuentes = [{
            "archivo": self.ruta.name,
            "pagina": 1,
            "sha256": sha256(self.ruta.read_bytes()).hexdigest(),
        }]
        self.make_ficha = lambda *args, **kwargs: ficha(
            *args, fuente_sha=self.fuentes[0]["sha256"], **kwargs
        )

    def propuesta(self, top=None, base=None, height=None):
        return {"elementos": [{
            "referencia_propuesta": "C-2",
            "ancho_superior_m_propuesto": top,
            "ancho_base_m_propuesto": base,
            "altura_m_propuesta": height,
            "longitud_m_propuesta": 91.32,
            "material_propuesto": None,
        }]}

    def integrar(self, propuesta, fichas):
        with patch("computos.documentos.fichas_lector_visual._paginas_fichas", return_value=([{}], [])), \
             patch("computos.documentos.fichas_lector_visual.lector.construir_fichas", return_value=(fichas, [])), \
             patch.dict("os.environ", {"COMPUTOESTIA_FICHAS_OCR": "0"}):
            return integrar_fichas_cimientos(propuesta, self.ruta, self.fuentes)

    def test_seccion_se_completa_sin_cambiar_longitud_ni_material(self):
        resultado = self.integrar(self.propuesta(), [self.make_ficha()])
        item = resultado["elementos"][0]
        self.assertEqual((item["ancho_superior_m_propuesto"], item["ancho_base_m_propuesto"], item["altura_m_propuesta"]), (.3, .6, .4))
        self.assertEqual(item["longitud_m_propuesta"], 91.32)
        self.assertIsNone(item["material_propuesto"])
        self.assertTrue(item["ficha_lector_15"]["requiere_revision"])
        self.assertEqual(len(resultado["paginas_detalle_lector_15"]), 1)

    def test_fuentes_contradictorias_no_se_sobrescriben(self):
        item = self.integrar(self.propuesta(top=.5), [self.make_ficha()])["elementos"][0]
        self.assertEqual(item["ancho_superior_m_propuesto"], .5)
        self.assertIsNone(item["ancho_base_m_propuesto"])
        self.assertIn("difieren", item["conflicto_fichas_lector"])

    def test_dos_fichas_para_mismo_tipo_no_habilitan_seccion(self):
        item = self.integrar(self.propuesta(), [self.make_ficha(), self.make_ficha()])["elementos"][0]
        self.assertIsNone(item["altura_m_propuesta"])
        self.assertIn("varias", item["conflicto_fichas_lector"])

    def test_ficha_de_otro_pdf_no_se_asocia(self):
        resultado = self.integrar(self.propuesta(), [ficha()])
        self.assertIsNone(resultado["elementos"][0]["altura_m_propuesta"])
        self.assertFalse(resultado["fichas_lector_15"]["fichas"][0]["origen_pdf_coincide"])

    def test_seccion_ocr_regional_es_respaldo_solo_si_faltan_datos(self):
        with patch("computos.documentos.fichas_lector_visual._paginas_fichas", side_effect=[([{}], []), ([{}], [])]) as leer, \
             patch("computos.documentos.fichas_lector_visual.lector.construir_fichas", side_effect=[([self.make_ficha(altura=None)], []), ([self.make_ficha()], [])]):
            item = integrar_fichas_cimientos(self.propuesta(), self.ruta, self.fuentes)
        self.assertEqual(leer.call_count, 2)
        self.assertTrue(leer.call_args.kwargs["ocr"])
        self.assertEqual(item["elementos"][0]["altura_m_propuesta"], .4)


if __name__ == "__main__":
    unittest.main()
