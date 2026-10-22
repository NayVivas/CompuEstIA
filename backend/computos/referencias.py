"""Descubrimiento y búsqueda de referencias estructurales.

La regla importante de este módulo es que la planta no decide por sí sola qué
texto representa una fundación. Primero se obtiene un catálogo desde el cuadro
de tipos y después se buscan únicamente esas referencias en la planta.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Collection, Iterable
import re
import unicodedata

from computos.documentos.modelos import Caja, PalabraNormalizada
from computos.documentos.regiones import contexto_del_encabezado, titulos_cuadros


PATRON_REFERENCIA = re.compile(
    r"^(?P<prefijo>[A-ZÑ]{1,10})"
    r"[.\-_/]*"
    r"(?P<numero>\d{1,4})"
    r"(?P<sufijo>[A-ZÑ]?)$"
)

ALIAS_ENCABEZADO_REFERENCIA = {
    "TIPO",
    "REF",
    "REFERENCIA",
    "MARCA",
    "CLAVE",
    "CODIGO",
    "NOMENCLATURA",
    "DESIGNACION",
    "ELEMENTO",
    "ID",
}

ALIAS_ENCABEZADOS_DATOS = {
    "X",
    "Y",
    "H",
    "B",
    "L",
    "BASE",
    "LARGO",
    "LONGITUD",
    "ANCHO",
    "ALTURA",
    "ESP",
    "ESPESOR",
    "CANTO",
    "PERALTE",
    "PROFUNDIDAD",
    "ARMADURA",
    "ARMADO",
    "ACERO",
    "REFUERZO",
    "HIERRO",
    "MALLA",
    "PEDESTAL",
    "DADO",
    "ARRANQUE",
    "CANTIDAD",
}

PALABRAS_CONTEXTO_FUNDACIONES = {
    "FUNDACION",
    "FUNDACIONES",
    "ZAPATA",
    "ZAPATAS",
    "BASES",
    "CIMENTACION",
    "CIMENTACIONES",
    "CIMIENTO",
    "CIMIENTOS",
}


class LecturaCuadroNoCompatible(ValueError):
    """El lector no pudo interpretar el formato; no prueba un error del plano."""


@dataclass(frozen=True, slots=True)
class ReferenciaNormalizada:
    """Partes comparables de una referencia, conservando su escritura original."""

    texto_original: str
    canonica: str
    prefijo: str
    numero: int
    sufijo: str = ""


@dataclass(frozen=True, slots=True)
class CandidatoReferencia:
    """Referencia encontrada en una posición concreta de un PDF."""

    referencia: ReferenciaNormalizada
    pagina: int
    caja_pdf: Caja
    caja_visual: Caja
    indices_origen: tuple[int, ...]


@dataclass(slots=True)
class CatalogoReferencias:
    """Referencias de tipos descubiertas en un cuadro del plano."""

    pagina: int
    encabezado: str
    referencias: list[CandidatoReferencia]
    confianza: str
    puntaje: float
    advertencias: list[str] = field(default_factory=list)
    palabra_encabezado: PalabraNormalizada | None = None
    titulo_cuadro: str | None = None
    contexto_local_confirmado: bool = False
    limite_x_izquierdo: float = float("-inf")
    limite_x_derecho: float = float("inf")

    @property
    def canonicas(self) -> list[str]:
        return [candidato.referencia.canonica for candidato in self.referencias]


def _sin_tildes(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(
        caracter
        for caracter in normalizado
        if not unicodedata.combining(caracter)
    )


def normalizar_etiqueta(texto: str) -> str:
    """Normaliza encabezados como ``Ref.``, ``REFERENCIA`` o ``Tipo``."""

    texto = _sin_tildes(texto).upper().strip()
    return re.sub(r"[^A-Z0-9Ñ]", "", texto)


def interpretar_referencia(texto: str) -> ReferenciaNormalizada | None:
    """Interpreta referencias alfanuméricas sin imponer un prefijo específico.

    Ejemplos equivalentes: ``Z-01``, ``Z.01`` y ``Z01``. Las referencias que
    contienen solamente números se dejan para el modo asistido, ya que en una
    planta se confundirían con ejes y cotas.
    """

    original = texto.strip()
    limpio = _sin_tildes(original).upper().strip()
    limpio = limpio.strip("()[]{}:;,#")
    limpio = re.sub(r"\s+", "", limpio)
    coincidencia = PATRON_REFERENCIA.fullmatch(limpio)
    if not coincidencia:
        return None

    prefijo = coincidencia.group("prefijo")
    numero = int(coincidencia.group("numero"))
    sufijo = coincidencia.group("sufijo")
    return ReferenciaNormalizada(
        texto_original=original,
        canonica=f"{prefijo}{numero}{sufijo}",
        prefijo=prefijo,
        numero=numero,
        sufijo=sufijo,
    )


def _union_cajas(cajas: Iterable[Caja]) -> Caja:
    cajas = tuple(cajas)
    return Caja(
        x0=min(caja.x0 for caja in cajas),
        y0=min(caja.y0 for caja in cajas),
        x1=max(caja.x1 for caja in cajas),
        y1=max(caja.y1 for caja in cajas),
    )


def _centro_x(caja: Caja) -> float:
    return (caja.x0 + caja.x1) / 2


def _centro_y(caja: Caja) -> float:
    return (caja.y0 + caja.y1) / 2


def _estan_en_misma_linea(
    primera: PalabraNormalizada,
    segunda: PalabraNormalizada,
) -> bool:
    if primera.pagina != segunda.pagina:
        return False

    altura = max(
        primera.caja_visual.alto,
        segunda.caja_visual.alto,
        1.0,
    )
    diferencia_vertical = abs(
        _centro_y(primera.caja_visual) - _centro_y(segunda.caja_visual)
    )
    espacio_horizontal = segunda.caja_visual.x0 - primera.caja_visual.x1
    return diferencia_vertical <= altura * 0.65 and -altura <= espacio_horizontal <= altura * 3


def extraer_candidatos_referencias(
    palabras: list[PalabraNormalizada],
) -> list[CandidatoReferencia]:
    """Encuentra referencias completas aunque el PDF las divida en tres palabras."""

    ordenadas = sorted(
        enumerate(palabras),
        key=lambda item: (
            item[1].pagina,
            round(_centro_y(item[1].caja_visual), 1),
            item[1].caja_visual.x0,
        ),
    )
    candidatos: list[CandidatoReferencia] = []
    claves_vistas: set[tuple] = set()

    for posicion, (indice_original, palabra) in enumerate(ordenadas):
        grupo = [(indice_original, palabra)]

        for cantidad_palabras in range(1, 4):
            if cantidad_palabras > 1:
                siguiente_posicion = posicion + cantidad_palabras - 1
                if siguiente_posicion >= len(ordenadas):
                    break
                siguiente = ordenadas[siguiente_posicion]
                if not _estan_en_misma_linea(grupo[-1][1], siguiente[1]):
                    break
                grupo.append(siguiente)

            texto = "".join(elemento[1].texto for elemento in grupo)
            referencia = interpretar_referencia(texto)
            if referencia is None:
                continue

            indices = tuple(elemento[0] for elemento in grupo)
            caja_pdf = _union_cajas(elemento[1].caja_pdf for elemento in grupo)
            caja_visual = _union_cajas(
                elemento[1].caja_visual for elemento in grupo
            )
            clave = (
                palabra.pagina,
                referencia.canonica,
                indices,
            )
            if clave in claves_vistas:
                continue
            claves_vistas.add(clave)
            candidatos.append(
                CandidatoReferencia(
                    referencia=referencia,
                    pagina=palabra.pagina,
                    caja_pdf=caja_pdf,
                    caja_visual=caja_visual,
                    indices_origen=indices,
                )
            )

    return candidatos


def _es_encabezado_referencia(palabra: PalabraNormalizada) -> bool:
    return normalizar_etiqueta(palabra.texto) in ALIAS_ENCABEZADO_REFERENCIA


def _encabezados_datos_en_linea(
    encabezado: PalabraNormalizada,
    palabras: list[PalabraNormalizada],
) -> list[PalabraNormalizada]:
    altura = max(encabezado.caja_visual.alto, 1.0)
    centro_y = _centro_y(encabezado.caja_visual)
    vecinos = [p for p in palabras if p.pagina == encabezado.pagina
               and p is not encabezado and _es_encabezado_referencia(p)
               and abs(_centro_y(p.caja_visual) - centro_y) <= max(8.0, altura * 3)]
    izquierda = max((_centro_x(p.caja_visual) for p in vecinos
                     if _centro_x(p.caja_visual) < _centro_x(encabezado.caja_visual) - 1), default=float("-inf"))
    derecha = min((p.caja_visual.x0 for p in vecinos
                   if _centro_x(p.caja_visual) > _centro_x(encabezado.caja_visual) + 1), default=float("inf"))
    return [
        palabra
        for palabra in palabras
        if palabra.pagina == encabezado.pagina
        and palabra is not encabezado
        and normalizar_etiqueta(palabra.texto) in ALIAS_ENCABEZADOS_DATOS
        and izquierda < _centro_x(palabra.caja_visual) < derecha
        and abs(_centro_y(palabra.caja_visual) - centro_y) <= max(8.0, altura * 3)
    ]


def _limites_columna_referencia(
    encabezado: PalabraNormalizada,
    encabezados_datos: list[PalabraNormalizada],
) -> tuple[float, float]:
    centro = _centro_x(encabezado.caja_visual)
    otros_centros = sorted(
        _centro_x(palabra.caja_visual)
        for palabra in encabezados_datos
        if abs(_centro_x(palabra.caja_visual) - centro) > 1.0
    )
    centros_izquierda = [valor for valor in otros_centros if valor < centro]
    centros_derecha = [valor for valor in otros_centros if valor > centro]

    vecino_izquierdo = max(centros_izquierda, default=None)
    vecino_derecho = min(centros_derecha, default=None)
    ancho_referencia = max(encabezado.caja_visual.ancho, 10.0)

    if vecino_izquierdo is None and vecino_derecho is None:
        return centro - ancho_referencia * 5, centro + ancho_referencia * 5
    if vecino_izquierdo is None:
        distancia = vecino_derecho - centro
        return centro - distancia * 1.5, (centro + vecino_derecho) / 2
    if vecino_derecho is None:
        distancia = centro - vecino_izquierdo
        return (vecino_izquierdo + centro) / 2, centro + distancia * 1.5
    return (vecino_izquierdo + centro) / 2, (centro + vecino_derecho) / 2


def _seleccionar_secuencia_filas(
    encabezado: PalabraNormalizada,
    candidatos: list[CandidatoReferencia],
) -> list[CandidatoReferencia]:
    """Conserva la secuencia continua que comienza debajo del encabezado."""

    if not candidatos:
        return []

    candidatos = sorted(candidatos, key=lambda item: _centro_y(item.caja_visual))
    centro_encabezado = _centro_y(encabezado.caja_visual)
    altura = max(encabezado.caja_visual.alto, 1.0)
    maximo_primer_salto = max(35.0, altura * 12)

    inicio = next(
        (
            indice
            for indice, candidato in enumerate(candidatos)
            if 0 < _centro_y(candidato.caja_visual) - centro_encabezado
            <= maximo_primer_salto
        ),
        None,
    )
    if inicio is None:
        return []

    seleccionados = [candidatos[inicio]]
    saltos: list[float] = []

    for candidato in candidatos[inicio + 1 :]:
        salto = _centro_y(candidato.caja_visual) - _centro_y(
            seleccionados[-1].caja_visual
        )
        if salto <= 1.0:
            # Dos candidatos en una misma fila hacen ambiguo el catálogo.
            seleccionados.append(candidato)
            continue

        limite_dinamico = max(
            45.0,
            (median(saltos) * 3.5) if saltos else altura * 12,
        )
        if salto > limite_dinamico:
            break

        saltos.append(salto)
        seleccionados.append(candidato)

    return seleccionados


def _inferir_encabezados_referencia(palabras, titulos, candidatos, existentes):
    """Recupera una celda REF vacía solo si hay título y ejes dimensionales.

    No inventa dimensiones ni interpreta códigos por su prefijo. Una tabla sin
    títulos ni encabezados dimensionales sigue siendo una extracción pendiente.
    """
    inferidos = []
    for titulo in titulos:
        if titulo.familia != "fundaciones":
            continue
        if any(contexto_del_encabezado(e, titulos, _encabezados_datos_en_linea(e, palabras)) == titulo
               for e in existentes):
            continue
        alto = max(titulo.caja.alto, 4.0)
        cercanos = [c for c in candidatos if c.pagina == titulo.pagina
                    and titulo.caja.y1 < c.caja_visual.y0 < titulo.caja.y1 + max(150.0, alto * 25)
                    and abs(c.caja_visual.x0 - titulo.caja.x0) < max(180.0, alto * 25)]
        grupos = []
        for c in sorted(cercanos, key=lambda c: c.caja_visual.x0):
            if not grupos or abs(c.caja_visual.x0 - grupos[-1][0].caja_visual.x0) > max(4.0, alto):
                grupos.append([c])
            else:
                grupos[-1].append(c)
        for grupo in grupos:
            if len(grupo) < 2:
                continue
            primero = min(grupo, key=lambda c: c.caja_visual.y0)
            datos = [p for p in palabras if p.pagina == titulo.pagina
                     and normalizar_etiqueta(p.texto) in ALIAS_ENCABEZADOS_DATOS
                     and titulo.caja.y1 < p.caja_visual.y0 < primero.caja_visual.y0
                     and 0 < p.caja_visual.x0 - primero.caja_visual.x0 < max(300.0, alto * 40)]
            bandas = []
            for p in sorted(datos, key=lambda p: p.caja_visual.y0):
                if not bandas or abs(p.caja_visual.y0 - bandas[-1][0].caja_visual.y0) > max(3.0, alto):
                    bandas.append([p])
                else:
                    bandas[-1].append(p)
            banda = max(bandas, key=len, default=[])
            if len(banda) < 2:
                continue
            y = median(p.caja_visual.y0 for p in banda)
            caja = Caja(primero.caja_visual.x0, y, primero.caja_visual.x1, y + max(4.0, banda[0].caja_visual.alto))
            inferido = PalabraNormalizada(titulo.pagina, "REF", caja, caja, -1, -1, 0)
            if contexto_del_encabezado(inferido, titulos, banda) == titulo:
                inferidos.append(inferido)
    return inferidos


def descubrir_catalogo_referencias(
    palabras: list[PalabraNormalizada],
) -> CatalogoReferencias:
    """Descubre la columna de referencias más probable de un cuadro.

    Si no existe una columna reconocible, se detiene y pide revisión en lugar
    de asumir que cualquier código alfanumérico es una fundación.
    """

    titulos = titulos_cuadros(palabras)
    candidatos = extraer_candidatos_referencias(palabras)
    encabezados = [palabra for palabra in palabras if _es_encabezado_referencia(palabra)]
    encabezados += _inferir_encabezados_referencia(palabras, titulos, candidatos, encabezados)
    if not encabezados:
        raise LecturaCuadroNoCompatible(
            "No se encontró una columna de referencias (TIPO, REF., REFERENCIA, "
            "MARCA, CLAVE o ID) en el cuadro."
        )

    evaluaciones: list[CatalogoReferencias] = []

    for encabezado in encabezados:
        encabezados_datos = _encabezados_datos_en_linea(encabezado, palabras)
        titulo = contexto_del_encabezado(encabezado, titulos, encabezados_datos)
        if titulo is not None and titulo.familia != "fundaciones":
            continue
        # En una lámina con títulos de varias familias no se atribuye un
        # cuadro sin contexto al único título de zapatas de toda la página.
        if titulo is None and any(t.pagina == encabezado.pagina for t in titulos):
            continue
        limite_izquierdo, limite_derecho = _limites_columna_referencia(
            encabezado,
            encabezados_datos,
        )
        candidatos_columna = [
            candidato
            for candidato in candidatos
            if candidato.pagina == encabezado.pagina
            and limite_izquierdo
            <= _centro_x(candidato.caja_visual)
            <= limite_derecho
            and _centro_y(candidato.caja_visual)
            > _centro_y(encabezado.caja_visual)
        ]
        siguientes = [p.caja_visual.y0 for p in encabezados if p is not encabezado
                      and p.pagina == encabezado.pagina and p.caja_visual.y0 > encabezado.caja_visual.y1
                      and limite_izquierdo <= _centro_x(p.caja_visual) <= limite_derecho]
        siguientes += [t.caja.y0 for t in titulos if t.pagina == encabezado.pagina
                       and t.caja.y0 > encabezado.caja_visual.y1
                       and limite_izquierdo <= t.caja.x0 <= limite_derecho]
        limite_y = min(siguientes, default=float("inf"))
        candidatos_columna = [c for c in candidatos_columna if _centro_y(c.caja_visual) < limite_y]
        filas = _seleccionar_secuencia_filas(encabezado, candidatos_columna)
        contexto = titulo is not None and titulo.familia == "fundaciones"
        puntaje = len(filas) * 2 + len(encabezados_datos) * 1.5 + (20 if contexto else 0)
        advertencias: list[str] = []

        if len(filas) < 2:
            advertencias.append(
                "Se encontraron menos de dos referencias debajo del encabezado."
            )
        if not encabezados_datos:
            advertencias.append(
                "No se encontraron encabezados de dimensiones junto a la referencia."
            )
        if not contexto:
            advertencias.append(
                "No se confirmó un título local de fundaciones para esta tabla."
            )
        if encabezado.numero_bloque == -1:
            advertencias.append("La celda de referencia no tenía rótulo; su posición se dedujo del título, los encabezados dimensionales y la alineación de dos o más referencias.")

        conteo_referencias = Counter(
            candidato.referencia.canonica
            for candidato in filas
        )
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
                f"{detalle}. No se corregirán automáticamente."
            )

        confianza = (
            "alta"
            if len(filas) >= 2 and len(encabezados_datos) >= 2 and contexto
            else "media"
            if len(filas) >= 1 and encabezados_datos
            else "baja"
        )
        evaluaciones.append(
            CatalogoReferencias(
                pagina=encabezado.pagina,
                encabezado=encabezado.texto,
                referencias=filas,
                confianza=confianza,
                puntaje=puntaje,
                advertencias=advertencias,
                palabra_encabezado=encabezado,
                titulo_cuadro=titulo.texto if titulo else None,
                contexto_local_confirmado=contexto,
            )
        )

    if not evaluaciones:
        raise LecturaCuadroNoCompatible("No se localizó un cuadro atribuible a fundaciones. Las tablas de otras familias no se consideran errores del plano.")
    mejor = max(evaluaciones, key=lambda evaluacion: evaluacion.puntaje)
    if not mejor.referencias or mejor.confianza == "baja":
        raise LecturaCuadroNoCompatible(
            "Se encontró un posible encabezado, pero no una columna confiable de "
            "referencias. El plano debe pasar al modo asistido."
        )

    empatados = [
        evaluacion
        for evaluacion in evaluaciones
        if evaluacion is not mejor
        and abs(evaluacion.puntaje - mejor.puntaje) < 1.0
    ]
    if empatados:
        if any(e.canonicas != mejor.canonicas for e in empatados):
            raise LecturaCuadroNoCompatible("Hay varios cuadros de fundaciones con alcance no resuelto. Se deben separar sus regiones o niveles; no se eligió el primero ni se renombraron referencias.")

    # Corredor de esta tabla: evita traer encabezados y celdas de una tabla
    # paralela. Los bordes no alteran el PDF ni las coordenadas originales.
    h = mejor.palabra_encabezado
    vecinos = [e for e in encabezados if e is not h and e.pagina == h.pagina
               and abs(_centro_y(e.caja_visual) - _centro_y(h.caja_visual)) <= max(8.0, h.caja_visual.alto * 3)]
    mejor.limite_x_izquierdo = max((e.caja_visual.x1 for e in vecinos
                                  if e.caja_visual.x1 < h.caja_visual.x0), default=float("-inf"))
    mejor.limite_x_derecho = min((e.caja_visual.x0 for e in vecinos
                                if e.caja_visual.x0 > h.caja_visual.x1), default=float("inf"))

    return mejor


def detectar_referencias_del_catalogo(
    palabras: list[PalabraNormalizada],
    referencias_validas: Collection[str],
) -> list[dict]:
    """Busca en planta únicamente los tipos autorizados por el cuadro."""

    canonicas_validas = set()
    for texto in referencias_validas:
        referencia = interpretar_referencia(texto)
        if referencia is None:
            raise ValueError(f"Referencia de catálogo inválida: {texto}")
        canonicas_validas.add(referencia.canonica)

    if not canonicas_validas:
        raise ValueError("El catálogo de referencias está vacío.")

    candidatos = extraer_candidatos_referencias(palabras)
    seleccionados = [
        candidato
        for candidato in candidatos
        if candidato.referencia.canonica in canonicas_validas
    ]

    # Si una referencia estaba dividida en varias palabras, evitamos conservar
    # además una detección parcial que utilice los mismos índices de origen.
    seleccionados.sort(
        key=lambda candidato: (
            candidato.pagina,
            _centro_y(candidato.caja_visual),
            _centro_x(candidato.caja_visual),
            len(candidato.indices_origen),
        )
    )
    unicos: list[CandidatoReferencia] = []
    for candidato in seleccionados:
        solapado = next(
            (
                existente
                for existente in unicos
                if existente.pagina == candidato.pagina
                and existente.referencia.canonica == candidato.referencia.canonica
                and set(existente.indices_origen) & set(candidato.indices_origen)
            ),
            None,
        )
        if solapado is None:
            unicos.append(candidato)
            continue
        if len(candidato.indices_origen) > len(solapado.indices_origen):
            unicos[unicos.index(solapado)] = candidato

    return [
        {
            "referencia": candidato.referencia.canonica,
            "texto_original": candidato.referencia.texto_original,
            "pagina": candidato.pagina,
            "x0": round(candidato.caja_pdf.x0, 2),
            "y0": round(candidato.caja_pdf.y0, 2),
            "x1": round(candidato.caja_pdf.x1, 2),
            "y1": round(candidato.caja_pdf.y1, 2),
            "centro_x": round(_centro_x(candidato.caja_pdf), 2),
            "centro_y": round(_centro_y(candidato.caja_pdf), 2),
            "x0_visual": round(candidato.caja_visual.x0, 2),
            "y0_visual": round(candidato.caja_visual.y0, 2),
            "x1_visual": round(candidato.caja_visual.x1, 2),
            "y1_visual": round(candidato.caja_visual.y1, 2),
        }
        for candidato in unicos
    ]
