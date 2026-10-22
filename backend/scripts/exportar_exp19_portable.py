"""Exportar artefactos propios y confiables EXP19 a JSON/NPZ (entorno de entrenamiento)."""
from pathlib import Path
import hashlib
import json
import sys
import joblib
import numpy as np


def exportar(carpeta):
    carpeta = Path(carpeta)
    union = joblib.load(carpeta / 'EXP19_TFIDF_HIBRIDO.joblib')
    config = {'version': 1, 'vectorizadores': [], 'clases': {}}
    pesos = {}
    for nombre, v in union.transformer_list:
        assert v.analyzer in ('word', 'char_wb') and v.norm == 'l2' and v.use_idf
        assert v.strip_accents in (None, 'unicode') and not v.binary
        assert v.preprocessor is None and v.tokenizer is None and v.stop_words is None
        spec = {k: getattr(v,k) for k in ['analyzer','lowercase','strip_accents','ngram_range','token_pattern','sublinear_tf']}
        spec.update(nombre=nombre, vocabulary={k:int(i) for k,i in v.vocabulary_.items()}, peso=(union.transformer_weights or {}).get(nombre,1.0))
        config['vectorizadores'].append(spec)
        pesos[nombre+'_idf'] = v.idf_
    for objetivo in ('disciplinas','roles_documentales','contenidos'):
        modelo = joblib.load(carpeta / f'EXP19_{objetivo}_MODELO.joblib')
        config['clases'][objetivo] = joblib.load(carpeta / f'EXP19_{objetivo}_BINARIZADOR.joblib').classes_.tolist()
        assert all(type(e).__name__ == 'LinearSVC' for e in modelo.estimators_)
        pesos[objetivo+'_coef'] = np.vstack([e.coef_ for e in modelo.estimators_])
        pesos[objetivo+'_intercept'] = np.concatenate([e.intercept_ for e in modelo.estimators_])
    destino = carpeta / 'EXP19_PORTABLE.npz'
    np.savez_compressed(destino, **pesos)
    config['sha256_pesos'] = hashlib.sha256(destino.read_bytes()).hexdigest()
    (carpeta/'EXP19_PORTABLE.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')

if __name__ == '__main__':
    exportar(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'data/modelos/exp19')
