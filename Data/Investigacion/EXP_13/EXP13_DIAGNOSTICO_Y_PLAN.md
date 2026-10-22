# EXP-13 — Diagnóstico por clase y por fuente

EXP-11 permanece como evaluación externa. No se entrenó ni se calibró ningún umbral con sus etiquetas.

## Hallazgo principal

El corpus histórico contiene 474 páginas y 37 carpetas, pero solo 8 grupos de fuente confirmados o provisionales. Una fuente reúne 271 páginas y cruza train, validation y test. Por eso el split histórico por carpeta no mide independencia real de fuente.

## Diagnósticos prioritarios

| Diagnóstico | Clases prioritarias |
|---|---:|
| datos_historicos_escasos | 7 |
| ranking_util_umbral_no_calibrado | 17 |
| representacion_no_generaliza | 3 |

## Clases críticas con evidencia externa suficiente

Se muestran clases con al menos cinco positivos externos y F1 menor a 0,30.

| Tarea | Clase | Entrada | Históricas | Fuentes | Externas | Predichas | F1 | AUC | Diagnóstico |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| contenidos | agua_caliente | texto_ocr_mas_imagen | 47 | 5 | 7 | 2 | 0.000 | 0.862 | separacion_parcial_y_bajo_recall |
| contenidos | agua_caliente | texto_pdf_mas_ocr | 47 | 5 | 7 | 0 | 0.000 | 0.935 | ranking_util_pero_umbral_no_calibrado |
| contenidos | agua_fria | texto_ocr_mas_imagen | 47 | 5 | 7 | 2 | 0.000 | 0.828 | separacion_parcial_y_bajo_recall |
| contenidos | agua_fria | texto_pdf_mas_ocr | 47 | 5 | 7 | 0 | 0.000 | 0.924 | ranking_util_pero_umbral_no_calibrado |
| contenidos | artefactos_sanitarios | texto_ocr_mas_imagen | 41 | 2 | 5 | 0 | 0.000 | 0.888 | datos_historicos_escasos |
| contenidos | artefactos_sanitarios | texto_pdf_mas_ocr | 41 | 2 | 5 | 0 | 0.000 | 0.889 | datos_historicos_escasos |
| contenidos | baja_tension | texto_ocr_mas_imagen | 40 | 4 | 7 | 0 | 0.000 | 0.735 | ranking_util_pero_umbral_no_calibrado |
| contenidos | baja_tension | texto_pdf_mas_ocr | 40 | 4 | 7 | 0 | 0.000 | 0.781 | ranking_util_pero_umbral_no_calibrado |
| contenidos | canalizaciones | texto_ocr_mas_imagen | 40 | 4 | 7 | 0 | 0.000 | 0.735 | ranking_util_pero_umbral_no_calibrado |
| contenidos | canalizaciones | texto_pdf_mas_ocr | 40 | 4 | 7 | 0 | 0.000 | 0.781 | ranking_util_pero_umbral_no_calibrado |
| contenidos | canerias_sanitarias | texto_ocr_mas_imagen | 41 | 3 | 6 | 0 | 0.000 | 0.862 | ranking_util_pero_umbral_no_calibrado |
| contenidos | canerias_sanitarias | texto_pdf_mas_ocr | 41 | 3 | 6 | 0 | 0.000 | 0.934 | ranking_util_pero_umbral_no_calibrado |
| contenidos | cloacal | texto_ocr_mas_imagen | 44 | 5 | 7 | 1 | 0.000 | 0.844 | separacion_parcial_y_bajo_recall |
| contenidos | cloacal | texto_pdf_mas_ocr | 44 | 5 | 7 | 0 | 0.000 | 0.925 | ranking_util_pero_umbral_no_calibrado |
| contenidos | cubiertas | texto_ocr_mas_imagen | 24 | 3 | 13 | 4 | 0.118 | 0.702 | separacion_parcial_y_bajo_recall |
| contenidos | cubiertas | texto_pdf_mas_ocr | 24 | 3 | 13 | 1 | 0.143 | 0.721 | separacion_parcial_y_bajo_recall |
| contenidos | cubiertas_estructurales | texto_ocr_mas_imagen | 29 | 7 | 6 | 28 | 0.176 | 0.724 | separacion_parcial_y_bajo_recall |
| contenidos | cubiertas_estructurales | texto_pdf_mas_ocr | 29 | 7 | 6 | 0 | 0.000 | 0.807 | ranking_util_pero_umbral_no_calibrado |
| contenidos | detalles_constructivos | texto_ocr_mas_imagen | 48 | 5 | 7 | 0 | 0.000 | 0.556 | representacion_no_generaliza |
| contenidos | detalles_constructivos | texto_pdf_mas_ocr | 48 | 5 | 7 | 0 | 0.000 | 0.518 | representacion_no_generaliza |
| contenidos | ejes_replanteo | texto_ocr_mas_imagen | 3 | 2 | 5 | 0 | 0.000 | 0.594 | datos_historicos_escasos |
| contenidos | ejes_replanteo | texto_pdf_mas_ocr | 3 | 2 | 5 | 0 | 0.000 | 0.714 | datos_historicos_escasos |
| contenidos | escaleras_estructurales | texto_ocr_mas_imagen | 98 | 6 | 14 | 20 | 0.294 | 0.713 | separacion_parcial_y_bajo_recall |
| contenidos | escaleras_estructurales | texto_pdf_mas_ocr | 98 | 6 | 14 | 6 | 0.200 | 0.663 | separacion_parcial_y_bajo_recall |
| contenidos | fachadas | texto_ocr_mas_imagen | 64 | 7 | 13 | 17 | 0.267 | 0.799 | separacion_parcial_y_bajo_recall |
| contenidos | fachadas | texto_pdf_mas_ocr | 64 | 7 | 13 | 9 | 0.273 | 0.596 | representacion_no_generaliza |
| contenidos | fuerza | texto_ocr_mas_imagen | 39 | 3 | 7 | 0 | 0.000 | 0.721 | ranking_util_pero_umbral_no_calibrado |
| contenidos | fuerza | texto_pdf_mas_ocr | 39 | 3 | 7 | 0 | 0.000 | 0.746 | ranking_util_pero_umbral_no_calibrado |
| contenidos | iluminacion | texto_ocr_mas_imagen | 45 | 6 | 7 | 0 | 0.000 | 0.767 | ranking_util_pero_umbral_no_calibrado |
| contenidos | iluminacion | texto_pdf_mas_ocr | 45 | 6 | 7 | 0 | 0.000 | 0.816 | ranking_util_pero_umbral_no_calibrado |
| contenidos | implantacion | texto_ocr_mas_imagen | 3 | 2 | 5 | 0 | 0.000 | 0.587 | datos_historicos_escasos |
| contenidos | implantacion | texto_pdf_mas_ocr | 3 | 2 | 5 | 0 | 0.000 | 0.723 | datos_historicos_escasos |
| contenidos | niveles | texto_ocr_mas_imagen | 3 | 2 | 7 | 0 | 0.000 | 0.573 | datos_historicos_escasos |
| contenidos | niveles | texto_pdf_mas_ocr | 3 | 2 | 7 | 0 | 0.000 | 0.673 | datos_historicos_escasos |
| contenidos | pluvial | texto_ocr_mas_imagen | 46 | 5 | 8 | 1 | 0.000 | 0.842 | separacion_parcial_y_bajo_recall |
| contenidos | pluvial | texto_pdf_mas_ocr | 46 | 5 | 8 | 0 | 0.000 | 0.879 | ranking_util_pero_umbral_no_calibrado |
| contenidos | puertas_carpinterias | texto_ocr_mas_imagen | 20 | 5 | 5 | 0 | 0.000 | 0.376 | representacion_no_generaliza |
| contenidos | puertas_carpinterias | texto_pdf_mas_ocr | 20 | 5 | 5 | 0 | 0.000 | 0.553 | representacion_no_generaliza |
| contenidos | tableros | texto_ocr_mas_imagen | 40 | 4 | 7 | 0 | 0.000 | 0.735 | ranking_util_pero_umbral_no_calibrado |
| contenidos | tableros | texto_pdf_mas_ocr | 40 | 4 | 7 | 0 | 0.000 | 0.781 | ranking_util_pero_umbral_no_calibrado |
| contenidos | terreno | texto_ocr_mas_imagen | 3 | 2 | 14 | 0 | 0.000 | 0.543 | datos_historicos_escasos |
| contenidos | terreno | texto_pdf_mas_ocr | 3 | 2 | 14 | 0 | 0.000 | 0.672 | datos_historicos_escasos |
| contenidos | tomacorrientes | texto_ocr_mas_imagen | 44 | 6 | 7 | 0 | 0.000 | 0.762 | ranking_util_pero_umbral_no_calibrado |
| contenidos | tomacorrientes | texto_pdf_mas_ocr | 44 | 6 | 7 | 0 | 0.000 | 0.816 | ranking_util_pero_umbral_no_calibrado |
| contenidos | ventanas_carpinterias | texto_ocr_mas_imagen | 19 | 5 | 5 | 4 | 0.000 | 0.467 | datos_historicos_escasos |
| contenidos | ventanas_carpinterias | texto_pdf_mas_ocr | 19 | 5 | 5 | 0 | 0.000 | 0.782 | datos_historicos_escasos |
| disciplinas | electricidad | texto_ocr_mas_imagen | 46 | 6 | 7 | 0 | 0.000 | 0.763 | ranking_util_pero_umbral_no_calibrado |
| disciplinas | electricidad | texto_pdf_mas_ocr | 46 | 6 | 7 | 0 | 0.000 | 0.801 | ranking_util_pero_umbral_no_calibrado |
| disciplinas | implantacion_topografia | texto_ocr_mas_imagen | 3 | 2 | 14 | 0 | 0.000 | 0.535 | datos_historicos_escasos |
| disciplinas | implantacion_topografia | texto_pdf_mas_ocr | 3 | 2 | 14 | 0 | 0.000 | 0.719 | datos_historicos_escasos |
| disciplinas | sanitarias | texto_ocr_mas_imagen | 50 | 5 | 14 | 2 | 0.000 | 0.749 | separacion_parcial_y_bajo_recall |
| disciplinas | sanitarias | texto_pdf_mas_ocr | 50 | 5 | 14 | 0 | 0.000 | 0.903 | ranking_util_pero_umbral_no_calibrado |
| roles_documentales | corte | texto_ocr_mas_imagen | 100 | 7 | 48 | 9 | 0.000 | 0.451 | representacion_no_generaliza |
| roles_documentales | corte | texto_pdf_mas_ocr | 100 | 7 | 48 | 5 | 0.038 | 0.534 | representacion_no_generaliza |
| roles_documentales | cuadro_planilla | texto_pdf_mas_ocr | 153 | 5 | 14 | 15 | 0.207 | 0.753 | separacion_parcial_y_bajo_recall |
| roles_documentales | elevacion_fachada | texto_ocr_mas_imagen | 65 | 5 | 11 | 21 | 0.250 | 0.669 | separacion_parcial_y_bajo_recall |

