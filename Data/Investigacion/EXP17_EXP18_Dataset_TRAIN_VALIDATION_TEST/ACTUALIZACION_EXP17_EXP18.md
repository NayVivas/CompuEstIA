# Actualización EXP17 + EXP18

Esta actualización integra los Ground Truth revisados de EXP02, EXP11 y EXP16,
crea un split por fuentes independientes y entrena una nueva línea base con
texto nativo y OCR.

## Aplicación

Copiá el contenido del ZIP sobre la raíz de `ComputoEstIA`, conservando las
carpetas `backend` y `Data`. El paquete no duplica los PDF originales.

```powershell
cd C:\Users\chari\Documents\ComputoEstIA\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ml.txt
python -m unittest discover -s tests -v
```

Para regenerar todo:

```powershell
python experimentos\preparar_exp17.py
python experimentos\extraer_texto_exp17.py
python experimentos\entrenar_exp18.py
```

Tesseract debe estar instalado y disponible en `PATH` para repetir el OCR. Si
conservás `Data/EXP17_dataset_integrado/EXP17_TEXT_CACHE.csv`, no hace falta
reprocesar las imágenes.

## Resultado reproducido

- 976 páginas utilizables.
- 675 TRAIN, 148 VALIDATION y 153 TEST.
- 45 grupos independientes sin fuga entre particiones.
- 329 páginas con OCR y ninguna página sin texto.
- Todas las etiquetas aparecen en TRAIN.

| Target | micro-F1 TEST | Precision | Recall |
|---|---:|---:|---:|
| Disciplinas | 0.7451 | 0.7862 | 0.7081 |
| Roles documentales | 0.7075 | 0.6918 | 0.7240 |
| Contenidos | 0.5560 | 0.6745 | 0.4729 |

EXP18 es la nueva referencia. No debe compararse de forma directa con EXP07
porque amplía proyectos, taxonomía y protocolo de separación.
