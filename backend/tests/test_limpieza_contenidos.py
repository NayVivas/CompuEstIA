import unittest
from computos.ia.limpieza_contenidos import limpiar_texto

class TestLimpiezaContenidosReal(unittest.TestCase):
    def test_remover_cajetin_y_autores(self):
        # Deben descartarse por completo por ser bloques administrativos
        self.assertEqual(limpiar_texto('PROYECTO: EDIFICIO ALFA'), '')
        self.assertEqual(limpiar_texto('DIBUJÓ: Juan Pérez'), '')
        self.assertEqual(limpiar_texto('APROBÓ: Ing. Gómez'), '')
        self.assertEqual(limpiar_texto('ESC. 1:100'), '')

    def test_preservar_plano_de(self):
        # Deben remover el prefijo administrativo pero conservar la semántica técnica
        self.assertEqual(limpiar_texto('PLANO DE FUNDACIONES'), 'fundaciones')
        self.assertEqual(limpiar_texto('PLANOS DE DETALLES ESTRUCTURALES'), 'detalles estructurales')

    def test_metadatos_inline_y_viñetas(self):
        # Deben limpiar el ruido inline o el prefijo pero dejar el contenido semántico
        self.assertEqual(limpiar_texto('PLANTA / ESCALA 1:50'), 'planta')
        self.assertEqual(limpiar_texto('1) VIGAS DE RIOSTRA'), 'vigas riostra')
        self.assertEqual(limpiar_texto('• COLUMNAS DE HORMIGON'), 'columnas hormigon')

if __name__ == '__main__':
    unittest.main()