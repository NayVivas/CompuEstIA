"""Evidencia textual contextual: separa contenido dibujado de firmas y menciones.

No usa nombres de archivos ni números de página. Mantiene propuestas del modelo
sin evidencia como hipótesis, sin presentarlas como contenido confirmado.
"""
import re
import unicodedata


def normalizar(texto):
    texto = ''.join(c for c in unicodedata.normalize('NFKD', texto.upper()) if not unicodedata.combining(c))
    # Rótulos CAD escritos con espaciado entre letras.
    for palabra in (
        'CUADRO', 'FUNDACION', 'FUNDACIONES', 'CIMENTACION',
        'CIMENTACIONES', 'CIMIENTO', 'CIMIENTOS', 'COLUMNAS',
        'CASTILLOS', 'DETALLE', 'DETALLES', 'PLANTA', 'PLANTAS', 'PLANO',
        'ESTRUCTURA', 'ESTRUCTURAS', 'PORTICO', 'PORTICOS',
        'ARQUITECTURA', 'ARQUITECTONICO', 'ARQUITECTONICOS', 'DE',
    ):
        texto = re.sub(r'\b' + r'[ \t]+'.join(palabra) + r'\b',palabra,texto)
    return re.sub(r'[ \t]+',' ',texto)


def clasificar_evidencias(texto):
    t = normalizar(texto)
    t = re.sub(r'PARA LA ESTRUCTURA[^:]{0,180}?VER LAMINAS[^\n]*(?:\nDESDE[^\n]*)?', '', t)
    objetivos = {k:{'etiquetas':[]} for k in ('disciplinas','roles_documentales','contenidos')}
    evidencias = []
    def agregar(obj, etiqueta, patron, inferencia=False):
        m = re.search(patron,t,re.M)
        if m and etiqueta not in objetivos[obj]['etiquetas']:
            objetivos[obj]['etiquetas'].append(etiqueta)
            evidencias.append({'objetivo':obj,'etiqueta':etiqueta,'texto':m.group().strip()[:180], 'origen':'patron_contextual' if inferencia else 'texto_explicito'})
        return bool(m)
    titulo_estructural = re.search(
        r'^\s*(?:(?:PLANTA|PLANO|DETALLES?|CUADRO|PLANILLA|TABLA|TIPOS?)\s+(?:INDICE\s+)?(?:DE\s+)?'
        r'(?:FUNDACION(?:ES)?|CIMENTACION(?:ES)?|CIMIENTOS?|ZAPATAS?|'
        r'COLUMNAS?|PILARES?|CASTILLOS?|PORTICOS?|VIGAS?|RIOSTRAS?|'
        r'TRABES?|DALAS?)|PLANO\s+ESTRUCTURAL(?:ES)?\b|'
        r'ESTRUCTURAS?\s*(?:[-:]|$)|PORTICOS?\b|'
        r'(?:PLACAS?\s+Y\s+)?(?:COLUMNAS?|PILARES?)\s*(?::|$))',
        t,
        re.M,
    )
    estructura = bool(
        titulo_estructural
        or re.search(
            r'^ESTRUCTURA\s*$|\b(?:HORMIGON ARMADO|CONCRETO ARMADO|'
            r'ARMADURAS|ESTRIBOS|ACERO DE REFUERZO)\b',
            t,
            re.M,
        )
    )
    if estructura:
        agregar(
            'disciplinas',
            'estructura',
            r'^ESTRUCTURAS?\s*(?:[-:]|$)|^\s*PLANO\s+ESTRUCTURAL(?:ES)?\b|'
            r'^\s*(?:PLANTA|PLANO|DETALLES?|CUADRO|PLANILLA|TABLA|TIPOS?)\s+(?:INDICE\s+)?(?:DE\s+)?'
            r'(?:FUNDACION(?:ES)?|CIMENTACION(?:ES)?|CIMIENTOS?|ZAPATAS?|COLUMNAS?|PILARES?|CASTILLOS?|PORTICOS?|VIGAS?|RIOSTRAS?|TRABES?|DALAS?)\b|'
            r'^\s*(?:PORTICOS?|(?:PLACAS?\s+Y\s+)?(?:COLUMNAS?|PILARES?))\s*(?::|$)|'
            r'\b(?:HORMIGON ARMADO|CONCRETO ARMADO|ARMADURAS|ESTRIBOS)\b',
        )
    # La profesión ARQUITECTO y las firmas no son una disciplina del plano.
    patron_arquitectura = (
        r'\bARQUITECTURA\b|\b(?:PLANTAS?|CORTES?)\s+ARQUITECTONIC[AO]S?\b|'
        r'\bPLANTA\s+DE\s+CONJUNTO\b|\bFACHADA (?:PRINCIPAL|POSTERIOR|LATERAL)\b|'
        r'^\s*PLANTA\s+(?:SEMISOTANO|SOTANO|AZOTEA|TECHOS?|'
        r'(?:PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO|\d+\s*[°º]?)\s+PISO)\b|'
        r'\bDORMITORIOS?\b|\bCOCINA\b'
    ) if not estructura else r'^\s*(?:ARQUITECTURA|PLANTAS? ARQUITECTONICAS?)\s*$'
    agregar('disciplinas','arquitectura',patron_arquitectura)
    espacios = re.findall(
        r'\b(?:OFICINAS?|TESORERIA|CONTABILIDAD|DEPOSITO|RECEPCION|'
        r'DORMITORIOS?|RECAMARAS?|COMEDOR|SALA|COCINA|GARAGE|BANOS?|'
        r'ESTAR|HALL|TERRAZA|GIMNASIO|ESTACIONAMIENTO|CUARTO)\b',
        t,
    )
    if not estructura and len(espacios) >= 3:
        evidencia_espacio = (
            r'\b(?:COMEDOR|SALA|COCINA|DORMITORIOS?|RECAMARAS?|OFICINAS?|'
            r'BANOS?|ESTAR|HALL|TERRAZA|GIMNASIO|ESTACIONAMIENTO|CUARTO)\b'
        )
        agregar('disciplinas','arquitectura',evidencia_espacio,True)
        agregar('contenidos','distribucion_espacios',evidencia_espacio,True)
    for etiqueta,patron in {
        'sanitaria':r'\b(?:IN(?:S)?TALACION(?:ES)? (?:SANITARIAS?|HIDRAULICAS?)|CLOACALES?|DESAGUES?|AGUA POTABLE|RED HIDRAULICA)\b|\bISOMETRICO DE INSTALACION HIDRAULICA\b',
        'gas':r'\b(?:INSTALACION(?:ES)? (?:DE )?GAS|GAS NATURAL|GASODUCTO)\b',
        'electricidad':r'\b(?:INSTALACION(?:ES)? ELECTRICAS?|ILUMINACION|CIRCUITOS? ELECTRICOS?|DIAGRAMA UNIFILAR|TABLERO (?:ELECTRICO|GENERAL)|TOMACORRIENTES?|CONDUCTORES ELECTRICOS?)\b|\bREDES DE TOMACORRIENTES Y COMUNICACIONES\b',
    }.items():
        if agregar('disciplinas',etiqueta,patron):
            agregar('contenidos',{'sanitaria':'instalaciones_sanitarias','gas':'instalaciones_gas','electricidad':'instalaciones_electricas'}[etiqueta],patron)
    for etiqueta,patron in {
        'detalle':r'\bDETALLES?\b|^\s*TIPOS?\s+DE\s+(?:CIMIENTOS?|ZAPATAS?|FUNDACIONES?)\b', 'cuadro_planilla':r'\b(?:CUADRO|TABLA|PLANILLA)\b',
        'corte':r'\b(?:CORTE|SECCION)\b', 'elevacion_fachada':r'\b(?:ELEVACION|FACHADA|ALZADO)\b',
        'elevacion_porticos':r'\bPORTICOS?\b',
        'isometrico':r'\bISOMETRI(?:A|CO)\b',
    }.items(): agregar('roles_documentales',etiqueta,patron)
    # Una nota de nivel '(PLANTA BAJA)' en una viga no vuelve planta a su detalle.
    if re.search(
        r'^\s*(?:LOSACERO\s+)?PLANTAS?\b|^\s*PLANO\s+(?:DE\s+)?(?:FUNDACION|CIMENTACION)|'
        r'^\s*PLANO\s+ESTRUCTURAL(?:ES)?\b',
        t,
        re.M,
    ):
        agregar(
            'roles_documentales',
            'planta',
            r'^\s*(?:(?:LOSACERO\s+)?PLANTAS?|PLANO\s+(?:DE\s+)?(?:FUNDACION|CIMENTACION)|PLANO\s+ESTRUCTURAL(?:ES)?)[^\n]*',
        )
    elif not estructura and len(espacios) >= 3:
        agregar('roles_documentales','planta',r'\b(?:COMEDOR|SALA|COCINA)\b',True)
    if re.search(r'^LOSA ENTREPISO[^\n]*ESC',t,re.M) and len(re.findall(r'^C\d+\s*$',t,re.M))>=3:
        agregar('roles_documentales','planta',r'^LOSA ENTREPISO[^\n]*',True)
    if re.search(r'EST\.?\s*[Ø∅]',t) and re.search(r'CORTE[^\n]*ESC',t):
        agregar('roles_documentales','detalle',r'CORTE[^\n]*ESC[^\n]*',True)
    estructurales = {
        'fundaciones':r'\b(?:FUNDACION(?:ES)?|CIMENTACION(?:ES)?|CIMIENTOS?|ZAPATAS?|PILOTES?|BASES AISLADAS?)\b',
        'columnas_pilares':r'\b(?:COLUMNAS?|PILARES?|CASTILLOS?|PEDESTALES?|DADOS?)\b',
        'vigas':r'\b(?:VIGAS?|RIOSTRAS?|TRABES?|DALAS?|CADENAS? DE (?:DESPLANTE|CIMENTACION|AMARRE))\b|\bV\.\s*(?:ESP\.?|EJE|AMARRE|R\.)',
        'losas_forjados':r'\b(?:LOSAS?|FORJADOS?|LOSACERO|LOSETA)\b',
        'armaduras_acero':r'\b(?:ARMADURAS?|ARMADOS?|ESTRIBOS?|ACERO (?:PARAMENTO|DE REFUERZO)|VARILLAS?)\b|\bEST\.?\s*[Ø∅#]|\d+\s*[Ø∅#]\s*\d',
        'muros_estructurales':r'\b(?:PANTALLAS?|MUROS? (?:ESTRUCTURALES?|DE CONTENCION))\b',
        'escaleras_estructurales':r'\bESCALERAS?\b|\bESC\s*-\s*\d+',
        'rampas':r'\bRAMPAS?\b',
        'porticos':r'\bPORTICOS?\b',
    }
    if estructura:
        for etiqueta,patron in estructurales.items(): agregar('contenidos',etiqueta,patron)
        if len(re.findall(r'^C\d+\s*$',t,re.M))>=3:
            agregar('contenidos','columnas_pilares',r'^C\d+\s*$',True)
        if 'porticos' in objetivos['contenidos']['etiquetas'] and len(re.findall(r'\d+\s*X\s*\d+',t))>=3:
            agregar('contenidos','vigas',r'\d+\s*X\s*\d+',True)
    if 'arquitectura' in objetivos['disciplinas']['etiquetas']:
        agregar('contenidos','fachadas',r'\bFACHADAS?\b')
        agregar('contenidos','ventanas_carpinterias',r'\b(?:VENTANAS?|CARPINTERIAS?)\b')
    titulos = list(dict.fromkeys(linea.strip() for linea in t.splitlines() if re.search(r'^(?:PLANTA|PORTICO|CUADRO|DETALLE|FACHADA|CORTE|ISOMETRIA|VIGAS|ESTRUCTURA|FUNDACIONES|PANTALLAS)\b',linea.strip()) and len(linea.strip())<150))[:16]
    requiere_revision = not objetivos['disciplinas']['etiquetas']
    motivos_revision = (
        ['No se encontró evidencia textual suficiente para identificar la disciplina.']
        if requiere_revision else []
    )
    return {
        'estado':'clasificado_por_reglas' if evidencias else 'sin_clasificacion',
        'metodo':'evidencias_contextuales',
        'objetivos':objetivos,
        'evidencias':evidencias,
        'titulos':titulos,
        'requiere_revision':requiere_revision,
        'motivos_revision':motivos_revision,
    }


