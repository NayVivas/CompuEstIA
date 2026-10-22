"""Pruebas del modo asistido sin consumir la API externa."""

from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from computos.ia.esquemas import (
    AnalisisEstructuralIA,
    DimensionesEstructurales,
    ElementoEstructuralExtraido,
    EvidenciaPlano,
)
from computos.ia.proveedor import (
    ConfiguracionIAError,
    ProveedorOpenAIEstructural,
    RespuestaProveedor,
)
from computos.ia.servicio import analizar_pdf_estructural


class ProveedorFalso:
    def __init__(self, analisis):
        self.analisis = analisis

    def analizar_pdf(self, _ruta_pdf):
        return RespuestaProveedor(
            analisis=self.analisis,
            proveedor="falso",
            modelo="prueba",
            respuesta_id="respuesta-prueba",
            tokens_entrada=100,
            tokens_salida=25,
        )


def _analisis(confianza=0.95, evidencias=None):
    return AnalisisEstructuralIA(
        es_plano_estructural=True,
        tipo_documento="planta_fundaciones",
        elementos=[
            ElementoEstructuralExtraido(
                tipo="fundacion",
                referencia=" f1 ",
                cantidad=4,
                pagina=1,
                dimensiones=DimensionesEstructurales(
                    ancho_m=1.4,
                    largo_m=1.4,
                    altura_m=0.35,
                    diametro_m=None,
                ),
                armaduras=[],
                evidencias=(
                    evidencias
                    if evidencias is not None
                    else [
                        EvidenciaPlano(
                            pagina=1,
                            texto="F1 1.40 x 1.40 x 0.35",
                            descripcion="Fila del cuadro de fundaciones",
                        )
                    ]
                ),
                confianza=confianza,
                requiere_revision=False,
                observaciones=[],
            )
        ],
        advertencias=[],
        resumen="Plano estructural con fundaciones.",
    )


class IaGenerativaTests(unittest.TestCase):
    def _crear_pdf(self, carpeta):
        ruta = Path(carpeta) / "plano.pdf"
        ruta.write_bytes(b"%PDF-prueba")
        return ruta

    def test_normaliza_referencia_y_no_realiza_calculos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = analizar_pdf_estructural(
                self._crear_pdf(carpeta),
                proveedor=ProveedorFalso(_analisis()),
            )

        elemento = resultado["elementos_extraidos"][0]
        self.assertEqual(elemento["referencia"], "F1")
        self.assertFalse(resultado["calculos_realizados_por_ia"])
        self.assertTrue(resultado["requiere_revision_profesional"])
        self.assertTrue(resultado["validacion_ia"]["calculos_habilitados"])

    def test_baja_confianza_y_sin_evidencia_exigen_revision(self):
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = analizar_pdf_estructural(
                self._crear_pdf(carpeta),
                proveedor=ProveedorFalso(
                    _analisis(
                        confianza=0.55,
                        evidencias=[],
                    )
                ),
            )

        elemento = resultado["elementos_extraidos"][0]
        self.assertTrue(elemento["requiere_revision"])
        self.assertIn(
            "sin_evidencia",
            elemento["motivos_revision_deterministica"],
        )
        self.assertFalse(resultado["validacion_ia"]["calculos_habilitados"])

    def test_esquema_rechaza_confianza_fuera_de_rango(self):
        with self.assertRaises(ValidationError):
            _analisis(confianza=1.5)

    def test_proveedor_real_exige_clave(self):
        with self.assertRaisesRegex(
            ConfiguracionIAError,
            "OPENAI_API_KEY",
        ):
            ProveedorOpenAIEstructural(api_key="")

    def test_proveedor_envia_pdf_y_solicita_salida_tipadas(self):
        llamadas = []

        class RespuestasFalsas:
            def parse(self, **datos):
                llamadas.append(datos)
                return SimpleNamespace(
                    output_parsed=_analisis(),
                    id="respuesta-ia",
                    usage=SimpleNamespace(
                        input_tokens=150,
                        output_tokens=40,
                    ),
                )

        class ClienteFalso:
            def __init__(self, **_datos):
                self.responses = RespuestasFalsas()

        modulo_falso = SimpleNamespace(
            OpenAI=ClienteFalso,
        )

        with (
            tempfile.TemporaryDirectory() as carpeta,
            patch.dict(
                sys.modules,
                {"openai": modulo_falso},
            ),
        ):
            proveedor = ProveedorOpenAIEstructural(
                api_key="clave-de-prueba",
                model="modelo-de-prueba",
            )
            respuesta = proveedor.analizar_pdf(
                self._crear_pdf(carpeta)
            )

        self.assertEqual(respuesta.modelo, "modelo-de-prueba")
        self.assertEqual(respuesta.tokens_entrada, 150)
        self.assertEqual(len(llamadas), 1)
        llamada = llamadas[0]
        self.assertFalse(llamada["store"])
        self.assertIs(
            llamada["text_format"],
            AnalisisEstructuralIA,
        )
        archivo = llamada["input"][1]["content"][0]
        self.assertEqual(archivo["type"], "input_file")
        self.assertEqual(archivo["detail"], "high")
        self.assertTrue(
            archivo["file_data"].startswith(
                "data:application/pdf;base64,"
            )
        )


if __name__ == "__main__":
    unittest.main()
