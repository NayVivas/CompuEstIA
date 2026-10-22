from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import json
import unittest
import pymupdf
from fastapi.testclient import TestClient
from computos.api.aplicacion import app
from computos.ia.enrutador_documentos import enrutar_documentos
from computos.ia.clasificacion_evidencias import combinar, clasificar_evidencias
from computos.ia.revision_documental import validar_revisiones


class RevisionDocumentalTests(unittest.TestCase):
    def setUp(self):
        t=TemporaryDirectory();self.addCleanup(t.cleanup);self.path=Path(t.name)/'original.pdf'
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((20,30),'ESTRUCTURA\nDETALLE COLUMNA 8\nESTRIBOS')
            pdf.new_page()
            pdf.save(self.path)
        self.decision={'sha256':sha256(self.path.read_bytes()).hexdigest(),'pagina':1,'revisor':'Ingeniera A','motivo':'Verificado en el plano original.','objetivos':{'disciplinas':['arquitectura'],'roles_documentales':['detalle'],'contenidos':['ventanas_carpinterias']}}

    def test_aplica_y_conserva_original_sin_habilitar_motor(self):
        r=enrutar_documentos({'doc':self.path},revisiones=[self.decision])
        p=r.documentos[0]['paginas'][0]
        self.assertEqual(p['estado'],'revisado_profesional')
        self.assertEqual(p['clasificacion']['objetivos']['disciplinas']['etiquetas'],['arquitectura'])
        self.assertIn('estructura',p['clasificacion_automatica']['objetivos']['disciplinas']['etiquetas'])
        self.assertEqual(p['roles_motor'],[])
        self.assertFalse(r.listo)

    def test_rechaza_otro_pdf_o_pagina(self):
        for cambios in [{'sha256':'a'*64},{'pagina':9}]:
            with self.assertRaises(ValueError): enrutar_documentos({'doc':self.path},revisiones=[{**self.decision,**cambios}])

    def test_clasificar_pagina_sin_texto_no_repara_lectura(self):
        r=enrutar_documentos({'doc':self.path},revisiones=[{**self.decision,'pagina':2}])
        p=r.documentos[0]['paginas'][1]
        self.assertTrue(p['requiere_revision'])
        self.assertEqual(p['roles_motor'],[])

    def test_api_recibe_revision_y_rechaza_invalida(self):
        c=TestClient(app)
        files=[('archivos',('original.pdf',self.path.read_bytes(),'application/pdf'))]
        r=c.post('/api/analisis/automatico/',files=files,data={'revision_documental':json.dumps([self.decision])})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['enrutamiento']['documentos'][0]['paginas'][0]['estado'],'revisado_profesional')
        r=c.post('/api/analisis/automatico/',files=files,data={'revision_documental':'{bad'})
        self.assertEqual(r.status_code,422)

    def test_validacion_sin_motivo_o_etiquetas_o_duplicados(self):
        for decisiones in [[{**self.decision,'motivo':''}],[{**self.decision,'objetivos':{}}],[self.decision,self.decision]]:
            with self.assertRaises(ValueError): validar_revisiones(decisiones)

    def test_conflicto_de_disciplina_sigue_pendiente(self):
        r=combinar({'objetivos':{'disciplinas':{'etiquetas':['electricidad']}}},clasificar_evidencias('ESTRUCTURA\nDETALLE COLUMNA 1'))
        self.assertTrue(r['requiere_revision'])
        self.assertIn('discrepan',r['motivos_revision'][0])
