# Configuraciones por proyecto

Esta carpeta contiene únicamente excepciones comprobadas de juegos de planos.
Las reglas generales del programa no deben incluir nombres como `F12`, `F13` o
`C4`.

Una configuración puede declarar los nombres esperados de los archivos y dos
tipos de corrección:

```json
{
  "nombre": "Proyecto de ejemplo",
  "archivos_esperados": {
    "planta": "planta.pdf",
    "detalles": "detalles.pdf",
    "columnas": "columnas.pdf"
  },
  "correcciones_referencias_cuadro": [
    {
      "referencia_original": "Z1",
      "aparicion": 2,
      "referencia_correcta": "Z2",
      "motivo": "Descripción verificable del error del plano."
    }
  ],
  "correcciones_columnas_fundaciones": []
}
```

Cada corrección exige un motivo. Los nombres en `archivos_esperados` impiden
aplicar por accidente una configuración a otro juego de planos.

Uso:

```powershell
python app.py --config-proyecto configuraciones\mi_proyecto.json
```

Si el plano no necesita excepciones, no se pasa este argumento.
