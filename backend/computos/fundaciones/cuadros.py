"""Lectura geométrica y semántica de cuadros de fundaciones.

El módulo trabaja siempre con coordenadas visuales normalizadas. De esa forma,
la orientación interna del PDF no cambia la manera de encontrar encabezados,
filas y celdas. Los nombres concretos del plano se traducen a campos semánticos
como ``X``, ``Y``, ``H`` o ``ARMADURA`` mediante conjuntos de alias.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Iterable
import re

from computos.documentos.modelos import Caja, PalabraNormalizada
from computos.referencias import (
    ALIAS_ENCABEZADO_REFERENCIA,
    CatalogoReferencias,
    normalizar_etiqueta,
    LecturaCuadroNoCompatible,
)


CAMPO_REFERENCIA = "REFERENCIA"
CAMPO_X = "X"
CAMPO_Y = "Y"
CAMPO_H = "H"
CAMPO_ARMADURA = "ARMADURA"
CAMPO_ARMADURA_SUPERIOR = "ARMADURA_SUPERIOR"
CAMPO_ARMADURA_INFERIOR = "ARMADURA_INFERIOR"
CAMPO_PEDESTAL = "PEDESTAL"


ALIAS_CAMPOS_CUADRO: dict[str, set[str]] = {
    CAMPO_REFERENCIA: set(ALIAS_ENCABEZADO_REFERENCIA)
    | {
        "TIPODEFUNDACION",
        "TIPODEZAPATA",
        "ZAPATA",
    },
    CAMPO_X: {
        "X",
        "LX",
        "A",
        "L",
        "LARGO",
        "LONGITUD",
        "DIMX",
        "DIMENSIONX",
        "DIMENSIONESX",
        "BASEX",
        "LADOX",
    },
    CAMPO_Y: {
        "Y",
        "LY",
        "B",
        "ANCHO",
        "DIMY",
        "DIMENSIONY",
        "DIMENSIONESY",
        "BASEY",
        "LADOY",
    },
    CAMPO_H: {
        "H",
        "HZ",
        "E",
        "ESP",
        "ESPESOR",
        "ALTURA",
        "CANTO",
        "PERALTE",
        "PROFUNDIDAD",
    },
    CAMPO_ARMADURA: {
        "ARMADURA",
        "ARMADO",
        "ACERO",
        "REFUERZO",
        "HIERRO",
        "MALLA",
    },
    CAMPO_ARMADURA_SUPERIOR: {
        "ARMADURASUPERIOR",
        "ACEROSUPERIOR",
        "MALLASUPERIOR",
        "REFUERZOSUPERIOR",
        "SUP",
    },
    CAMPO_ARMADURA_INFERIOR: {
        "ARMADURAINFERIOR",
        "ACEROINFERIOR",
        "MALLAINFERIOR",
        "REFUERZOINFERIOR",
        "INF",
    },
    CAMPO_PEDESTAL: {
        "PEDESTAL",
        "DADO",
        "ARRANQUE",
        "COLUMNA",
        "PILAR",
    },
    "CANTIDAD": {
        "CANT",
        "CANTIDAD",
        "UNIDADES",
    },
    "DESCRIPCION": {
        "DESCRIPCION",
        "UBICACION",
        "POSICION",
    },
    "HORMIGON": {
        "HORMIGON",
        "CONCRETO",
        "MATERIAL",
    },
    "OBSERVACIONES": {
        "OBS",
        "OBSERVACION",
        "OBSERVACIONES",
        "NOTA",
        "NOTAS",
    },
}

ALIAS_UNIDADES = {
    "m": {
        "M",
        "MT",
        "MTS",
        "METRO",
        "METROS",
    },
    "cm": {
        "CM",
        "CMS",
        "CENTIMETRO",
        "CENTIMETROS",
    },
    "mm": {
        "MM",
        "MMS",
        "MILIMETRO",
        "MILIMETROS",
    },
}

PATRON_NUMERO = re.compile(
    r"(?<![\d/])(?:\d+(?:[.,]\d+)?|[.,]\d+)(?![\d/])"
)


@dataclass(frozen=True, slots=True)
class EncabezadoCuadro:
    """Encabezado original asociado con un campo semántico."""

    campo: str
    texto_original: str
    pagina: int
    caja_visual: Caja
    palabras: tuple[PalabraNormalizada, ...]
    unidad: str | None = None

    @property
    def centro_x(self) -> float:
        return _centro_x(self.caja_visual)

    @property
    def centro_y(self) -> float:
        return _centro_y(self.caja_visual)


@dataclass(slots=True)
class CeldaCuadro:
    """Contenido de una celda, conservando las palabras que lo originaron."""

    campo: str
    texto: str
    palabras: list[PalabraNormalizada] = field(default_factory=list)


@dataclass(slots=True)
class FilaCuadro:
    """Fila detectada a partir de la posición de su referencia."""

    numero_fila: int
    referencia: str
    referencia_texto: str
    centro_y_visual: float
    limite_superior_visual: float
    limite_inferior_visual: float
    celdas: dict[str, CeldaCuadro] = field(default_factory=dict)


@dataclass(slots=True)
class CuadroFundaciones:
    """Representación de un cuadro independiente de su rotación y etiquetas."""

    pagina: int
    encabezados: dict[str, EncabezadoCuadro]
    filas: list[FilaCuadro]
    confianza: str
    advertencias: list[str] = field(default_factory=list)

    def a_diccionario(self) -> dict:
        """Devuelve una versión breve y serializable para control del usuario."""

        return {
            "pagina": self.pagina,
            "confianza": self.confianza,
            "advertencias": list(self.advertencias),
            "encabezados": {
                campo: {
                    "texto_original": encabezado.texto_original,
                    "unidad": encabezado.unidad,
                    "centro_x_visual": round(encabezado.centro_x, 3),
                    "centro_y_visual": round(encabezado.centro_y, 3),
                }
                for campo, encabezado in self.encabezados.items()
            },
            "filas": [
                {
                    "numero_fila": fila.numero_fila,
                    "referencia": fila.referencia,
                    "referencia_texto": fila.referencia_texto,
                    "celdas": {
                        campo: celda.texto
                        for campo, celda in fila.celdas.items()
                    },
                }
                for fila in self.filas
            ],
        }


@dataclass(frozen=True, slots=True)
class _CandidatoEncabezado:
    campo: str
    palabras: tuple[PalabraNormalizada, ...]
    caja_visual: Caja
    puntaje: float


def _centro_x(caja: Caja) -> float:
    return (caja.x0 + caja.x1) / 2


def _centro_y(caja: Caja) -> float:
    return (caja.y0 + caja.y1) / 2


def _union_cajas(cajas: Iterable[Caja]) -> Caja:
    cajas = tuple(cajas)
    return Caja(
        x0=min(caja.x0 for caja in cajas),
        y0=min(caja.y0 for caja in cajas),
        x1=max(caja.x1 for caja in cajas),
        y1=max(caja.y1 for caja in cajas),
    )


def _misma_linea(
    primera: PalabraNormalizada,
    segunda: PalabraNormalizada,
) -> bool:
    altura = max(
        primera.caja_visual.alto,
        segunda.caja_visual.alto,
        1.0,
    )
    diferencia_y = abs(
        _centro_y(primera.caja_visual)
        - _centro_y(segunda.caja_visual)
    )
    espacio = segunda.caja_visual.x0 - primera.caja_visual.x1
    return diferencia_y <= altura * 0.8 and -altura <= espacio <= altura * 5


def _buscar_encabezado_referencia(
    palabras: list[PalabraNormalizada],
    catalogo: CatalogoReferencias,
) -> PalabraNormalizada:
    if catalogo.palabra_encabezado is not None:
        return catalogo.palabra_encabezado
    primera_fila_y = min(
        _centro_y(candidato.caja_visual)
        for candidato in catalogo.referencias
    )
    centro_referencias_x = median(
        _centro_x(candidato.caja_visual)
        for candidato in catalogo.referencias
    )
    candidatos = [
        palabra
        for palabra in palabras
        if palabra.pagina == catalogo.pagina
        and normalizar_etiqueta(palabra.texto)
        in ALIAS_CAMPOS_CUADRO[CAMPO_REFERENCIA]
        and _centro_y(palabra.caja_visual) < primera_fila_y
    ]
    if not candidatos:
        raise ValueError(
            "No se pudo recuperar la posición visual del encabezado de referencias."
        )

    return min(
        candidatos,
        key=lambda palabra: (
            abs(_centro_x(palabra.caja_visual) - centro_referencias_x) * 2
            + primera_fila_y
            - _centro_y(palabra.caja_visual)
        ),
    )


def _crear_candidatos_encabezados(
    palabras: list[PalabraNormalizada],
    encabezado_referencia: PalabraNormalizada,
    primera_fila_y: float,
) -> list[_CandidatoEncabezado]:
    centro_y_encabezado = _centro_y(encabezado_referencia.caja_visual)
    altura = max(encabezado_referencia.caja_visual.alto, 1.0)
    limite_inferior = (centro_y_encabezado + primera_fila_y) / 2
    tolerancia_y = max(6.0, altura * 2.5)
    banda = [
        palabra
        for palabra in palabras
        if palabra.pagina == encabezado_referencia.pagina
        and abs(_centro_y(palabra.caja_visual) - centro_y_encabezado)
        <= tolerancia_y
        and _centro_y(palabra.caja_visual) < limite_inferior
    ]
    banda.sort(key=lambda palabra: palabra.caja_visual.x0)
    candidatos: list[_CandidatoEncabezado] = []

    for inicio in range(len(banda)):
        grupo: list[PalabraNormalizada] = []
        for cantidad in range(1, 5):
            posicion = inicio + cantidad - 1
            if posicion >= len(banda):
                break
            palabra = banda[posicion]
            if grupo and not _misma_linea(grupo[-1], palabra):
                break
            grupo.append(palabra)
            etiqueta_original = normalizar_etiqueta(
                " ".join(elemento.texto for elemento in grupo)
            )
            etiqueta, _unidad = _separar_etiqueta_y_unidad(
                etiqueta_original
            )

            for campo, alias in ALIAS_CAMPOS_CUADRO.items():
                if etiqueta not in alias:
                    continue
                caja = _union_cajas(
                    elemento.caja_visual
                    for elemento in grupo
                )
                puntaje = (
                    len(etiqueta) * 0.1
                    - len(grupo) * 0.05
                    - abs(_centro_y(caja) - centro_y_encabezado) * 2
                    - abs(
                        _centro_x(caja)
                        - _centro_x(encabezado_referencia.caja_visual)
                    ) * 0.01
                )
                candidatos.append(
                    _CandidatoEncabezado(
                        campo=campo,
                        palabras=tuple(grupo),
                        caja_visual=caja,
                        puntaje=puntaje,
                    )
                )

    return candidatos


def _seleccionar_encabezados(
    candidatos: list[_CandidatoEncabezado],
    encabezado_referencia: PalabraNormalizada,
) -> dict[str, EncabezadoCuadro]:
    mejores: dict[str, _CandidatoEncabezado] = {}
    for candidato in candidatos:
        existente = mejores.get(candidato.campo)
        if existente is None or candidato.puntaje > existente.puntaje:
            mejores[candidato.campo] = candidato

    # La ubicación de la referencia ya fue validada al descubrir el catálogo.
    mejores[CAMPO_REFERENCIA] = _CandidatoEncabezado(
        campo=CAMPO_REFERENCIA,
        palabras=(encabezado_referencia,),
        caja_visual=encabezado_referencia.caja_visual,
        puntaje=float("inf"),
    )

    return {
        campo: EncabezadoCuadro(
            campo=campo,
            texto_original=" ".join(
                palabra.texto
                for palabra in candidato.palabras
            ),
            pagina=encabezado_referencia.pagina,
            caja_visual=candidato.caja_visual,
            palabras=candidato.palabras,
        )
        for campo, candidato in mejores.items()
    }


def _limites_columnas(
    encabezados: dict[str, EncabezadoCuadro],
) -> dict[str, tuple[float, float]]:
    ordenados = sorted(
        encabezados.values(),
        key=lambda encabezado: encabezado.centro_x,
    )
    if len(ordenados) < 2:
        raise ValueError("No hay suficientes columnas reconocibles en el cuadro.")

    limites: dict[str, tuple[float, float]] = {}
    for indice, encabezado in enumerate(ordenados):
        if indice == 0:
            distancia = ordenados[1].centro_x - encabezado.centro_x
            izquierda = encabezado.centro_x - distancia / 2
        else:
            izquierda = (
                ordenados[indice - 1].caja_visual.x1
                + encabezado.caja_visual.x0
            ) / 2

        if indice == len(ordenados) - 1:
            distancia = encabezado.centro_x - ordenados[indice - 1].centro_x
            factor = (
                1.5
                if encabezado.campo
                in {
                    CAMPO_ARMADURA,
                    CAMPO_ARMADURA_SUPERIOR,
                    CAMPO_ARMADURA_INFERIOR,
                }
                else 0.5
            )
            derecha = encabezado.centro_x + distancia * factor
        else:
            derecha = (
                encabezado.caja_visual.x1
                + ordenados[indice + 1].caja_visual.x0
            ) / 2
        limites[encabezado.campo] = (izquierda, derecha)

    return limites


def _detectar_unidad(palabras: Iterable[PalabraNormalizada]) -> str | None:
    etiquetas = {
        normalizar_etiqueta(palabra.texto)
        for palabra in palabras
    }
    for unidad, alias in ALIAS_UNIDADES.items():
        if etiquetas & alias:
            return unidad
    for etiqueta in etiquetas:
        _base, unidad = _separar_etiqueta_y_unidad(etiqueta)
        if unidad is not None:
            return unidad
    return None


def _separar_etiqueta_y_unidad(
    etiqueta: str,
) -> tuple[str, str | None]:
    """Separa casos compactos como ``XCM``, ``ESPESORMM`` o ``140CM``."""

    sufijos = (
        ("MILIMETROS", "mm"),
        ("MILIMETRO", "mm"),
        ("CENTIMETROS", "cm"),
        ("CENTIMETRO", "cm"),
        ("METROS", "m"),
        ("METRO", "m"),
        ("MMS", "mm"),
        ("CMS", "cm"),
        ("MTS", "m"),
        ("MM", "mm"),
        ("CM", "cm"),
        ("M", "m"),
    )
    for sufijo, unidad in sufijos:
        if not etiqueta.endswith(sufijo) or etiqueta == sufijo:
            continue
        base = etiqueta[: -len(sufijo)]
        es_dimension_conocida = any(
            base in alias
            for campo, alias in ALIAS_CAMPOS_CUADRO.items()
            if campo in {CAMPO_X, CAMPO_Y, CAMPO_H}
        )
        if es_dimension_conocida or any(caracter.isdigit() for caracter in base):
            return base, unidad
    return etiqueta, None


def _completar_textos_y_unidades_encabezados(
    encabezados: dict[str, EncabezadoCuadro],
    limites: dict[str, tuple[float, float]],
    palabras: list[PalabraNormalizada],
) -> dict[str, EncabezadoCuadro]:
    referencia = encabezados[CAMPO_REFERENCIA]
    altura = max(referencia.caja_visual.alto, 1.0)
    tolerancia_y = max(2.0, altura * 0.8)
    resultado: dict[str, EncabezadoCuadro] = {}

    for campo, encabezado in encabezados.items():
        izquierda, derecha = limites[campo]
        palabras_columna = [
            palabra
            for palabra in palabras
            if palabra.pagina == encabezado.pagina
            and izquierda <= _centro_x(palabra.caja_visual) < derecha
            and abs(_centro_y(palabra.caja_visual) - referencia.centro_y)
            <= tolerancia_y
        ]
        palabras_columna = _ordenar_palabras_visualmente(palabras_columna)
        if not palabras_columna:
            palabras_columna = list(encabezado.palabras)
        resultado[campo] = EncabezadoCuadro(
            campo=campo,
            texto_original=" ".join(
                palabra.texto
                for palabra in palabras_columna
            ),
            pagina=encabezado.pagina,
            caja_visual=_union_cajas(
                palabra.caja_visual
                for palabra in palabras_columna
            ),
            palabras=tuple(palabras_columna),
            unidad=_detectar_unidad(palabras_columna),
        )

    return resultado


def _ordenar_palabras_visualmente(
    palabras: Iterable[PalabraNormalizada],
) -> list[PalabraNormalizada]:
    pendientes = sorted(
        palabras,
        key=lambda palabra: (
            _centro_y(palabra.caja_visual),
            palabra.caja_visual.x0,
        ),
    )
    lineas: list[list[PalabraNormalizada]] = []

    for palabra in pendientes:
        centro_y = _centro_y(palabra.caja_visual)
        linea_elegida = None
        for linea in lineas:
            centro_linea = median(
                _centro_y(elemento.caja_visual)
                for elemento in linea
            )
            altura = max(
                palabra.caja_visual.alto,
                *(elemento.caja_visual.alto for elemento in linea),
                1.0,
            )
            if abs(centro_y - centro_linea) <= max(1.0, altura * 0.6):
                linea_elegida = linea
                break
        if linea_elegida is None:
            lineas.append([palabra])
        else:
            linea_elegida.append(palabra)

    lineas.sort(
        key=lambda linea: median(
            _centro_y(elemento.caja_visual)
            for elemento in linea
        )
    )
    resultado: list[PalabraNormalizada] = []
    for linea in lineas:
        resultado.extend(
            sorted(linea, key=lambda palabra: palabra.caja_visual.x0)
        )
    return resultado


def _limites_filas(
    catalogo: CatalogoReferencias,
    encabezado_referencia: EncabezadoCuadro,
) -> list[tuple[float, float, float]]:
    centros = [
        _centro_y(candidato.caja_visual)
        for candidato in catalogo.referencias
    ]
    if not centros:
        return []
    saltos = [
        siguiente - actual
        for actual, siguiente in zip(centros, centros[1:])
        if siguiente - actual > 1.0
    ]
    salto_tipico = median(saltos) if saltos else max(
        encabezado_referencia.caja_visual.alto * 3,
        10.0,
    )
    limites: list[tuple[float, float, float]] = []

    for indice, centro in enumerate(centros):
        superior = (
            (encabezado_referencia.centro_y + centro) / 2
            if indice == 0
            else (centros[indice - 1] + centro) / 2
        )
        inferior = (
            centro + salto_tipico / 2
            if indice == len(centros) - 1
            else (centro + centros[indice + 1]) / 2
        )
        limites.append((centro, superior, inferior))

    return limites


def _crear_filas(
    palabras: list[PalabraNormalizada],
    catalogo: CatalogoReferencias,
    encabezados: dict[str, EncabezadoCuadro],
    limites_columnas: dict[str, tuple[float, float]],
) -> list[FilaCuadro]:
    limites = _limites_filas(
        catalogo,
        encabezados[CAMPO_REFERENCIA],
    )
    filas: list[FilaCuadro] = []

    for numero, (candidato, datos_limite) in enumerate(
        zip(catalogo.referencias, limites),
        start=1,
    ):
        centro, superior, inferior = datos_limite
        celdas: dict[str, CeldaCuadro] = {}

        for campo, (izquierda, derecha) in limites_columnas.items():
            palabras_celda = [
                palabra
                for palabra in palabras
                if palabra.pagina == catalogo.pagina
                and superior
                <= _centro_y(palabra.caja_visual)
                < inferior
                and izquierda
                <= _centro_x(palabra.caja_visual)
                < derecha
            ]
            palabras_celda = _ordenar_palabras_visualmente(palabras_celda)
            celdas[campo] = CeldaCuadro(
                campo=campo,
                texto=" ".join(
                    palabra.texto
                    for palabra in palabras_celda
                ).strip(),
                palabras=palabras_celda,
            )

        filas.append(
            FilaCuadro(
                numero_fila=numero,
                referencia=candidato.referencia.canonica,
                referencia_texto=candidato.referencia.texto_original,
                centro_y_visual=centro,
                limite_superior_visual=superior,
                limite_inferior_visual=inferior,
                celdas=celdas,
            )
        )

    return filas


def localizar_estructura_cuadro(
    palabras: list[PalabraNormalizada],
    catalogo: CatalogoReferencias,
    exigir_armadura: bool = True,
) -> CuadroFundaciones:
    """Construye columnas y filas sin depender de rotación ni nombres únicos."""

    if not catalogo.referencias:
        raise ValueError("El catálogo no contiene filas para construir el cuadro.")

    palabras = [p for p in palabras if p.pagina == catalogo.pagina
                and catalogo.limite_x_izquierdo < _centro_x(p.caja_visual) < catalogo.limite_x_derecho]

    encabezado_referencia = _buscar_encabezado_referencia(
        palabras,
        catalogo,
    )
    primera_fila_y = min(
        _centro_y(candidato.caja_visual)
        for candidato in catalogo.referencias
    )
    candidatos = _crear_candidatos_encabezados(
        palabras,
        encabezado_referencia,
        primera_fila_y,
    )
    encabezados = _seleccionar_encabezados(
        candidatos,
        encabezado_referencia,
    )

    faltantes = [
        campo
        for campo in (CAMPO_X, CAMPO_Y, CAMPO_H)
        if campo not in encabezados
    ]
    tiene_armadura = any(
        campo in encabezados
        for campo in (
            CAMPO_ARMADURA,
            CAMPO_ARMADURA_SUPERIOR,
            CAMPO_ARMADURA_INFERIOR,
        )
    )
    if not tiene_armadura and exigir_armadura:
        faltantes.append(CAMPO_ARMADURA)
    if faltantes:
        detectados = ", ".join(sorted(encabezados))
        raise LecturaCuadroNoCompatible(
            "El cuadro no contiene todos los campos necesarios. "
            f"Faltan: {', '.join(faltantes)}. "
            f"Se detectaron: {detectados}."
        )

    limites = _limites_columnas(encabezados)
    encabezados = _completar_textos_y_unidades_encabezados(
        encabezados,
        limites,
        palabras,
    )
    # Los centros pueden ampliarse al incorporar la unidad, por eso los límites
    # definitivos se calculan una segunda vez.
    limites = _limites_columnas(encabezados)
    filas = _crear_filas(
        palabras,
        catalogo,
        encabezados,
        limites,
    )

    advertencias: list[str] = []
    if CAMPO_PEDESTAL not in encabezados:
        advertencias.append(
            "El cuadro no contiene una columna de pedestal; ese cálculo se omitirá."
        )
    vacias = [
        f"{fila.referencia}:{campo}"
        for fila in filas
        for campo in (CAMPO_X, CAMPO_Y, CAMPO_H)
        if not fila.celdas[campo].texto
    ]
    if vacias:
        advertencias.append(
            "Hay celdas dimensionales vacías: "
            + ", ".join(vacias)
        )

    conteo_referencias = Counter(fila.referencia for fila in filas)
    duplicadas = {
        referencia: cantidad
        for referencia, cantidad in conteo_referencias.items()
        if cantidad > 1
    }
    if duplicadas:
        detalle = ", ".join(
            f"{referencia} ({cantidad} apariciones)"
            for referencia, cantidad in sorted(duplicadas.items())
        )
        advertencias.append(
            "El cuadro contiene referencias repetidas: "
            f"{detalle}. Revise las correcciones del proyecto."
        )

    confianza = "alta" if not vacias else "media"
    return CuadroFundaciones(
        pagina=catalogo.pagina,
        encabezados=encabezados,
        filas=filas,
        confianza=confianza,
        advertencias=advertencias,
    )


def _extraer_decimal(celda: CeldaCuadro, referencia: str, campo: str) -> Decimal:
    coincidencia = PATRON_NUMERO.search(celda.texto)
    if coincidencia is None:
        raise ValueError(
            f"No se encontró un valor numérico para {campo} en {referencia}: "
            f"{celda.texto!r}."
        )
    try:
        return Decimal(coincidencia.group().replace(",", "."))
    except InvalidOperation as error:
        raise ValueError(
            f"Valor dimensional inválido para {campo} en {referencia}."
        ) from error


def _convertir_a_metros(valor: Decimal, unidad: str) -> Decimal:
    if unidad == "m":
        return valor
    if unidad == "cm":
        return valor / Decimal("100")
    if unidad == "mm":
        return valor / Decimal("1000")
    raise ValueError(f"Unidad dimensional no admitida: {unidad}")


def extraer_dimensiones_cuadro(
    cuadro: CuadroFundaciones,
    unidad_predeterminada: str = "m",
) -> list[dict]:
    """Extrae X, Y y H y convierte m, cm o mm a metros."""

    unidad_predeterminada = unidad_predeterminada.lower().strip()
    if unidad_predeterminada not in ALIAS_UNIDADES:
        raise ValueError(
            "La unidad predeterminada debe ser m, cm o mm."
        )

    resultado: list[dict] = []
    campos_con_unidad_asumida: set[str] = set()
    for fila in cuadro.filas:
        unidades_fila: dict[str, str] = {}
        for campo in (CAMPO_X, CAMPO_Y, CAMPO_H):
            unidad_celda = _detectar_unidad(
                fila.celdas[campo].palabras
            )
            unidad_encabezado = cuadro.encabezados[campo].unidad
            unidades_fila[campo] = (
                unidad_celda
                or unidad_encabezado
                or unidad_predeterminada
            )
            if unidad_celda is None and unidad_encabezado is None:
                campos_con_unidad_asumida.add(campo)
        valores_originales = {
            campo: _extraer_decimal(
                fila.celdas[campo],
                fila.referencia,
                campo,
            )
            for campo in (CAMPO_X, CAMPO_Y, CAMPO_H)
        }
        valores_metros = {
            campo: _convertir_a_metros(
                valores_originales[campo],
                unidades_fila[campo],
            )
            for campo in (CAMPO_X, CAMPO_Y, CAMPO_H)
        }
        resultado.append(
            {
                "numero_fila": fila.numero_fila,
                "referencia": fila.referencia,
                "referencia_texto": fila.referencia_texto,
                "x": str(valores_metros[CAMPO_X]),
                "y": str(valores_metros[CAMPO_Y]),
                "h": str(valores_metros[CAMPO_H]),
                "x_original": str(valores_originales[CAMPO_X]),
                "y_original": str(valores_originales[CAMPO_Y]),
                "h_original": str(valores_originales[CAMPO_H]),
                "unidad_x": unidades_fila[CAMPO_X],
                "unidad_y": unidades_fila[CAMPO_Y],
                "unidad_h": unidades_fila[CAMPO_H],
            }
        )

    for campo in sorted(campos_con_unidad_asumida):
        advertencia = (
            f"No se indicó la unidad de {campo}; se asumió "
            f"{unidad_predeterminada}."
        )
        if advertencia not in cuadro.advertencias:
            cuadro.advertencias.append(advertencia)

    return resultado
