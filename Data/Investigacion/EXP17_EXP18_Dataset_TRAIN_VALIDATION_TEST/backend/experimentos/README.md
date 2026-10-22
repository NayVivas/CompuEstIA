# Experimentos

`app_fases_0_a_4.py` conserva una versión histórica del desarrollo para fines
de consulta. No es el punto de entrada vigente y no debe utilizarse para
ejecutar el proyecto.

Los comandos mantenidos son `python app.py`, `python -m computos` y
`python analizar_planos.py`.

## Datasets y entrenamiento

- `python experimentos/preparar_exp17.py`: integra EXP02, EXP11 y EXP16 y
  genera un split por grupos independientes.
- `python experimentos/extraer_texto_exp17.py`: extrae texto nativo y OCR.
  Requiere Tesseract disponible en `PATH`.
- `python experimentos/entrenar_exp18.py`: entrena TF-IDF híbrido + Logistic
  Regression y calibra umbrales únicamente con VALIDATION.

Instalá las dependencias con `pip install -r requirements-ml.txt`.
