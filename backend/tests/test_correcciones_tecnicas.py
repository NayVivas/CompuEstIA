import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from fastapi.testclient import TestClient
from computos.api.aplicacion import app
from computos.documentos.correcciones_tecnicas import validar_correcciones, validar_resoluciones, corregir_filas
from computos.documentos.analisis import extraer_palabras_normalizadas
from computos.referencias import descubrir_catalogo_referencias
from computos.api.servicio import _aplicar_resoluciones_tecnicas
from computos.configuracion.proyecto import ConfiguracionProyecto


class CorreccionesTests(unittest.TestCase):
    def setUp(self):
        from tests.test_auditoria_tecnica import AuditoriaTests
        AuditoriaTests.setUp(self)
    def decision(self, **changes):
        return {'sha256':sha256(self.path.read_bytes()).hexdigest(),'pagina':1,'fila':2,'referencia_original':'Z7','referencia_correcta':'Z8','revisor':'Profesional','motivo':'Fila identificada según referencia de planta.',**changes}

    def request(self, decisions):
        return TestClient(app).post('/api/analisis/automatico/',files=[('archivos',('obra.pdf',self.path.read_bytes(),'application/pdf'))],data={'correcciones_tecnicas':json.dumps(decisions)})

    def test_corrige_solo_fila_y_revalida_cruce_con_planta(self):
        r=self.request([self.decision()]);self.assertEqual(r.status_code,200,r.text)
        audit=r.json()['enrutamiento']['auditoria_tecnica']
        self.assertFalse(any(not i['resuelta'] for i in audit['incidencias']))
        self.assertEqual(audit['revisiones_aplicadas'][0]['aparicion'],2)
        self.assertTrue(any(i['codigo']=='referencia_corregida_cuadro' for i in audit['incidencias']))

    def test_no_acepta_otro_archivo_fila_o_referencia(self):
        for c in [{'sha256':'b'*64},{'fila':99},{'referencia_original':'Z9'},{'referencia_correcta':'Z7'},{'motivo':'x'}]:
            self.assertEqual(self.request([self.decision(**c)]).status_code,422)

    def test_no_modifica_pdf_original(self):
        before=self.path.read_bytes();self.request([self.decision()]);self.assertEqual(before,self.path.read_bytes())

    def test_valida_seccion_manual_general(self):
        decision={'accion':'definir_seccion_columna','sha256':'a'*64,'pagina':3,'referencia':'C19','dimension_1_m':.25,'dimension_2_m':.30,'revisor':'Ingeniera','motivo':'Dimensiones verificadas en el detalle estructural.'}
        self.assertEqual(validar_resoluciones([decision])[0]['dimension_2_m'],.30)
        with self.assertRaises(ValueError):
            validar_resoluciones([{**decision,'dimension_1_m':0}])

    def test_correccion_llega_al_motor_con_aparicion_y_huellas(self):
        import pymupdf
        col=self.path.parent/'columnas.pdf'
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((30,30),'ESTRUCTURA DETALLE COLUMNA 8 (C8)')
            pdf.save(col)
        files=[('archivos',(p.name,p.read_bytes(),'application/pdf')) for p in (self.path,col)]
        with patch('computos.api.aplicacion.procesar_archivos_hibrido',return_value={'cantidad_fundaciones':3}) as motor:
            r=TestClient(app).post('/api/analisis/automatico/',files=files,data={'correcciones_tecnicas':json.dumps([self.decision()]),'ejecutar_computo':'true'})
        self.assertEqual(r.status_code,200,r.text)
        motor.assert_called_once()
        decision=motor.call_args.kwargs['revision_cuadro']
        self.assertEqual(decision['correcciones_referencias_cuadro'][0]['aparicion'],2)
        self.assertEqual(decision['correcciones_referencias_cuadro'][0]['referencia_correcta'],'Z8')
        self.assertEqual(set(decision['huellas_archivos']),{'planta','detalles','columnas'})

    def test_reasignacion_conserva_rol_y_pagina_del_motor(self):
        configuracion = ConfiguracionProyecto.vacia()
        archivos = {
            "planta": Path("planta.pdf"),
            "detalles": Path("detalles.pdf"),
            "columnas": Path("columnas.pdf"),
        }
        decision = {
            "accion": "reasignar_referencia_detalle",
            "rol": "columnas",
            "pagina_motor": 2,
            "referencia_original": "C4",
            "referencia_correcta": "C3",
            "revisor": "Ing. Responsable",
            "motivo": "Rótulo verificado contra la planta estructural.",
        }

        _aplicar_resoluciones_tecnicas(
            configuracion,
            archivos,
            [decision],
        )

        self.assertEqual(
            configuracion.reasignaciones_detalles_columnas,
            [
                {
                    "rol": "columnas",
                    "pagina": 2,
                    "referencia_original": "C4",
                    "referencia_correcta": "C3",
                    "revisor": "Ing. Responsable",
                    "motivo": (
                        "Rótulo verificado contra la planta estructural."
                    ),
                }
            ],
        )
