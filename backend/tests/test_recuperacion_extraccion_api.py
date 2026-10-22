"""Un formato parcial debe permitir revisar datos y llegar a cantidades."""

import json
import unittest

import pymupdf
from fastapi.testclient import TestClient

from computos.api import app


class RecuperacionExtraccionApiTests(unittest.TestCase):
    def test_cuadro_sin_armadura_pasa_a_geometria_y_calcula_sin_inventar_acero(self):
        with pymupdf.open() as doc:
            p = doc.new_page(width=600, height=600)
            p.insert_text((30, 30), 'PLANTA DE FUNDACIONES')
            p.insert_text((100, 150), 'BA-7')
            p.insert_text((300, 350), 'BA-8')
            p = doc.new_page(width=600, height=600)
            p.insert_text((30, 30), 'CUADRO DE ZAPATAS')
            for x,t in [(30,'REF'),(100,'X'),(160,'Y'),(220,'H')]:
                p.insert_text((x,60),t)
            for y,ref in [(90,'BA-7'),(120,'BA-8')]:
                for x,t in [(30,ref),(100,'1.20'),(160,'1.40'),(220,'0.45')]:
                    p.insert_text((x,y),t)
            p = doc.new_page(width=600, height=600)
            p.insert_text((30,30),'DETALLE DE COLUMNAS')
            p.insert_text((60,80),'C1 0.30 X 0.30')
            contenido = doc.tobytes()
        with TestClient(app) as cliente:
            def enviar(decision=None):
                data = {'ejecutar_computo':'true', 'proyecto_id':'regresion-formato-parcial'}
                if decision is not None:
                    data['revision_geometria'] = json.dumps(decision)
                return cliente.post('/api/analisis/automatico/', data=data,
                    files=[('archivos',('nombre-arbitrario.pdf',contenido,'application/pdf'))])
            inicial = enviar()
            self.assertEqual(inicial.status_code, 200, inicial.text[:600])
            body = inicial.json()
            self.assertEqual(body['estado'], 'requiere_revision_geometria', str(body)[:1500])
            self.assertEqual(body['enrutamiento']['recuperacion_extraccion']['destino'], 'geometria')
            propuesta = body['revision_geometria']
            self.assertEqual(len(propuesta['elementos']), 2)
            self.assertTrue(all(e['origen_dimensiones']=='cuadro_local_tipado' for e in propuesta['elementos']))
            decision = {
                'identidad_fuentes':propuesta['identidad_fuentes'],
                'revisor':'Profesional de prueba',
                'motivo':'Cotas verificadas en las filas originales del cuadro de zapatas.',
                'elementos':[{'id':e['id'],'incluir':True,'referencia':e['referencia_propuesta'],
                    'x_m':e['x_m_propuesto'],'y_m':e['y_m_propuesto'],'h_m':e['h_m_propuesto']}
                    for e in propuesta['elementos']],
            }
            calculado = enviar(decision)
            self.assertEqual(calculado.status_code, 200, calculado.text[:600])
            resultado = calculado.json()
            self.assertEqual(resultado['estado'],'completado', str(resultado)[:1500])
            self.assertAlmostEqual(resultado['resultado']['volumen_hormigon_m3'], 1.512)
            self.assertIsNone(resultado['resultado']['peso_acero_kg'])
            repetido = enviar(decision)
            self.assertEqual(repetido.json()['estado'], 'completado')
            self.assertAlmostEqual(repetido.json()['resultado']['volumen_hormigon_m3'], 1.512)

