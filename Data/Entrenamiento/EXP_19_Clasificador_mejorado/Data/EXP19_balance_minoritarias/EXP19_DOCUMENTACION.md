# EXP19 - Balance de etiquetas minoritarias

Se conservaron las características TF-IDF híbridas de EXP18. Los modelos y umbrales se eligieron solo con VALIDATION; TEST se evaluó una vez después de congelar cada configuración.

Criterio: maximizar macro-F1 de etiquetas presentes entre candidatos cuyo micro-F1 esté a no más de 0,02 del mejor micro-F1 de VALIDATION.

| Target | Modelo | Umbrales | micro-F1 TEST | Δ micro-F1 | macro-F1 TEST | Δ macro-F1 |
|---|---|---|---:|---:|---:|---:|
| disciplinas | linearsvc_c05 | por_etiqueta_s5_r10 | 0.7467 | +0.0016 | 0.4251 | -0.0024 |
| roles_documentales | linearsvc_c05 | por_etiqueta_s5_r10 | 0.7180 | +0.0105 | 0.3305 | +0.0094 |
| contenidos | linearsvc_c05 | por_etiqueta_s10_r10 | 0.5411 | -0.0149 | 0.2584 | +0.0238 |

## Contenidos por fuente en TEST

| Fuente | Páginas | micro-F1 EXP18 | micro-F1 EXP19 | Δ | Recall EXP18 | Recall EXP19 |
|---|---:|---:|---:|---:|---:|---:|
| EXP02 | 17 | 0.2857 | 0.3250 | +0.0393 | 0.2000 | 0.4333 |
| EXP11 | 49 | 0.3758 | 0.4935 | +0.1177 | 0.2500 | 0.5089 |
| EXP16 | 87 | 0.6278 | 0.5846 | -0.0432 | 0.5901 | 0.6714 |

## Lectura correcta

EXP19 es una mejora del clasificador textual, no una validación final de producción. Las clases ausentes o casi ausentes en VALIDATION no pueden calibrarse de forma fiable y conservan el umbral global.

El paso siguiente recomendado es EXP20: incorporar características visuales y de composición de página al texto para reducir el cambio de dominio entre fuentes.
