"""Las cotas deben corresponder a una geometría, no solo estar próximas."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from computos.fundaciones.geometria_distribuida import preparar_revision_geometrica


class CotasContornoTests(unittest.TestCase):
    def test_rotulo_alfabetico_no_se_presenta_como_cobertura_completa(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ruta = Path(temporal.name) / 'combinada.pdf'
        with pymupdf.open() as doc:
            p = doc.new_page()
            p.insert_text((20, 30), 'PLANTA DE CIMENTACION')
            p.insert_text((150, 150), 'Z1')
            p.insert_text((250, 250), 'Z-A')
            doc.save(ruta)
        resultado = preparar_revision_geometrica(ruta,
            fuentes_planta=[{'archivo':'combinada.pdf','pagina':1}],
            identidad_fuentes={'sha256':'f'*64,'fuentes':[]})
        self.assertEqual(resultado['referencias_no_interpretadas'][0]['texto'], 'Z-A')
        self.assertEqual(resultado['referencias_no_interpretadas'][0]['pagina_motor'], 1)

    def preparar(self, *, rotacion=0, contorno=True, proporcion_correcta=True, h_ajena=False):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ruta = Path(temporal.name) / "lamina-sin-nombre-especial.pdf"
        with pymupdf.open() as doc:
            p = doc.new_page(width=600, height=450)
            p.insert_text((20, 25), "PLANTA DE CIMENTACION")
            p.insert_text((225, 190), "Z-83", fontsize=10)
            if contorno:
                p.draw_rect(pymupdf.Rect(200, 160, 280, 220))
            p.insert_text((230, 152), "2.00", fontsize=7)
            p.insert_text((291, 198), "1.50" if proporcion_correcta else "3.50", fontsize=7, rotate=90)
            # Esta cota está más cerca del rótulo, pero dentro de la zapata.
            p.insert_text((240, 195), "0.25", fontsize=7)
            if h_ajena:
                p.insert_text((30, 350), 'COLUMNA H=3.00')
            p.set_rotation(rotacion)
            doc.save(ruta)
        return preparar_revision_geometrica(
            ruta, fuentes_planta=[{"archivo": ruta.name, "pagina": 1}],
            identidad_fuentes={"sha256": "f"*64, "fuentes": []},
        )["elementos"][0]

    def test_cotas_coherentes_no_sustituidas_por_numero_cercano(self):
        propuesta = self.preparar()
        self.assertEqual((propuesta['x_m_propuesto'], propuesta['y_m_propuesto']), (2.0, 1.5))
        self.assertEqual(propuesta['origen_dimensiones'], 'contorno_y_dos_cotas_coherentes')

    def test_rotacion_270_conserva_ejes_visuales_y_dimensiones(self):
        propuesta = self.preparar(rotacion=270)
        self.assertEqual((propuesta['x_m_propuesto'], propuesta['y_m_propuesto']), (1.5, 2.0))

    def test_no_rellena_con_numeros_cercanos_sin_contorno(self):
        propuesta = self.preparar(contorno=False)
        self.assertIsNone(propuesta['x_m_propuesto'])
        self.assertIsNone(propuesta['y_m_propuesto'])
        self.assertTrue(propuesta['alternativas_dimensiones'])

    def test_rechaza_escalas_incompatibles_en_los_dos_ejes(self):
        propuesta = self.preparar(proporcion_correcta=False)
        self.assertIsNone(propuesta['x_m_propuesto'])
        self.assertIsNone(propuesta['y_m_propuesto'])

    def test_altura_de_columna_ajena_no_es_altura_de_zapata(self):
        self.assertIsNone(self.preparar(h_ajena=True)['h_m_propuesto'])

