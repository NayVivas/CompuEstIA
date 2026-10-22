"""Regresiones: portabilidad del modelo y separación entre evidencia y predicción."""
import builtins
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import numpy as np
from computos.ia.clasificador_exp19 import ClasificadorExp19, ruta_modelos_predeterminada
from computos.ia.exp19_portable import Exp19Portable
from computos.ia.clasificacion_evidencias import clasificar_evidencias, combinar


class PortableTests(unittest.TestCase):
    def test_inferencia_sin_importar_sklearn_o_joblib(self):
        original = builtins.__import__
        def protegido(nombre,*args,**kwargs):
            if nombre.split('.')[0] in ('sklearn','joblib'):
                raise AssertionError('La inferencia portable no debe cargar pickle/sklearn')
            return original(nombre,*args,**kwargs)
        with patch('builtins.__import__',side_effect=protegido):
            r=ClasificadorExp19().clasificar_texto('ESTRUCTURA DETALLE COLUMNA 1 ESTRIBOS')
        self.assertEqual(r['runtime'],'numpy_portable')

    def test_equivalencia_vectores_y_tres_modelos(self):
        import joblib
        carpeta=ruta_modelos_predeterminada()
        portable=Exp19Portable(carpeta)
        v=joblib.load(carpeta/'EXP19_TFIDF_HIBRIDO.joblib')
        textos=['PÓRTICO 8\nC1\n50 X 60\nARQUITECTO: Firma', 'a á\t b  Ø 3/8 EST. acero\n\nPLANTA', 'FACHADA PRINCIPAL VENTANAS', '', 'PLANTA SANITARIA DESAGUES', 'xxxyyzz 123']
        for texto in textos:
            x=v.transform([texto]); y=portable.vectorizar(texto)
            np.testing.assert_allclose(y,x.toarray()[0],atol=1e-12)
            for objetivo in ('disciplinas','roles_documentales','contenidos'):
                modelo=joblib.load(carpeta/f'EXP19_{objetivo}_MODELO.joblib')
                np.testing.assert_allclose(portable.puntajes(objetivo,y),modelo.decision_function(x)[0],atol=1e-12)

    def test_rechaza_pesos_danados(self):
        with TemporaryDirectory() as temp:
            p=Path(temp)
            (p/'EXP19_PORTABLE.json').write_text(json.dumps({'version':1,'sha256_pesos':'incorrecto'}))
            (p/'EXP19_PORTABLE.npz').write_bytes(b'incompleto')
            with self.assertRaisesRegex(ValueError,'incompletos'):
                Exp19Portable(p)


class EvidenciasTests(unittest.TestCase):
    def etiquetas(self,t,obj):
        return clasificar_evidencias(t)['objetivos'][obj]['etiquetas']

    def test_firma_no_es_arquitectura(self):
        self.assertEqual(self.etiquetas('ESTRUCTURA\nDETALLE COLUMNA 8\nARQUITECTO: Firma','disciplinas'),['estructura'])
        self.assertEqual(self.etiquetas('ARQUITECTO: Firma','disciplinas'),[])

    def test_porticos_y_secciones(self):
        t='ESTRUCTURA\nPÓRTICO Z\nC20\nC21\nC22\n40 X 50\n45 X 60\n30 X 40'
        self.assertEqual(set(self.etiquetas(t,'contenidos')),{'porticos','columnas_pilares','vigas'})
        self.assertIn('elevacion_porticos',self.etiquetas(t,'roles_documentales'))

    def test_equipo_no_es_lamina_electrica(self):
        t='PLANTA SOTANO\nOFICINAS\nTESORERIA\nCONTABILIDAD\nPLANTA ELECTRICA\n450KVA'
        self.assertEqual(self.etiquetas(t,'disciplinas'),['arquitectura'])
        self.assertIn('electricidad',self.etiquetas('INSTALACION ELECTRICA\nDIAGRAMA UNIFILAR','disciplinas'))

    def test_nivel_de_viga_no_es_planta(self):
        t='ESTRUCTURA\nV. ESP 55 (PLANTA BAJA)\nEST Ø 3/8\nCORTE 1 ESC 1:10'
        self.assertNotIn('planta',self.etiquetas(t,'roles_documentales'))
        self.assertIn('detalle',self.etiquetas(t,'roles_documentales'))

    def test_fachada_no_confirma_columnas_por_cota(self):
        t='FACHADA PRINCIPAL\nCOLUMNA +17.31\nVENTANAS'
        self.assertEqual(self.etiquetas(t,'disciplinas'),['arquitectura'])
        self.assertNotIn('columnas_pilares',self.etiquetas(t,'contenidos'))

    def test_referencia_a_otras_laminas_no_confirma_escalera(self):
        t='ESTRUCTURA\nLOSACERO\nNOTA:\nPARA LA ESTRUCTURA DEL\nNUCLEO DE LA ESCALERA Y\nEL ASCENSOR VER LAMINAS\nDESDE LA E30/35 HASTA LA\nE35/35'
        self.assertNotIn('escaleras_estructurales',self.etiquetas(t,'contenidos'))

    def test_hipotesis_modelo_separadas(self):
        e=clasificar_evidencias('ESTRUCTURA\nPORTICO 30')
        m={'objetivos':{'contenidos':{'etiquetas':['fundaciones','porticos']}}}
        r=combinar(m,e)
        self.assertNotIn('fundaciones',r['objetivos']['contenidos']['etiquetas'])
        self.assertEqual(r['propuestas_modelo_sin_evidencia']['contenidos'],['fundaciones'])
        self.assertFalse(r['requiere_revision'])
        self.assertTrue(r['tiene_sugerencias'])

    def test_alias_sanitaria_no_genera_conflicto_artificial(self):
        evidencia = clasificar_evidencias('INSTALACION SANITARIA\nISOMETRICO')
        modelo = {'objetivos': {'disciplinas': {'etiquetas': ['sanitarias']}}}
        self.assertFalse(combinar(modelo, evidencia)['requiere_revision'])

    def test_titulos_y_espacios_clasifican_sin_nombre_de_archivo(self):
        arquitectura = clasificar_evidencias(
            'PLANTA AZOTEA\nTERRAZA\nHALL\nBAÑO\nCUARTO DE MAQUINAS'
        )
        electricidad = clasificar_evidencias(
            'PLANTA 2 PISO\nREDES DE TOMACORRIENTES Y COMUNICACIONES\nTABLERO GENERAL'
        )
        self.assertIn('arquitectura', arquitectura['objetivos']['disciplinas']['etiquetas'])
        self.assertFalse(arquitectura['requiere_revision'])
        self.assertIn('electricidad', electricidad['objetivos']['disciplinas']['etiquetas'])
