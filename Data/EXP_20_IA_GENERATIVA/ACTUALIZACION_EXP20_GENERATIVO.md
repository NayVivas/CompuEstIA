# EXP20 — Modo asistido generativo para estructura

## Decisión de alcance

El entregable se concentra en planos estructurales. Se suspende la búsqueda de
un clasificador general para todas las disciplinas porque las métricas de
EXP17–EXP19 mostraron un cambio importante entre fuentes y poco soporte para
muchas etiquetas.

EXP20 no descarta el trabajo anterior. Lo reorganiza en un sistema híbrido:

1. el PDF y sus imágenes son interpretados por un modelo multimodal;
2. la respuesta se restringe a un contrato JSON tipado;
3. Python valida referencias, evidencia, dimensiones y contradicciones;
4. el ingeniero confirma los datos extraídos;
5. el motor determinístico calcula hormigón, acero y encofrado.

La IA generativa no calcula cómputos finales.

## Alcance del primer prototipo

- plantas y cuadros de fundaciones;
- detalles de fundaciones;
- plantas y detalles de columnas;
- plantas y detalles de vigas de riostra;
- referencias, cantidades, dimensiones y armaduras visibles;
- evidencia textual, página, confianza y motivos de revisión.

Los planos arquitectónicos, sanitarios, eléctricos y topográficos quedan fuera
del entregable principal. Se pueden identificar como no estructurales, pero no
se intentan computar.

## Configuración

Desde `backend`:

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY="tu-clave"
$env:COMPUTOESTIA_IA_MODEL="gpt-6-sol"
uvicorn computos.api:app --reload --port 8000
```

La clave debe configurarse únicamente en el backend. Nunca debe escribirse en
React, enviarse al navegador ni guardarse en Git.

## Prueba manual

Consultar configuración:

```powershell
Invoke-RestMethod `
    -Method Get `
    -Uri "http://127.0.0.1:8000/api/ia/estado"
```

Enviar un PDF estructural:

```powershell
curl.exe `
    -X POST `
    "http://127.0.0.1:8000/api/ia/analizar-estructura/" `
    -F "plano=@C:\ruta\plano_estructural.pdf"
```

El campo `calculos_realizados_por_ia` debe ser siempre `false`. Si la confianza
es inferior a 0,80, falta evidencia o existen dimensiones contradictorias, el
elemento queda pendiente de revisión.

## Archivos agregados o modificados

- `backend/computos/ia/esquemas.py`;
- `backend/computos/ia/proveedor.py`;
- `backend/computos/ia/servicio.py`;
- `backend/computos/api/aplicacion.py`;
- `backend/tests/test_ia_generativa.py`;
- `backend/requirements.txt`;
- `backend/.env.example`;
- `.gitignore`.

## Validación necesaria antes de la entrega final

La integración técnica no implica que el modelo ya esté validado. El siguiente
paso es ejecutar el endpoint sobre planos estructurales que no hayan sido usados
como ejemplo y comparar cada campo contra una revisión manual.

Se medirán:

- precisión y recall de referencias;
- exactitud de cantidad y dimensiones;
- porcentaje de elementos con evidencia correcta;
- tasa de datos inventados;
- porcentaje enviado a revisión;
- tiempo por PDF y consumo de tokens.

El sistema se considerará apto para demostración cuando no habilite cálculos
ante contradicciones, conserve trazabilidad y el profesional pueda corregir los
campos pendientes desde la interfaz.