def combinar(modelo, evidencia):
    """No confundir ausencia de evidencia con prueba de que algo no existe."""
    propuestas = {}
    for objetivo, datos in modelo.get('objetivos',{}).items():
        verificadas = set(evidencia['objetivos'].get(objetivo,{}).get('etiquetas',[]))
        propuestas[objetivo] = [e for e in datos.get('etiquetas',[]) if e not in verificadas]
    resultado = dict(evidencia)
    resultado.update(estado='clasificado_hibrido',metodo='EXP19_y_evidencias',modelo='EXP19',runtime=modelo.get('runtime'), propuestas_modelo_sin_evidencia=propuestas)
    alias_disciplinas = {
        'sanitarias': 'sanitaria',
        'electrica': 'electricidad',
        'electricas': 'electricidad',
    }
    disciplinas = set(evidencia['objetivos']['disciplinas']['etiquetas'])
    predichas = set(modelo.get('objetivos',{}).get('disciplinas',{}).get('etiquetas',[]))
    disciplinas_comparables = {alias_disciplinas.get(item, item) for item in disciplinas}
    predichas_comparables = {alias_disciplinas.get(item, item) for item in predichas}
    motivos = []
    if not disciplinas:
        motivos.append('Falta identificar la disciplina mediante evidencia del plano.')
    # Una lámina arquitectónica puede llevar superpuesta una instalación. En
    # ese caso la segunda etiqueta del modelo se conserva como propuesta, pero
    # no obliga a revisar una disciplina que el texto ya respalda. Se mantiene
    # el conflicto cuando una única disciplina técnica contradice al modelo.
    if (
        len(disciplinas_comparables) == 1
        and 'arquitectura' not in disciplinas_comparables
        and predichas_comparables
        and not disciplinas_comparables.intersection(predichas_comparables)
    ):
        motivos.append('El modelo y el texto discrepan sobre la disciplina.')
    resultado['motivos_revision'] = motivos
    resultado['requiere_revision'] = bool(motivos)
    resultado['tiene_sugerencias'] = any(propuestas.values())
    return resultado