## Plan recomendado

1. **Corregir el protocolo por fuente.** No volver a dividir por carpeta cuando varias carpetas provienen del mismo repositorio u obra original.
2. **Datos nuevos para clases escasas.** Buscar al menos tres fuentes realmente independientes y 20–30 páginas útiles por clase antes de reentrenar.
3. **Modelo para clases con datos pero mala separación.** Comparar TF-IDF por caracteres y reglas basadas en títulos usando solamente validación histórica por fuente.
4. **Calibración.** Solo calibrar clases cuyo ranking sea útil; hacerlo mediante folds por fuente, nunca con EXP-11.
5. **Mantener EXP-11 cerrado.** Usarlo nuevamente una sola vez después de fijar el nuevo pipeline y sus umbrales.

### Clases que necesitan más diversidad de datos

- `contenidos / artefactos_sanitarios`: 41 páginas históricas en 2 fuentes.
- `contenidos / ejes_replanteo`: 3 páginas históricas en 2 fuentes.
- `contenidos / implantacion`: 3 páginas históricas en 2 fuentes.
- `contenidos / niveles`: 3 páginas históricas en 2 fuentes.
- `contenidos / terreno`: 3 páginas históricas en 2 fuentes.
- `contenidos / ventanas_carpinterias`: 19 páginas históricas en 5 fuentes.
- `disciplinas / implantacion_topografia`: 3 páginas históricas en 2 fuentes.

