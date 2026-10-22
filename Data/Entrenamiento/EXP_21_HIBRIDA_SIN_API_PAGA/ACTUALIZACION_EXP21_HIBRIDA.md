# EXP21: flujo híbrido sin dependencia obligatoria de una API paga

## Resultado

El endpoint habitual `POST /api/analisis/` conserva los cálculos existentes y
agrega tres bloques auditables:

- `clasificacion_documentos_exp19`: inferencia local por PDF;
- `validacion_clasificacion_exp19`: documentos que requieren revisión;
- `ia_generativa_opcional`: estado del proveedor, sin afectar los cálculos.

La IA generativa queda desactivada por defecto. EXP19 y el motor funcionan sin
saldo, sin clave y sin conexión a internet.

## Instalación

1. Copiar el contenido de este paquete sobre la raíz de `ComputoEstIA`.
2. Activar el entorno virtual dentro de `backend`.
3. Instalar dependencias:

```powershell
python -m pip install -r requirements.txt
```

4. Ejecutar primero las pruebas nuevas:

```powershell
python -m unittest tests.test_clasificador_exp19 -v
python -m unittest tests.test_flujo_hibrido -v
```

5. Ejecutar la batería completa:

```powershell
python -m unittest discover -s tests -v
```

## Ejecución sin pagar API

No configurar `COMPUTOESTIA_IA_GENERATIVA`, o establecerla en cero:

```powershell
$env:COMPUTOESTIA_IA_GENERATIVA="0"
python -m uvicorn computos.api:app --reload --port 8000
```

El frontend continúa usando `POST /api/analisis/` con los tres PDF habituales.

## Activación futura de la IA generativa

La activación siempre es expresa:

```powershell
$env:COMPUTOESTIA_IA_GENERATIVA="1"
$env:COMPUTOESTIA_IA_ESTRATEGIA="solo_revision"
```

`solo_revision` evita llamadas cuando EXP19 considera coherente el documento.
También existe `todos`, pensado únicamente para una evaluación controlada.

Si falta configuración, saldo o disponibilidad, el motor no se interrumpe. El
resultado informa `omitida_sin_interrumpir_motor` y conserva los cómputos.

## Ubicación de modelos

Los artefactos necesarios quedan en:

```text
backend/data/modelos/exp19/
```

La ruta puede cambiarse mediante `COMPUTOESTIA_EXP19_DIR`.

## Principio de trazabilidad

Los márgenes de Linear SVC no se presentan como porcentajes de confianza. La
respuesta conserva puntaje, umbral y margen por etiqueta. Solamente el motor
determinístico produce cantidades de hormigón, acero y encofrado.

