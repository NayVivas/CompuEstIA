# Actualización EXP19

## Objetivo

Mejorar la detección de etiquetas minoritarias sobre el dataset congelado de
EXP17, manteniendo las características TF-IDF de EXP18 y sin seleccionar
decisiones con TEST.

## Metodología

- Se reutilizó el texto nativo/OCR y el vectorizador de EXP18.
- Se compararon cinco modelos: Logistic Regression con `C=1, 2, 4` y
  Linear SVC con `C=0.5, 1`.
- Cada modelo se evaluó con cuatro estrategias: umbral global y tres variantes
  de umbral por etiqueta regularizado según soporte.
- Se evaluaron 20 candidatos por objetivo y 60 en total usando únicamente
  VALIDATION.
- Se eligió la mayor macro-F1 entre las configuraciones cuyo micro-F1 quedó a
  no más de 0,02 del mejor micro-F1 de VALIDATION.
- TEST se evaluó una sola vez después de congelar la configuración ganadora de
  cada objetivo.

## Configuraciones seleccionadas

| Objetivo | Modelo | Estrategia |
|---|---|---|
| Disciplinas | Linear SVC, C=0.5 | por etiqueta, soporte mínimo 5, regularización 10 |
| Roles documentales | Linear SVC, C=0.5 | por etiqueta, soporte mínimo 5, regularización 10 |
| Contenidos | Linear SVC, C=0.5 | por etiqueta, soporte mínimo 10, regularización 10 |

## Resultado en TEST frente a EXP18

| Objetivo | micro-F1 EXP18 | micro-F1 EXP19 | macro-F1 EXP18 | macro-F1 EXP19 | Recall EXP18 | Recall EXP19 |
|---|---:|---:|---:|---:|---:|---:|
| Disciplinas | 0.7451 | 0.7467 | 0.4275 | 0.4251 | 0.7081 | 0.6957 |
| Roles documentales | 0.7075 | 0.7180 | 0.3212 | 0.3305 | 0.7240 | 0.7849 |
| Contenidos | 0.5560 | 0.5411 | 0.2346 | 0.2584 | 0.4729 | 0.6118 |

En `contenidos`, EXP19 cambia el equilibrio: pierde 0,0149 de micro-F1, pero
gana 0,0238 de macro-F1 y 0,1388 de recall. Las etiquetas presentes con F1
cero bajaron de 21 a 15 en VALIDATION y de 19 a 12 en TEST.

Por fuente, el micro-F1 de `contenidos` mejoró en EXP02 (+0,0393) y EXP11
(+0,1177), pero disminuyó en EXP16 (-0,0432). Esto confirma que el problema ya
no es solo el umbral: todavía existe cambio de dominio visual entre fuentes.

## Ejecución

Desde `backend`:

```powershell
python -m experimentos.entrenar_exp19
python -m unittest tests.test_exp19_calibracion -v
```

Los resultados se guardan en `Data/EXP19_balance_minoritarias`.

## Qué sigue: EXP20

EXP20 debe conservar el texto de EXP19 e incorporar características visuales y
de composición obtenidas directamente de cada página:

1. tamaño, orientación y rotación;
2. densidad y distribución de bloques de texto;
3. cantidad y orientación de líneas y objetos vectoriales;
4. cobertura de imágenes y necesidad de OCR;
5. ubicación y densidad del rótulo o carátula;
6. fusión de esas variables con TF-IDF usando el mismo split por proyectos.

Primero se probarán características geométricas deterministas, más baratas y
auditables. Solo si no alcanzan se incorporará un embedding visual compacto.
No hace falta volver a etiquetar ni buscar más proyectos para iniciar EXP20.

## Archivos principales

- `backend/experimentos/entrenar_exp19.py`
- `backend/tests/test_exp19_calibracion.py`
- `Data/EXP19_balance_minoritarias/EXP19_DOCUMENTACION.md`
- `Data/EXP19_balance_minoritarias/EXP19_CONFIG.json`
- `Data/EXP19_balance_minoritarias/EXP19_METRICAS.csv`
- `Data/EXP19_balance_minoritarias/EXP18_VS_EXP19.csv`
- `Data/EXP19_balance_minoritarias/EXP18_VS_EXP19_POR_SEGMENTO.csv`
- `Data/EXP19_balance_minoritarias/EXP19_DIAGNOSTICO_ETIQUETAS_F1_CERO.csv`
