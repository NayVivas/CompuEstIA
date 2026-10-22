"""Inferencia EXP19 con pesos numéricos; sin pickle ni scikit-learn.

Reproduce los analizadores y TF-IDF del artefacto exportado, sin reentrenar.
Solo admite el contrato congelado exportado por exportar_exp19_portable.py.
"""
from collections import Counter
from io import BytesIO
from pathlib import Path
import hashlib
import json
import re
import unicodedata
import numpy as np


class Exp19Portable:
    def __init__(self, carpeta):
        carpeta = Path(carpeta)
        self.config = json.loads((carpeta / 'EXP19_PORTABLE.json').read_text(encoding='utf-8'))
        if self.config['version'] != 1:
            raise ValueError('Versión de EXP19 portable no soportada')
        pesos = carpeta / 'EXP19_PORTABLE.npz'
        # Algunos medios de distribución limitan el tamaño de un archivo
        # individual. Cuando existen partes, se prefieren para no leer primero
        # una copia monolítica que podría estar truncada.
        partes = sorted(carpeta.glob('EXP19_PORTABLE.npz.part*'))
        contenido = (
            b''.join(parte.read_bytes() for parte in partes)
            if partes
            else (pesos.read_bytes() if pesos.is_file() else b'')
        )
        if hashlib.sha256(contenido).hexdigest() != self.config['sha256_pesos']:
            raise ValueError('Los pesos EXP19 están incompletos o no corresponden al manifiesto')
        with np.load(BytesIO(contenido), allow_pickle=False) as archivo:
            self.pesos = {k: archivo[k] for k in archivo.files}

    def vectorizar(self, texto):
        bloques = []
        for spec in self.config['vectorizadores']:
            t = texto.lower() if spec['lowercase'] else texto
            if spec['strip_accents'] == 'unicode':
                t = ''.join(c for c in unicodedata.normalize('NFKD', t) if not unicodedata.combining(c))
            minimo, maximo = spec['ngram_range']
            if spec['analyzer'] == 'word':
                tokens = re.findall(spec['token_pattern'], t)
                terminos = (' '.join(tokens[i:i+n]) for n in range(minimo, maximo+1) for i in range(len(tokens)-n+1))
            elif spec['analyzer'] == 'char_wb':
                def caracteres():
                    for palabra in t.split():
                        palabra = ' ' + palabra + ' '
                        for n in range(minimo, maximo+1):
                            for i in range(max(1, len(palabra)-n+1)):
                                yield palabra[i:i+n]
                            if len(palabra) <= n:
                                break
                terminos = caracteres()
            else:
                raise ValueError('Analizador no soportado')
            vocabulario = spec['vocabulary']
            cuentas = Counter(vocabulario[x] for x in terminos if x in vocabulario)
            bloque = np.zeros(len(vocabulario), dtype=np.float64)
            for indice, cantidad in cuentas.items():
                bloque[indice] = (1 + np.log(cantidad)) if spec['sublinear_tf'] else cantidad
            bloque *= self.pesos[spec['nombre'] + '_idf']
            norma = np.linalg.norm(bloque)
            if norma:
                bloque /= norma
            bloques.append(bloque * spec['peso'])
        return np.concatenate(bloques)

    def puntajes(self, objetivo, vector):
        return self.pesos[objetivo + '_coef'] @ vector + self.pesos[objetivo + '_intercept']
