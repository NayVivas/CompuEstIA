"""Proveedor multimodal desacoplado para el modo asistido."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import os
from pathlib import Path
from typing import Protocol

from computos.ia.esquemas import AnalisisEstructuralIA


MODELO_PREDETERMINADO = "gpt-6-sol"


class ConfiguracionIAError(RuntimeError):
    """La integración no tiene las credenciales o dependencias necesarias."""


class ProveedorIAError(RuntimeError):
    """El proveedor no pudo producir una respuesta estructurada."""


@dataclass(frozen=True)
class RespuestaProveedor:
    analisis: AnalisisEstructuralIA
    proveedor: str
    modelo: str
    respuesta_id: str | None
    tokens_entrada: int | None
    tokens_salida: int | None


class ProveedorEstructural(Protocol):
    def analizar_pdf(self, ruta_pdf: Path) -> RespuestaProveedor:
        """Interpreta el PDF sin ejecutar cálculos métricos."""


INSTRUCCIONES = """
Sos un asistente de ingeniería civil especializado exclusivamente en planos
estructurales. Analizá el PDF completo y extraé solo información que esté
visible o escrita en el documento.

Reglas obligatorias:
1. No inventes referencias, dimensiones, cantidades ni armaduras.
2. No completes datos usando prácticas habituales de obra.
3. Si un valor no aparece o es ambiguo, devolvé null y marcá revisión.
4. Indicá páginas usando numeración humana desde 1.
5. Cada dato importante debe conservar evidencia textual visible.
6. Convertí a metros únicamente las cotas explícitas en cm o mm.
7. No calcules volúmenes, pesos de acero ni áreas de encofrado.
8. Separá la referencia del elemento de su cantidad y dimensiones.
9. Si el documento no es estructural, no extraigas elementos.
10. Una confianza alta exige referencia, dimensiones y evidencia coherentes.

El resultado será revisado por un profesional y luego consumido por un motor
determinístico de cómputos.
""".strip()


class ProveedorOpenAIEstructural:
    """Implementación mediante Responses API y Structured Outputs."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv("OPENAI_API_KEY", "")
        ).strip()
        self.model = (
            model
            or os.getenv(
                "COMPUTOESTIA_IA_MODEL",
                MODELO_PREDETERMINADO,
            )
        ).strip()

        if not self.api_key:
            raise ConfiguracionIAError(
                "Falta configurar OPENAI_API_KEY para activar el modo asistido."
            )

        try:
            from openai import OpenAI
        except ImportError as error:
            raise ConfiguracionIAError(
                "Falta instalar la dependencia 'openai'."
            ) from error

        self._client = OpenAI(api_key=self.api_key)

    def analizar_pdf(self, ruta_pdf: Path) -> RespuestaProveedor:
        contenido = base64.b64encode(
            ruta_pdf.read_bytes()
        ).decode("ascii")

        try:
            respuesta = self._client.responses.parse(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": INSTRUCCIONES,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_file",
                                "filename": ruta_pdf.name,
                                "file_data": (
                                    "data:application/pdf;base64,"
                                    f"{contenido}"
                                ),
                                "detail": "high",
                            },
                            {
                                "type": "input_text",
                                "text": (
                                    "Clasificá el documento y extraé sus "
                                    "elementos estructurales con evidencia."
                                ),
                            },
                        ],
                    },
                ],
                text_format=AnalisisEstructuralIA,
                store=False,
            )
        except Exception as error:
            raise ProveedorIAError(
                "La API multimodal no pudo analizar el plano."
            ) from error

        analisis = getattr(
            respuesta,
            "output_parsed",
            None,
        )
        if analisis is None:
            raise ProveedorIAError(
                "La API no devolvió un resultado estructurado utilizable."
            )

        uso = getattr(respuesta, "usage", None)
        return RespuestaProveedor(
            analisis=analisis,
            proveedor="openai",
            modelo=self.model,
            respuesta_id=getattr(respuesta, "id", None),
            tokens_entrada=getattr(uso, "input_tokens", None),
            tokens_salida=getattr(uso, "output_tokens", None),
        )
