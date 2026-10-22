# EXP-07 — TF-IDF + Logistic Regression multilabel

## Objetivo
Evaluar una representación textual de las páginas mediante TF-IDF y un clasificador Logistic Regression multilabel, manteniendo exactamente el split de EXP-03 y comparándolo descriptivamente con EXP-04 (reglas) y EXP-05 (LogReg con 5 features agregadas).

## Unidad experimental
- Unidad de predicción: página.
- Unidad de independencia: proyecto.
- Dataset: 474 páginas, 37 proyectos, 278 PDFs.
- Targets: disciplinas, roles_documentales y contenidos.
- Split: 26 train / 5 validation / 6 test proyectos; 332 / 71 / 71 páginas.

## Entrada y prevención de leakage
- Entrada: texto extraído de la página del PDF.
- No se utiliza el nombre del archivo como feature.
- No se utilizan etiquetas del Ground Truth como feature.
- El vocabulario TF-IDF se ajusta exclusivamente sobre TRAIN y luego se transforma VALIDATION/TEST.
- La transformación se guarda como artefacto reproducible.

## Configuración inicial
- `TfidfVectorizer`: lowercase=True, strip_accents=unicode, ngram_range=(1,2), min_df=2, max_features=20000, sublinear_tf=True.
- Clasificador: One-vs-Rest Logistic Regression.
- `C=1.0`, `class_weight=balanced`, `solver=liblinear`, `max_iter=3000`.
- Umbral fijo: 0.5.
- No se hizo tuning sobre TEST.

## Tratamiento de etiquetas raras
Las etiquetas que no aparecen en TRAIN no pueden ser aprendidas por el modelo supervisado. Se conservan en la evaluación como columnas de referencia y se reportan con `seen_in_train=False`; sus predicciones son cero. Esto evita ocultar una limitación del split.

## Métricas
Se reportan precision, recall y F1 micro/macro, Hamming loss, exact match, cobertura y abstención. La cobertura se define como proporción de páginas con al menos una etiqueta predicha.

## Comparación
EXP-07 se compara sobre los mismos proyectos TEST con EXP-04 y EXP-05. La comparación es descriptiva: no se establece un ganador global. Deben observarse conjuntamente precisión, recall, F1, cobertura y las diferencias entre targets.

## Resultados TEST

            target split                    model  micro_precision  micro_recall  micro_f1  macro_precision  macro_recall  macro_f1  hamming_loss  exact_match  coverage  abstention
        contenidos  test EXP04_Baseline_0B_Reglas         0.346535      0.106707  0.163170         0.198939      0.064176  0.083883      0.126408     0.000000  0.309859    0.690141
       disciplinas  test EXP04_Baseline_0B_Reglas         0.628571      0.282051  0.389381         0.158442      0.098485  0.120703      0.138833     0.154930  0.309859    0.690141
roles_documentales  test EXP04_Baseline_0B_Reglas         0.340000      0.110390  0.166667         0.292929      0.045914  0.077640      0.266041     0.000000  0.309859    0.690141
       disciplinas  test  EXP05_LogReg_5_features         0.222826      0.525641  0.312977         0.191095      0.515152  0.211039      0.362173     0.070423  1.000000    0.000000
roles_documentales  test  EXP05_LogReg_5_features         0.348485      0.746753  0.475207         0.316050      0.591631  0.340513      0.447183     0.000000  1.000000    0.000000
        contenidos  test  EXP05_LogReg_5_features         0.197386      0.920732  0.325081         0.138289      0.673033  0.220901      0.441549     0.000000  1.000000    0.000000
       disciplinas  test       EXP07_TFIDF_LogReg         0.176471      0.384615  0.241935         0.221939      0.470779  0.171429      0.378270     0.098592  0.985915    0.014085
roles_documentales  test       EXP07_TFIDF_LogReg         0.420495      0.772727  0.544622         0.302274      0.534269  0.333990      0.311424     0.084507  1.000000    0.000000
        contenidos  test       EXP07_TFIDF_LogReg         0.182316      0.710366  0.290162         0.118878      0.561070  0.185775      0.401408     0.000000  0.746479    0.253521

## Lectura descriptiva
- `EXP04` es un baseline de reglas que puede abstenerse; por eso su cobertura no es equivalente a la de los modelos supervisados.
- `EXP05` usa cinco features agregadas de inventario; `EXP07` usa texto de página mediante TF-IDF.
- En `disciplinas`, EXP-07 presenta mayor recall que EXP-04 pero menor precisión; frente a EXP-05, EXP-07 cambia el equilibrio precisión/recall.
- En `roles_documentales`, EXP-07 aumenta el micro-F1 respecto de EXP-05 y mantiene recall alto, con cobertura total en TEST.
- En `contenidos`, EXP-07 mantiene un recall alto pero menor precisión que EXP-05, por lo que el comportamiento refleja una mayor tendencia a emitir etiquetas.
- Estas diferencias no constituyen un ganador global: deben interpretarse por target, métrica y cobertura.

## Artefactos
- `EXP07_tfidf_vectorizer.joblib`
- modelos y label binarizers por target
- `EXP07_METRICAS.csv`
- `EXP07_METRICAS_POR_LABEL.csv`
- `EXP07_PREDICCIONES_TEST.csv`
- `EXP07_COMPARACION_TEST_EXP04_EXP05_EXP07.csv`
- `EXP07_COMPARACION_RESUMEN.csv`
- `EXP07_TEXT_CACHE.csv`
