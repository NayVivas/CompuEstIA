"""Configuración auditable para particularidades de un proyecto.

El motor de lectura no contiene correcciones de rótulos concretos. Cuando un
plano tiene un error conocido, la corrección se declara en un JSON externo y
se carga explícitamente desde la línea de comandos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from computos.referencias import interpretar_referencia


@dataclass(slots=True)
class ConfiguracionProyecto:
    """Particularidades documentadas de un juego de planos."""

    nombre: str | None = None
    ruta: Path | None = None
    archivos_esperados: dict[str, str] = field(default_factory=dict)
    correcciones_referencias_cuadro: dict[tuple[str, int], str] = field(
        default_factory=dict
    )
    motivos_referencias_cuadro: dict[tuple[str, int], str] = field(
        default_factory=dict
    )
    correcciones_columnas_fundaciones: dict[str, str] = field(
        default_factory=dict
    )
    motivos_columnas_fundaciones: dict[str, str] = field(default_factory=dict)
    reasignaciones_detalles_columnas: list[dict] = field(
        default_factory=list
    )
    selecciones_fuentes_columnas: list[dict] = field(default_factory=list)
    secciones_manuales_columnas: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def vacia(cls) -> "ConfiguracionProyecto":
        """Crea una configuración sin excepciones específicas."""

        return cls()

    def validar_archivos(
        self,
        *,
        planta: str | Path,
        detalles: str | Path,
        columnas: str | Path | None = None,
    ) -> None:
        """Evita aplicar por accidente una configuración a otros planos."""

        recibidos = {
            "planta": Path(planta).name,
            "detalles": Path(detalles).name,
        }
        if columnas is not None:
            recibidos["columnas"] = Path(columnas).name

        diferencias = []
        for tipo, esperado in self.archivos_esperados.items():
            recibido = recibidos.get(tipo)
            if recibido is not None and recibido.casefold() != esperado.casefold():
                diferencias.append(
                    f"{tipo}: se esperaba {esperado!r} y se recibió {recibido!r}"
                )

        if diferencias:
            raise ValueError(
                "La configuración de proyecto no corresponde a los archivos "
                "seleccionados. " + "; ".join(diferencias)
            )

    def a_diccionario(self) -> dict:
        """Devuelve una representación serializable para los reportes."""

        correcciones_referencias = []
        for clave, nueva in self.correcciones_referencias_cuadro.items():
            original, aparicion = clave
            correcciones_referencias.append(
                {
                    "referencia_original": original,
                    "aparicion": aparicion,
                    "referencia_correcta": nueva,
                    "motivo": self.motivos_referencias_cuadro[clave],
                }
            )

        correcciones_columnas = []
        for original, nueva in self.correcciones_columnas_fundaciones.items():
            correcciones_columnas.append(
                {
                    "referencia_original": original,
                    "referencia_correcta": nueva,
                    "motivo": self.motivos_columnas_fundaciones[original],
                }
            )

        return {
            "nombre": self.nombre,
            "archivo_configuracion": self.ruta.name if self.ruta else None,
            "archivos_esperados": dict(self.archivos_esperados),
            "correcciones_referencias_cuadro": correcciones_referencias,
            "correcciones_columnas_fundaciones": correcciones_columnas,
            "reasignaciones_detalles_columnas": [
                dict(reasignacion)
                for reasignacion in self.reasignaciones_detalles_columnas
            ],
            "selecciones_fuentes_columnas": [
                dict(seleccion) for seleccion in self.selecciones_fuentes_columnas
            ],
            "secciones_manuales_columnas": [
                {"referencia": referencia, **dict(datos)}
                for referencia, datos in self.secciones_manuales_columnas.items()
            ],
        }


def _normalizar_referencia(valor: Any, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{campo} debe ser un texto no vacío.")

    referencia = interpretar_referencia(valor)
    if referencia is None:
        raise ValueError(f"{campo} contiene una referencia inválida: {valor!r}.")
    return referencia.canonica


def _leer_motivo(registro: dict, campo: str) -> str:
    motivo = registro.get("motivo")
    if not isinstance(motivo, str) or not motivo.strip():
        raise ValueError(
            f"{campo} debe incluir un motivo para que la corrección sea auditable."
        )
    return motivo.strip()


def _leer_lista(datos: dict, campo: str) -> list:
    valor = datos.get(campo, [])
    if not isinstance(valor, list):
        raise ValueError(f"{campo} debe ser una lista.")
    return valor


def interpretar_configuracion_proyecto(
    datos: Any,
    *,
    ruta: str | Path | None = None,
) -> ConfiguracionProyecto:
    """Valida el contenido ya decodificado de una configuración JSON."""

    if not isinstance(datos, dict):
        raise ValueError("La configuración de proyecto debe ser un objeto JSON.")

    nombre = datos.get("nombre")
    if nombre is not None and (not isinstance(nombre, str) or not nombre.strip()):
        raise ValueError("nombre debe ser un texto no vacío cuando se informa.")

    archivos_esperados_datos = datos.get("archivos_esperados", {})
    if not isinstance(archivos_esperados_datos, dict):
        raise ValueError("archivos_esperados debe ser un objeto JSON.")
    # Trabajamos con una copia para no modificar el diccionario recibido por
    # quien invoque esta función.
    archivos_esperados = dict(archivos_esperados_datos)
    tipos_archivo = {"planta", "detalles", "columnas"}
    desconocidos = set(archivos_esperados) - tipos_archivo
    if desconocidos:
        raise ValueError(
            "Tipos desconocidos en archivos_esperados: "
            + ", ".join(sorted(desconocidos))
        )
    for tipo, archivo in archivos_esperados.items():
        if not isinstance(archivo, str) or not Path(archivo).name:
            raise ValueError(f"El archivo esperado para {tipo} no es válido.")
        archivos_esperados[tipo] = Path(archivo).name

    correcciones_referencias: dict[tuple[str, int], str] = {}
    motivos_referencias: dict[tuple[str, int], str] = {}
    for posicion, registro in enumerate(
        _leer_lista(datos, "correcciones_referencias_cuadro"),
        start=1,
    ):
        campo = f"correcciones_referencias_cuadro[{posicion}]"
        if not isinstance(registro, dict):
            raise ValueError(f"{campo} debe ser un objeto JSON.")
        original = _normalizar_referencia(
            registro.get("referencia_original"),
            f"{campo}.referencia_original",
        )
        nueva = _normalizar_referencia(
            registro.get("referencia_correcta"),
            f"{campo}.referencia_correcta",
        )
        aparicion = registro.get("aparicion")
        if (
            isinstance(aparicion, bool)
            or not isinstance(aparicion, int)
            or aparicion < 1
        ):
            raise ValueError(f"{campo}.aparicion debe ser un entero mayor que cero.")
        clave = (original, aparicion)
        if clave in correcciones_referencias:
            raise ValueError(
                f"La corrección de {original}, aparición {aparicion}, está repetida."
            )
        correcciones_referencias[clave] = nueva
        motivos_referencias[clave] = _leer_motivo(registro, campo)

    correcciones_columnas: dict[str, str] = {}
    motivos_columnas: dict[str, str] = {}
    for posicion, registro in enumerate(
        _leer_lista(datos, "correcciones_columnas_fundaciones"),
        start=1,
    ):
        campo = f"correcciones_columnas_fundaciones[{posicion}]"
        if not isinstance(registro, dict):
            raise ValueError(f"{campo} debe ser un objeto JSON.")
        original = _normalizar_referencia(
            registro.get("referencia_original"),
            f"{campo}.referencia_original",
        )
        nueva = _normalizar_referencia(
            registro.get("referencia_correcta"),
            f"{campo}.referencia_correcta",
        )
        if original in correcciones_columnas:
            raise ValueError(f"La corrección de columna {original} está repetida.")
        correcciones_columnas[original] = nueva
        motivos_columnas[original] = _leer_motivo(registro, campo)

    reasignaciones_detalles_columnas = []
    claves_reasignaciones = set()
    for posicion, registro in enumerate(
        _leer_lista(datos, "reasignaciones_detalles_columnas"),
        start=1,
    ):
        campo = f"reasignaciones_detalles_columnas[{posicion}]"
        if not isinstance(registro, dict):
            raise ValueError(f"{campo} debe ser un objeto JSON.")
        rol = str(registro.get("rol") or "").strip().lower()
        if rol not in {"detalles", "columnas"}:
            raise ValueError(
                f"{campo}.rol debe ser detalles o columnas."
            )
        pagina = registro.get("pagina")
        if (
            isinstance(pagina, bool)
            or not isinstance(pagina, int)
            or pagina < 1
        ):
            raise ValueError(
                f"{campo}.pagina debe ser un entero mayor que cero."
            )
        original = _normalizar_referencia(
            registro.get("referencia_original"),
            f"{campo}.referencia_original",
        )
        nueva = _normalizar_referencia(
            registro.get("referencia_correcta"),
            f"{campo}.referencia_correcta",
        )
        if original == nueva:
            raise ValueError(
                f"{campo}: la referencia corregida debe ser distinta."
            )
        clave = (rol, pagina, original)
        if clave in claves_reasignaciones:
            raise ValueError(
                f"{campo}: la reasignación está repetida."
            )
        claves_reasignaciones.add(clave)
        reasignacion = {
            "rol": rol,
            "pagina": pagina,
            "referencia_original": original,
            "referencia_correcta": nueva,
            "motivo": _leer_motivo(registro, campo),
        }
        revisor = registro.get("revisor")
        if revisor is not None:
            if not isinstance(revisor, str) or len(revisor.strip()) < 2:
                raise ValueError(
                    f"{campo}.revisor debe identificar al profesional."
                )
            reasignacion["revisor"] = revisor.strip()
        reasignaciones_detalles_columnas.append(reasignacion)

    return ConfiguracionProyecto(
        nombre=nombre.strip() if isinstance(nombre, str) else None,
        ruta=Path(ruta) if ruta is not None else None,
        archivos_esperados=dict(archivos_esperados),
        correcciones_referencias_cuadro=correcciones_referencias,
        motivos_referencias_cuadro=motivos_referencias,
        correcciones_columnas_fundaciones=correcciones_columnas,
        motivos_columnas_fundaciones=motivos_columnas,
        reasignaciones_detalles_columnas=(
            reasignaciones_detalles_columnas
        ),
    )


def cargar_configuracion_proyecto(
    ruta: str | Path | None,
) -> ConfiguracionProyecto:
    """Carga una configuración; sin ruta usa reglas generales únicamente."""

    if ruta is None:
        return ConfiguracionProyecto.vacia()

    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(
            f"No existe el archivo de configuración de proyecto: {ruta}"
        )

    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"El archivo de configuración no contiene JSON válido: {ruta}"
        ) from error

    return interpretar_configuracion_proyecto(datos, ruta=ruta)
