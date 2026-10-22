"""Asociación de cotas con contornos, no con el número más cercano al rótulo."""

from itertools import combinations
import re

import pymupdf


def contornos_y_segmentos(pagina):
    rectangulos = []
    segmentos = []
    matriz = pagina.rotation_matrix
    for dibujo in pagina.get_drawings():
        for item in dibujo.get("items", []):
            if item[0] in {"re", "qu"}:
                if item[0] == "qu":
                    q = item[1] * matriz
                    puntos_quad = [q.ul, q.ur, q.lr, q.ll, q.ul]
                    if not all(abs(a.x-b.x) < .3 or abs(a.y-b.y) < .3
                               for a,b in zip(puntos_quad, puntos_quad[1:])):
                        continue
                    r = q.rect
                else:
                    r = item[1] * matriz
                rectangulos.append(r)
                puntos = [r.tl, r.tr, r.br, r.bl, r.tl]
                segmentos.extend(zip(puntos, puntos[1:]))
            elif item[0] == "l":
                segmentos.append((item[1] * matriz, item[2] * matriz))
    return rectangulos, segmentos


def dimensiones_del_contorno(referencia, numeros, rectangulos):
    """Exige dos cotas exteriores y escala X/Y coherente con un rectángulo."""
    centro = pymupdf.Point(*referencia["centro"])
    propuestas = []
    for r in rectangulos:
        if not r.contains(centro) or min(r.width, r.height) < 4 or max(r.width, r.height) > 350:
            continue
        margen = max(3.0, min(r.width, r.height) * .6)
        horizontales, verticales = [], []
        for n in numeros:
            if n['pagina'] != referencia['pagina'] or not n['decimal_explicito']:
                continue
            x, y = n['centro']
            caja = n['caja']
            if r.x0 <= x <= r.x1 and caja.ancho > caja.alto * 1.1:
                distancia = min(abs(y-r.y0), abs(y-r.y1))
                if not r.y0 <= y <= r.y1 and distancia <= margen:
                    horizontales.append((distancia, n))
            if r.y0 <= y <= r.y1 and caja.alto > caja.ancho * 1.1:
                distancia = min(abs(x-r.x0), abs(x-r.x1))
                if not r.x0 <= x <= r.x1 and distancia <= margen:
                    verticales.append((distancia, n))
        for dx, nx in horizontales:
            for dy, ny in verticales:
                sx, sy = r.width/nx['valor_m'], r.height/ny['valor_m']
                diferencia = abs(sx-sy)/max(sx,sy)
                if diferencia > .06:
                    continue
                score = diferencia * 8 + (dx+dy)/max(r.width+r.height,1)
                propuestas.append((score, nx, ny, r))
    if not propuestas:
        return None
    propuestas.sort(key=lambda p:p[0])
    mejor = propuestas[0]
    if any(abs(p[0]-mejor[0]) < .04 and (p[1]['valor_m'],p[2]['valor_m']) != (mejor[1]['valor_m'],mejor[2]['valor_m']) for p in propuestas[1:]):
        return None
    _, nx, ny, r = mejor
    return {
        "x_m": nx['valor_m'], "y_m": ny['valor_m'],
        "contorno": {"x0":r.x0,"y0":r.y0,"x1":r.x1,"y1":r.y1},
        "cotas": [{"eje":"X","texto":nx['texto'],"valor_m":nx['valor_m']},
                  {"eje":"Y","texto":ny['texto'],"valor_m":ny['valor_m']}],
        "origen":"contorno_y_dos_cotas_coherentes",
    }


def altura_detalle_tipico(palabras, numeros, segmentos):
    """Propone H solo desde un cuerpo de zapata rectangular y una cota lateral.

    El título debe decir DETALLE TIPICO ... ZAPATA. Una losa de limpieza o un
    pedestal estrecho no cumplen la forma requerida. El valor sigue sujeto a
    confirmación profesional; no se asigna si hay alternativas distintas.
    """
    titulos = []
    for palabra in palabras:
        if not re.fullmatch(r"ZAPATAS?", palabra.texto.upper().strip(".:")):
            continue
        linea = ' '.join(p.texto for p in palabras if p.pagina==palabra.pagina
                         and p.numero_bloque==palabra.numero_bloque and p.numero_linea==palabra.numero_linea).upper()
        if re.search(r"DETALLE\s+TIPIC[OA]", linea):
            titulos.append(palabra)
    propuestas=[]
    for titulo in titulos:
        tx=(titulo.caja_visual.x0+titulo.caja_visual.x1)/2
        ty=titulo.caja_visual.y0
        horizontales=[]; verticales=[]
        for a,b in segmentos:
            if not (tx-130 <= a.x <= tx+130 and ty-140 <= a.y <= ty):
                continue
            if abs(a.y-b.y) < .4 and abs(a.x-b.x)>4:
                horizontales.append((min(a.x,b.x),max(a.x,b.x),(a.y+b.y)/2))
            if abs(a.x-b.x)<.4 and abs(a.y-b.y)>3:
                verticales.append(((a.x+b.x)/2,min(a.y,b.y),max(a.y,b.y)))
        for izquierda,derecha in combinations(verticales,2):
            x0,x1=sorted((izquierda[0],derecha[0]))
            if abs(izquierda[1]-derecha[1])>.8 or abs(izquierda[2]-derecha[2])>.8:
                continue
            y0=(izquierda[1]+derecha[1])/2; y1=(izquierda[2]+derecha[2])/2
            ancho=x1-x0; alto=y1-y0
            if not 1.5<=ancho/alto<=8 or ty-y1>max(60,ancho):
                continue
            def borde_suficiente(borde):
                tramos = sorted((max(l,x0),min(r,x1)) for l,r,y in horizontales
                                if abs(y-borde)<.8 and r>x0 and l<x1)
                if not tramos or tramos[0][0]>x0+.8 or max(r for _,r in tramos)<x1-.8:
                    return False
                cubierto=0; extremo=x0
                for l,r in tramos:
                    cubierto+=max(0,r-max(l,extremo)); extremo=max(extremo,r)
                # En el borde superior el pedestal puede interrumpir el trazo.
                return cubierto >= ancho*.55
            if not all(borde_suficiente(borde) for borde in (y0,y1)):
                continue
            for n in numeros:
                if n['pagina']!=titulo.pagina or not n['decimal_explicito']:
                    continue
                x,y=n['centro']
                distancia=min(abs(x-x0),abs(x-x1))
                if x0<=x<=x1 or not y0<=y<=y1 or distancia>ancho*.7:
                    continue
                propuestas.append((abs(y-(y0+y1)/2)/alto+distancia/ancho, n))
    if not propuestas:
        return None
    propuestas.sort(key=lambda p:p[0])
    mejor=propuestas[0]
    if any(p[0]-mejor[0]<.15 and p[1]['valor_m']!=mejor[1]['valor_m'] for p in propuestas[1:]):
        return None
    return {"h_m":mejor[1]['valor_m'],"texto":mejor[1]['texto'],"origen":"cota_lateral_del_cuerpo_en_detalle_tipico"}
