from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import unittest
import pymupdf
from fastapi.testclient import TestClient
from computos.api.aplicacion import app
from computos.documentos.auditoria_tecnica import auditar_documentos
from computos.ia.enrutador_documentos import enrutar_documentos


class AuditoriaTests(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup);self.path=Path(tmp.name)/'obra.pdf'
        with pymupdf.open() as pdf:
            p=pdf.new_page()
            p.insert_text((30,25),'CUADRO DE FUNDACIONES')
            for x,t in [(30,'TIPO'),(150,'X'),(210,'Y'),(270,'H'),(340,'ARMADURA')]: p.insert_text((x,60),t)
            for y in [90,120]:
                for x,t in [(30,'Z7'),(150,'1.20'),(210,'1.40'),(270,'0.40'),(340,'1/2 c/15')]:p.insert_text((x,y),t)
            p=pdf.new_page();p.insert_text((30,30),'PLANTA DE FUNDACIONES\nZ7\nZ7\nZ8')
            pdf.save(self.path)
        self.rutas={'doc':self.path}
        self.diagnostico={'documentos':[{'documento_id':'doc','nombre':'obra.pdf','sha256':'a'*64,'paginas':[{'pagina':1,'caracteres':100,'clasificacion':{'objetivos':{'contenidos':{'etiquetas':['fundaciones']},'roles_documentales':{'etiquetas':['cuadro_planilla']}}}},{'pagina':2,'caracteres':100,'clasificacion':{'objetivos':{'contenidos':{'etiquetas':['fundaciones']},'roles_documentales':{'etiquetas':['planta']}}}}]}]}

    def test_catalogo_general_y_repeticiones_de_planta(self):
        r=auditar_documentos(self.rutas,self.diagnostico)
        codigos=[(i['codigo'],i['referencia']) for i in r['incidencias']]
        self.assertIn(('referencia_duplicada_cuadro','Z7'),codigos)
        self.assertIn(('fundacion_sin_fila_localizada','Z8'),codigos)
        duplicada=next(i for i in r['incidencias'] if i['codigo']=='referencia_duplicada_cuadro')
        self.assertEqual([f['pagina'] for f in duplicada['fuentes']],[1,1])
        self.assertEqual(len([i for i in r['incidencias'] if i['codigo']=='referencia_duplicada_cuadro']),1)

    def test_fallo_control_no_se_presenta_como_ausencia_de_errores(self):
        with patch('computos.documentos.auditoria_tecnica.descubrir_catalogo_referencias',side_effect=ValueError('No interpretable')):
            r=auditar_documentos(self.rutas,self.diagnostico)
        self.assertEqual(r['estado'],'parcial')
        self.assertEqual(r['resumen']['controles_no_evaluados'],1)
        self.assertFalse(any(i['codigo']=='fundacion_sin_fila_localizada' for i in r['incidencias']))

    def test_resolucion_guardada_obsoleta_no_bloquea_revalidacion(self):
        decision = {
            'accion': 'seleccionar_fuente_columna',
            'incidencia_id': '1' * 24,
            'campo': 'seccion',
            'referencia': 'C99',
            'sha256': 'a' * 64,
            'pagina': 1,
            'revisor': 'Ingeniera',
            'motivo': 'Decisión perteneciente a un conflicto anterior ya corregido.',
        }
        resultado = auditar_documentos(
            self.rutas,
            self.diagnostico,
            resoluciones=[decision],
        )
        self.assertEqual(resultado['resoluciones_aplicadas'], [])
        self.assertEqual(len(resultado['resoluciones_obsoletas']), 1)
        self.assertEqual(
            resultado['resoluciones_obsoletas'][0]['estado'],
            'obsoleta',
        )

    def test_reasigna_detalle_con_fuente_y_revalida(self):
        ruta=self.path.parent/'columnas.pdf'
        with pymupdf.open() as pdf:
            p=pdf.new_page();p.insert_text((30,30),'DETALLE COLUMNA 4 (C4)')
            p=pdf.new_page();p.insert_text((30,30),'PLANTA DE COLUMNAS C3')
            pdf.save(ruta)
        huella='b'*64
        diagnostico={'fuentes_por_rol':{'detalles':{'fuentes':[{'sha256':huella,'pagina':1}]}},'documentos':[{
            'documento_id':'doc','nombre':'columnas.pdf','sha256':huella,'paginas':[
                {'pagina':1,'caracteres':30,'clasificacion':{'objetivos':{'contenidos':{'etiquetas':['columnas_pilares']},'roles_documentales':{'etiquetas':['detalle']}}}},
                {'pagina':2,'caracteres':30,'clasificacion':{'objetivos':{'contenidos':{'etiquetas':['columnas_pilares']},'roles_documentales':{'etiquetas':['planta']}}}},
            ]}]}
        pendiente=auditar_documentos({'doc':ruta},diagnostico)
        self.assertTrue(any(i['codigo']=='columna_sin_detalle_localizado' and i['referencia']=='C3' for i in pendiente['incidencias']))
        decision={'accion':'reasignar_referencia_detalle','sha256':huella,'pagina':1,'referencia_original':'C4','referencia_correcta':'C3','revisor':'Ingeniera','motivo':'Rótulo verificado contra la planta estructural.'}
        resuelta=auditar_documentos({'doc':ruta},diagnostico,resoluciones=[decision])
        self.assertFalse(any(i['codigo']=='columna_sin_detalle_localizado' and i['referencia']=='C3' for i in resuelta['incidencias']))
        self.assertTrue(any(i['codigo']=='referencia_detalle_reasignada' for i in resuelta['incidencias']))

    def test_api_audita_sin_ejecutar_computo(self):
        with patch('computos.api.aplicacion.procesar_archivos_hibrido') as motor:
            r=TestClient(app).post('/api/analisis/automatico/',files=[('archivos',('obra.pdf',self.path.read_bytes(),'application/pdf'))])
        self.assertEqual(r.status_code,200)
        self.assertIn('auditoria_tecnica',r.json()['enrutamiento'])
        self.assertTrue(r.json()['enrutamiento']['auditoria_tecnica']['incidencias'])
        motor.assert_not_called()

    @unittest.skipUnless(os.getenv('COMPUTOESTIA_TEST_PDF'),'PDF real de regresión no configurado')
    def test_pdf_real_seis_hallazgos_con_fuentes(self):
        rutas={'doc':Path(os.environ['COMPUTOESTIA_TEST_PDF'])}
        r=auditar_documentos(rutas,enrutar_documentos(rutas).a_diccionario())
        ids={(i['codigo'],i['referencia']) for i in r['incidencias']}
        self.assertEqual(ids,{('referencia_duplicada_cuadro','F12'),('fundacion_sin_fila_localizada','F13'),('secciones_diferentes','C4'),('armaduras_diferentes','C4'),('columna_sin_detalle_localizado','C3'),('seccion_columna_no_interpretable','C19')})
        s=next(i for i in r['incidencias'] if i['codigo']=='secciones_diferentes')
        self.assertEqual([(f['pagina'],f['dimensiones_m']) for f in s['fuentes']],[(1,[.5,.6]),(2,[.45,.6])])
        json.dumps(r)