### Clases con problema de representación o generalización

- `contenidos / detalles_constructivos`
- `contenidos / puertas_carpinterias`
- `roles_documentales / corte`

### Clases candidatas a calibración futura

- `contenidos / agua_caliente` (AUC máximo 0.935)
- `contenidos / agua_fria` (AUC máximo 0.924)
- `contenidos / baja_tension` (AUC máximo 0.781)
- `contenidos / canalizaciones` (AUC máximo 0.781)
- `contenidos / canerias_sanitarias` (AUC máximo 0.934)
- `contenidos / cloacal` (AUC máximo 0.925)
- `contenidos / cubiertas` (AUC máximo 0.721)
- `contenidos / cubiertas_estructurales` (AUC máximo 0.807)
- `contenidos / escaleras_estructurales` (AUC máximo 0.713)
- `contenidos / fachadas` (AUC máximo 0.799)
- `contenidos / fuerza` (AUC máximo 0.746)
- `contenidos / iluminacion` (AUC máximo 0.816)
- `contenidos / pluvial` (AUC máximo 0.879)
- `contenidos / tableros` (AUC máximo 0.781)
- `contenidos / tomacorrientes` (AUC máximo 0.816)
- `disciplinas / electricidad` (AUC máximo 0.801)
- `disciplinas / sanitarias` (AUC máximo 0.903)
