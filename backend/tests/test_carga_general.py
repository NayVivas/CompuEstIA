"""Contratos generales con PDFs generados: no dependen de planos de ejemplo."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pymupdf
from fastapi.testclient import TestClient
from computos.api import aplicacion
from computos.api.servicio import _seleccionar_configuracion
from computos.ia.enrutador_documentos import enrutar_documentos
from computos.ia.clasificador_exp19 import extraer_texto_nativo_pdf


class SinModelo:
    def clasificar_texto(self, texto):
        return {"objetivos": {}, "estado": "sin_modelo"}


def pdf_bytes(texto="", rotacion=0):
    with pymupdf.open() as pdf:
        pagina = pdf.new_page()
        if texto:
            pagina.insert_text((40, 60), texto)
        pagina.set_rotation(rotacion)
        return pdf.tobytes()


class CargaGeneralTests(unittest.TestCase):
    def setUp(self):
        self.temporal = TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        self.client = TestClient(aplicacion.app)

    def archivos(self):
        textos = ["PLANTA DE CIMENTACIONES", "CUADRO DE ZAPATAS", "PLANILLA DE PILARES", "INSTALACION SANITARIA"]
        rutas = {}
        for i, texto in enumerate(textos, 1):
            ruta = self.raiz / f"archivo-{i}.pdf"
            ruta.write_bytes(pdf_bytes(texto, 270 if i == 2 else 0))
            rutas[f"doc-{i:03d}"] = ruta
        return rutas

    def test_contenido_no_nombres_y_mas_de_tres_archivos(self):
        rutas = self.archivos()
        resultado = enrutar_documentos(rutas, nombres={i: "Fundaciones_1.pdf" for i in rutas}, clasificador=SinModelo())
        self.assertEqual(resultado.asignaciones_sugeridas, {"planta": "doc-001", "detalles": "doc-002", "columnas": "doc-003"})
        self.assertTrue(resultado.listo)
        confirmado = enrutar_documentos(rutas, asignaciones=resultado.asignaciones_sugeridas, clasificador=SinModelo())
        self.assertTrue(confirmado.listo)
        self.assertNotIn("doc-004", confirmado.asignaciones.values())
        self.assertEqual(confirmado.rutas_por_rol()["detalles"], rutas["doc-002"])

    def test_ambiguedad_no_elige_primero(self):
        rutas = self.archivos()
        rutas["doc-004"].write_bytes(pdf_bytes("PLANTA DE CIMENTACIONES"))
        resultado = enrutar_documentos(rutas, clasificador=SinModelo())
        self.assertNotIn("planta", resultado.asignaciones_sugeridas)
        self.assertFalse(resultado.listo)

    def test_pdf_vacio_y_roto_no_se_asignan(self):
        for contenido in [pdf_bytes(), b"%PDF-invalido"]:
            ruta = self.raiz / "plano.pdf"; ruta.write_bytes(contenido)
            resultado = enrutar_documentos({"doc-001": ruta}, clasificador=SinModelo())
            self.assertFalse(resultado.listo)
            self.assertTrue(resultado.documentos[0]["advertencias"] or resultado.documentos[0]["paginas"][0]["advertencias"])
            self.assertFalse(enrutar_documentos({"doc-001": ruta}, asignaciones={"planta": "doc-001"}, clasificador=SinModelo()).listo)

    def test_asignacion_inexistente(self):
        with self.assertRaises(ValueError):
            enrutar_documentos(self.archivos(), asignaciones={"planta": "doc-099"}, clasificador=SinModelo())

    def test_pdf_sin_texto_no_clasifica_marcador_artificial(self):
        ruta = self.raiz / "vacio.pdf"; ruta.write_bytes(pdf_bytes())
        texto, metadatos = extraer_texto_nativo_pdf(ruta)
        self.assertEqual(texto, "")
        self.assertEqual(metadatos["paginas_con_texto_nativo"], 0)

    def test_no_hereda_correcciones_del_ejemplo(self):
        config, automatico = _seleccionar_configuracion(self.archivos())
        self.assertFalse(automatico)
        self.assertEqual(config.correcciones_referencias_cuadro, {})
        self.assertEqual(config.correcciones_columnas_fundaciones, {})

    def test_api_revision_y_error_no_producen_completado(self):
        rutas = self.archivos()
        cargas = [("archivos", (r.name, r.read_bytes(), "application/pdf")) for r in rutas.values()]
        respuesta = self.client.post("/api/analisis/automatico/", files=cargas)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "clasificacion_documental")
        self.assertNotIn("resultado", respuesta.json())
        asignaciones = {"planta": "doc-001", "detalles": "doc-002", "columnas": "doc-003"}
        for error in [ValueError("No se reconoce una dimensión del elemento Z27"), RuntimeError("detalle interno secreto")]:
            with patch.object(aplicacion, "procesar_archivos_hibrido", side_effect=error):
                respuesta = self.client.post("/api/analisis/automatico/", files=cargas, data={"asignaciones": json.dumps(asignaciones), "ejecutar_computo": "true"})
            body = respuesta.json()
            self.assertEqual(body["estado"], "requiere_revision")
            self.assertFalse(body["resultado"]["computos_disponibles"])
            self.assertNotIn("volumen_hormigon_m3", body["resultado"])
            self.assertNotIn("detalle interno secreto", respuesta.text)
            self.assertEqual(self.client.get(f"/api/analisis/{body['analisis_id']}/resultados/").json(), body)

    def test_documentar_no_desbloquea_y_persiste(self):
        body = aplicacion._respuesta_incidencia(ValueError("Dimensiones contradictorias"), "computo")
        incidencia_id = body["resultado"]["incidencias"][0]["id"]
        url = f"/api/analisis/{body['analisis_id']}/incidencias/{incidencia_id}/documentar"
        with patch.object(aplicacion, "DATA_DIR", self.raiz):
            respuesta = self.client.post(url, json={"revisor": "Profesional", "motivo": "Consultar dimensiones en el plano firmado"})
        self.assertEqual(respuesta.json()["estado"], "requiere_revision")
        self.assertTrue(respuesta.json()["resultado"]["incidencias"][0]["bloqueante"])
        self.assertEqual(len(list((self.raiz / "revisiones_incidencias").glob("*.json"))), 1)
        self.assertEqual(self.client.post(url, json={"revisor": "  ", "motivo": " " * 12}).status_code, 422)

    def test_revision_real_de_referencia_distinta_de_f12(self):
        from computos.configuracion.proyecto import ConfiguracionProyecto
        from computos.fundaciones.revision_cuadro import preparar_revision_cuadro, RevisionCuadroRequerida, guardar_revision_cuadro
        rutas = {}
        for rol in ("planta", "detalles", "columnas"):
            ruta = self.raiz / f"documento-{rol}.pdf"; rutas[rol] = ruta
            with pymupdf.open() as pdf:
                pagina = pdf.new_page()
                if rol == "detalles":
                    pagina.insert_text((20, 30), "CUADRO DE ZAPATAS")
                    for x, texto in [(20, "REF."), (110, "X"), (210, "Y"), (310, "H")]:
                        pagina.insert_text((x, 60), texto)
                    for y in (90, 130):
                        for x, texto in [(20, "Z-01"), (110, "1.40"), (210, "1.60"), (310, "0.45")]:
                            pagina.insert_text((x, y), texto)
                else:
                    pagina.insert_text((30, 60), "PLANTA DE ZAPATAS Z-01 Z-02")
                pdf.save(ruta)
        with patch("computos.fundaciones.revision_cuadro.DIRECTORIO_REVISIONES", self.raiz / "revisiones"):
            with self.assertRaises(RevisionCuadroRequerida) as capturada:
                preparar_revision_cuadro(rutas, ConfiguracionProyecto.vacia(), proyecto_id="nuevo")
            revision = capturada.exception.revision
            self.assertEqual(revision["duplicadas"], {"Z1": 2})
            self.assertEqual(len(revision["filas"]), 2)
            decision = {"huellas_archivos": revision["huellas_archivos"], "revisor": "Profesional de ensayo", "correcciones_referencias_cuadro": [{"referencia_original": "Z1", "aparicion": 2, "referencia_correcta": "Z2", "motivo": "La segunda fila corresponde a Z2 según la planta"}]}
            config, registro, destino = preparar_revision_cuadro(rutas, ConfiguracionProyecto.vacia(), decision, "nuevo")
            self.assertEqual(config.correcciones_referencias_cuadro, {("Z1", 2): "Z2"})
            self.assertFalse(destino.exists())
            guardar_revision_cuadro(destino, registro)
            config, _, _ = preparar_revision_cuadro(rutas, ConfiguracionProyecto.vacia(), proyecto_id="nuevo")
            self.assertEqual(config.correcciones_referencias_cuadro, {("Z1", 2): "Z2"})
            with self.assertRaises(RevisionCuadroRequerida):
                preparar_revision_cuadro(rutas, ConfiguracionProyecto.vacia(), proyecto_id="otro-proyecto")
