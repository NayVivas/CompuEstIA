"""Decisiones técnicas explícitas. El PDF original nunca se modifica."""
from computos.referencias import interpretar_referencia


ACCIONES_RESOLUCION = {
    "reasignar_referencia_detalle",
    "seleccionar_fuente_columna",
    "definir_seccion_columna",
}


def _referencia_normalizada(valor, campo):
    if not isinstance(valor, str):
        raise ValueError(f"{campo}: referencia inválida.")
    referencia = interpretar_referencia(valor)
    if not referencia or referencia.canonica != valor.strip().upper():
        raise ValueError(
            f"{campo}: usá una referencia alfanumérica normalizada, por ejemplo C13."
        )
    return referencia.canonica


def _identidad_fuente(registro):
    sha = registro.get("sha256")
    if (
        not isinstance(sha, str)
        or len(sha) != 64
        or any(c not in "0123456789abcdef" for c in sha)
    ):
        raise ValueError("Huella de PDF inválida en la resolución técnica.")
    pagina = registro.get("pagina")
    if type(pagina) is not int or pagina < 1:
        raise ValueError("Página inválida en la resolución técnica.")
    return sha, pagina


def validar_resoluciones(datos):
    """Valida resoluciones trazables sin confiar en campos calculados del cliente."""

    if not isinstance(datos, list) or len(datos) > 1000:
        raise ValueError(
            "Las resoluciones técnicas deben ser una lista de hasta 1000 decisiones."
        )
    claves = set()
    resultado = []
    for posicion, original in enumerate(datos, start=1):
        if not isinstance(original, dict):
            raise ValueError(f"Resolución técnica {posicion}: formato inválido.")
        accion = original.get("accion")
        if accion not in ACCIONES_RESOLUCION:
            raise ValueError(f"Resolución técnica {posicion}: acción no permitida.")
        sha, pagina = _identidad_fuente(original)
        revisor = original.get("revisor")
        motivo = original.get("motivo")
        if not isinstance(revisor, str) or not 2 <= len(revisor.strip()) <= 160:
            raise ValueError("Indicá el profesional revisor (2 a 160 caracteres).")
        if not isinstance(motivo, str) or not 10 <= len(motivo.strip()) <= 1000:
            raise ValueError("El motivo técnico debe tener entre 10 y 1000 caracteres.")

        decision = {
            "accion": accion,
            "sha256": sha,
            "pagina": pagina,
            "revisor": revisor.strip(),
            "motivo": motivo.strip(),
        }
        incidencia_id = original.get("incidencia_id")
        if incidencia_id is not None:
            if (
                not isinstance(incidencia_id, str)
                or len(incidencia_id) != 24
                or any(c not in "0123456789abcdef" for c in incidencia_id)
            ):
                raise ValueError("Identificador de incidencia inválido.")
            decision["incidencia_id"] = incidencia_id

        if accion == "reasignar_referencia_detalle":
            origen = _referencia_normalizada(
                original.get("referencia_original"), "referencia_original"
            )
            destino = _referencia_normalizada(
                original.get("referencia_correcta"), "referencia_correcta"
            )
            if origen == destino:
                raise ValueError("La referencia corregida debe ser distinta de la original.")
            decision.update(
                referencia_original=origen,
                referencia_correcta=destino,
            )
            clave = (accion, sha, pagina, origen)
        elif accion == "seleccionar_fuente_columna":
            campo = original.get("campo")
            if campo not in {"seccion", "armadura"}:
                raise ValueError("La selección de fuente debe indicar sección o armadura.")
            referencia = _referencia_normalizada(
                original.get("referencia"), "referencia"
            )
            decision.update(campo=campo, referencia=referencia)
            clave = (accion, campo, referencia)
        else:
            referencia = _referencia_normalizada(
                original.get("referencia"), "referencia"
            )
            dimensiones = []
            for campo in ("dimension_1_m", "dimension_2_m"):
                valor = original.get(campo)
                if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                    raise ValueError(f"{campo}: ingresá una dimensión numérica en metros.")
                valor = float(valor)
                if not 0.05 <= valor <= 5.0:
                    raise ValueError(f"{campo}: la dimensión debe estar entre 0.05 y 5.00 m.")
                dimensiones.append(round(valor, 4))
            decision.update(
                referencia=referencia,
                dimension_1_m=dimensiones[0],
                dimension_2_m=dimensiones[1],
            )
            clave = (accion, referencia)

        if clave in claves:
            raise ValueError("Hay más de una resolución para el mismo dato técnico.")
        claves.add(clave)
        resultado.append(decision)
    return resultado


def validar_correcciones(datos):
    if not isinstance(datos,list) or len(datos)>1000: raise ValueError('Las correcciones técnicas deben ser una lista de hasta 1000 filas.')
    claves=set()
    for d in datos:
        if not isinstance(d,dict): raise ValueError('Corrección técnica inválida.')
        sha=d.get('sha256')
        if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha): raise ValueError('Huella de PDF inválida.')
        if any(type(d.get(k)) is not int or d[k]<1 for k in ('pagina','fila')): raise ValueError('Página o fila inválida.')
        clave=(sha,d['pagina'],d['fila'])
        if clave in claves: raise ValueError('Corrección repetida para una misma fila.')
        claves.add(clave)
        for k,mini,maxi in [('revisor',2,160),('motivo',10,1000),('referencia_original',1,30),('referencia_correcta',1,30)]:
            if not isinstance(d.get(k),str) or not mini<=len(d[k].strip())<=maxi: raise ValueError(f'{k}: dato inválido.')
        for k in ('referencia_original','referencia_correcta'):
            ref=interpretar_referencia(d[k])
            if not ref or ref.canonica!=d[k].strip().upper(): raise ValueError('Usá una referencia alfanumérica normalizada, por ejemplo Z13.')
    return datos


def corregir_filas(catalogo, sha, pagina, correcciones):
    originales=[c.referencia.canonica for c in catalogo.referencias]
    resultado=list(originales); aplicadas=[]
    from collections import Counter
    repetidas={r for r,n in Counter(originales).items() if n>1}
    for d in correcciones:
        if d['sha256']!=sha or d['pagina']!=pagina: continue
        i=d['fila']-1
        if i>=len(originales) or originales[i]!=d['referencia_original'] or originales[i] not in repetidas:
            raise ValueError('La corrección no corresponde a una fila duplicada del cuadro original.')
        if d['referencia_correcta']==originales[i]: raise ValueError('La nueva referencia debe ser distinta de la original.')
        resultado[i]=d['referencia_correcta']
        aplicadas.append({**d,'aparicion':originales[:i+1].count(originales[i])})
    if aplicadas and any(n>1 for n in Counter(resultado).values()):
        raise ValueError('La propuesta todavía deja referencias duplicadas en el cuadro.')
    return resultado,aplicadas
