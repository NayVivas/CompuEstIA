import unittest

from computos.documentos.reglas_roles import detectar_indicio_corte


class ReglasRolesTests(unittest.TestCase):
    def test_detecta_corte_literal_en_texto(self):
        resultado = detectar_indicio_corte("PLANTA Y CORTE A-A")

        self.assertTrue(resultado["detectado"])
        self.assertEqual(resultado["patron"], "corte_literal")
        self.assertEqual(resultado["fuente_evidencia"], "texto_pagina")
        self.assertIn("CORTE A-A", resultado["contexto"])

    def test_detecta_corte_en_nombre_del_archivo(self):
        resultado = detectar_indicio_corte("", "Terminal cortes.pdf")

        self.assertTrue(resultado["detectado"])
        self.assertEqual(resultado["fuente_evidencia"], "nombre_archivo")
        self.assertEqual(resultado["confianza_regla"], "alta")

    def test_detecta_alias_codificado_del_pdf(self):
        resultado = detectar_indicio_corte("&RUWH longitudinal A-A")

        self.assertTrue(resultado["detectado"])
        self.assertEqual(resultado["patron"], "alias_pdf_codificado")

    def test_no_confunde_cortina_ni_seccion(self):
        for texto in ("detalle de cortina", "sección de viga", "planta baja"):
            with self.subTest(texto=texto):
                self.assertFalse(detectar_indicio_corte(texto)["detectado"])


if __name__ == "__main__":
    unittest.main()
