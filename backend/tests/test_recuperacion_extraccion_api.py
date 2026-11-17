"""Un formato parcial debe permitir revisar datos y llegar a cantidades."""

import json
import unittest

import pymupdf
from fastapi.testclient import TestClient

from computos.api import app
from computos.documentos.analisis import extraer_palabras_normalizadas
from computos.fundaciones.cuadros import DimensionesAgrupadasRequierenRevision, localizar_estructura_cuadro
from computos.fundaciones.cuadros_agrupados import extraer_tipos_agrupados
from computos.referencias import descubrir_catalogo_referencias


class RecuperacionExtraccionApiTests(unittest.TestCase):
    def test_otro_proyecto_con_tipos_y_unidades_distintas_lee_una_celda_agrupada(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "nombre-cualquiera.pdf"
            with pymupdf.open() as doc:
                pagina = doc.new_page(width=600, height=450)
                pagina.insert_text((30, 25), "CUADRO DE ZAPATAS")
                for x, titulo in ((30, "TIPO"), (130, "X×Y(cm)"), (315, "H(m)")):
                    pagina.insert_text((x, 60), titulo)
                for y, ref, par, alto in (
                    (95, "Z-04", "80 × 80", "0.25"),
                    (130, "Z-05", "120 × 100", "0.35"),
                ):
                    for x, valor in ((30, ref), (130, par), (315, alto)):
                        pagina.insert_text((x, y), valor)
                doc.save(ruta)

            palabras = extraer_palabras_normalizadas(ruta)
            catalogo = descubrir_catalogo_referencias(palabras)
            with self.assertRaises(DimensionesAgrupadasRequierenRevision):
                localizar_estructura_cuadro(palabras, catalogo, exigir_armadura=False)
            tipos = {item["referencia"]: item for item in extraer_tipos_agrupados(palabras, catalogo)}
            self.assertEqual(set(tipos), {"Z4", "Z5"})
            self.assertEqual((tipos["Z4"]["x_m"], tipos["Z4"]["y_m"], tipos["Z4"]["h_m"]),
                             (0.8, 0.8, 0.25))
            self.assertEqual((tipos["Z5"]["x_m"], tipos["Z5"]["y_m"], tipos["Z5"]["h_m"]),
                             (1.2, 1.0, 0.35))

    def test_dos_pdf_con_cotas_agrupadas_permiten_validar_y_calcular(self):
        with pymupdf.open() as plano:
            pagina = plano.new_page(width=600, height=600)
            pagina.insert_text((30, 30), "PLANTA GENERAL FUNDACIONES")
            pagina.insert_text((100, 150), "F1")
            pagina.insert_text((300, 350), "F2")
            planta = plano.tobytes()
        with pymupdf.open() as plano:
            pagina = plano.new_page(width=600, height=600)
            pagina.insert_text((30, 30), "CUADRO DE FUNDACIONES")
            for x, valor in [(30, "TIPO"), (130, "A x B"), (270, "Hmin"), (380, "As")]:
                pagina.insert_text((x, 60), valor)
            for y, referencia, dimensiones, espesor in (
                (90, "F1", "1.8 x 1.8", "0.35"),
                (125, "F2", "1.5 x 1.5", "0.30"),
            ):
                for x, valor in [(30, referencia), (130, dimensiones), (270, espesor)]:
                    pagina.insert_text((x, y), valor)
            detalles = plano.tobytes()

        with TestClient(app) as cliente:
            def enviar(revision=None):
                datos = {"ejecutar_computo": "true", "proyecto_id": "prueba-agrupadas"}
                if revision is not None:
                    datos["revision_geometria"] = json.dumps(revision)
                return cliente.post(
                    "/api/analisis/automatico/", data=datos,
                    files=[
                        ("archivos", ("plano.pdf", planta, "application/pdf")),
                        ("archivos", ("cuadro.pdf", detalles, "application/pdf")),
                    ],
                )

            primera = enviar()
            self.assertEqual(primera.status_code, 200, primera.text[:600])
            respuesta = primera.json()
            self.assertEqual(respuesta["estado"], "requiere_revision_geometria")
            propuesta = respuesta["revision_geometria"]
            self.assertTrue(propuesta["requiere_revisar_dimensiones_agrupadas"])
            self.assertEqual(len(propuesta["elementos"]), 2)
            por_tipo = {item["referencia"]: item for item in propuesta["tipos_fundaciones"]}
            self.assertEqual(set(por_tipo), {"F1", "F2"})
            self.assertEqual(
                [(e["referencia_propuesta"], e["x_m_propuesto"], e["y_m_propuesto"], e["h_m_propuesto"])
                 for e in propuesta["elementos"]],
                [("F1", 1.8, 1.8, None), ("F2", 1.5, 1.5, None)],
            )
            self.assertEqual(por_tipo["F1"]["texto_celda"], "1.8 x 1.8")
            revision = {
                "identidad_fuentes": propuesta["identidad_fuentes"],
                "revisor": "Ingeniera de prueba",
                "motivo": "Cotas comprobadas contra la tabla y la planta estructural.",
                "elementos": [
                    {
                        "id": elemento["id"],
                        "referencia": elemento["referencia_propuesta"],
                        "incluir": elemento["referencia_propuesta"] == "F1",
                        **({"x_m": 1.8, "y_m": 1.8, "h_m": 0.35}
                           if elemento["referencia_propuesta"] == "F1"
                           else {"motivo_exclusion": "Excluido solo para probar la revisión parcial."}),
                    }
                    for elemento in propuesta["elementos"]
                ],
            }
            calculado = enviar(revision)
            self.assertEqual(calculado.status_code, 200, calculado.text[:600])
            self.assertEqual(calculado.json()["estado"], "completado")
            self.assertAlmostEqual(calculado.json()["resultado"]["volumen_hormigon_m3"], 1.134)
            self.assertIsNone(calculado.json()["resultado"]["peso_acero_kg"])

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

