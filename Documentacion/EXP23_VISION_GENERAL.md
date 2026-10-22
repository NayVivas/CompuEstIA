# EXP23 — Base de visión general por proyectos

## Estado verificable

EXP22 clasifica **páginas** combinando texto, OCR, vectores y rasgos globales
de la imagen. Esas etiquetas no delimitan fundaciones, cimientos, vigas,
pedestales ni columnas en una página. Los conjuntos de entrenamiento de EXP19
y las anotaciones de EXP02/EXP16 son también etiquetas documentales; no son
verdad de terreno para detectar objetos. Que el sistema clasifique una página
como estructural no demuestra que pueda contar sus elementos o calcularlos.

Este incremento agrega una herramienta **local e independiente de la API**:

- inventario de PDF sueltos, carpetas de PDF o documentos multipágina;
- imágenes de páginas para marcación de contornos y recorridos;
- revisión humana, incluso páginas sin ninguna de las cinco familias;
- separación del conjunto por proyecto y rechazo de PDF duplicados entre
  proyectos;
- evaluación posterior de un detector mediante polígonos y ejes contra
  páginas totalmente revisadas.

No incluye pesos entrenados, inferencia automática ni nuevos cálculos. Las
anotaciones tampoco ingresan al motor de cómputo. Para incorporarlo al flujo de
la aplicación será necesario entrenar y comprobar un detector con varios
proyectos independientes, relacionar los objetos con cotas y detalles, y
exigir revisión para cualquier dato insuficiente o contradictorio.

## Uso en Windows, desde la terminal habitual

En PowerShell, con el entorno virtual del backend ya preparado:

```powershell
cd C:\ruta\a\ComputoEstIA\backend
.\.venv\Scripts\python.exe scripts\dataset_visual.py preparar `
  --proyecto vivienda="C:\ruta\a\Vivienda" `
  --proyecto edificio="C:\ruta\a\Edificio estructura.pdf" `
  --proyecto mercado="C:\ruta\a\Proyecto_8.pdf" `
  --split vivienda=train `
  --split edificio=validation `
  --split mercado=test `
  --salida datasets_visuales\estudio_01

.\.venv\Scripts\python.exe scripts\dataset_visual.py servir `
  --salida datasets_visuales\estudio_01 --abrir
```

Un proyecto puede ser un PDF multipágina o una carpeta con uno o más PDF.
Para preparar un primer conjunto sin particiones basta con omitir `--split`,
pero la evaluación requiere proyectos separados en `validation` o `test`.
Los identificadores de proyecto son propios del conjunto, por ejemplo
`vivienda`, `edificio`, `mercado`; no son nombres reconocidos por el motor.
El servidor de anotación escucha solamente en `127.0.0.1`. Cerrarlo con
`Ctrl+C` no borra las revisiones guardadas. Preparar de nuevo con los mismos
PDF conserva las anotaciones; si se elimina un PDF que ya tenía anotaciones,
la herramienta se detiene para evitar perder su correspondencia.

En la página de revisión, seleccione la familia y dibuje:

| Familia | Marcación permitida |
| --- | --- |
| Fundación aislada | Polígono del contorno |
| Cimiento corrido | Polígono del área o polilínea del eje |
| Pedestal | Polígono del contorno |
| Viga de riostra | Polígono del área o polilínea del eje |
| Columna | Polígono del contorno |

Marque también las páginas arquitectónicas, sanitarias, eléctricas o sin
infraestructura como **revisadas sin elementos** cuando corresponda. Esos
negativos permiten medir falsos positivos en proyectos completos. Escriba
una referencia solo si aparece en el dibujo; no la deduzca de la cercanía.
Termine cada figura y pulse **Guardar revisión**. El estado `revisada` exige
nombre del revisor. Los puntos se guardan normalizados entre 0 y 1; una línea
sin escala del plano todavía no representa metros.

El resumen se obtiene con:

```powershell
.\.venv\Scripts\python.exe scripts\dataset_visual.py validar `
  --salida datasets_visuales\estudio_01
```

La carpeta `datasets_visuales/` está excluida de Git por tamaño y porque
puede contener planos privados. Respáldela por separado con acceso adecuado.

## Contrato para evaluar un futuro detector

La salida del detector debe ser un JSON independiente. Los identificadores de
página se leen de `manifest.json`. Un ejemplo mínimo:

```json
{
  "version": 1,
  "predicciones": {
    "ID_DE_PAGINA_TEST": [
      {
        "familia": "viga_riostra",
        "geometria": "polilinea",
        "puntos": [[0.1, 0.2], [0.5, 0.2], [0.8, 0.3]]
      }
    ]
  }
}
```

Las páginas omitidas en `predicciones` se interpretan como cero detecciones.
Solo se admiten IDs de la partición evaluada. Todas las páginas de esa
partición deben estar revisadas para poder contar falsos positivos.

```powershell
.\.venv\Scripts\python.exe scripts\dataset_visual.py evaluar `
  --salida datasets_visuales\estudio_01 `
  --predicciones C:\ruta\a\predicciones_test.json --split test
```

La comparación es individual por página y familia. Para polígonos, exige
intersección sobre unión (IoU) aproximada ≥ 0,50. Para polilíneas, exige una
cobertura recíproca ≥ 0,75 dentro del 1 % del lado largo de la página. Se
emparejan objetos una sola vez y se informan aciertos, omisiones y falsos
positivos, globalmente y por familia/proyecto. Esta evaluación **no** mide si
la referencia F13 o una longitud es correcta, ni la exactitud del hormigón,
encofrado o acero. Esos datos requieren pruebas adicionales con la fuente
documental y el cómputo manual.

## Criterio para avanzar al motor de la aplicación

1. Revisar proyectos variados, no solo el caso donde el sistema funciona bien.
   Reservar proyectos completos para `test` antes de ajustar el detector.
2. Entrenar localización o segmentación sobre `train`, seleccionar parámetros
   sobre `validation` y medir una vez sobre `test`. El único proyecto con
   anotaciones de prueba no permite afirmar generalización.
3. Revisar precisión y omisiones por familia y proyecto, incluidas páginas
   negativas; inspeccionar errores de planos rotados, escaneos y cuadros.
4. Asociar cada detección corroborada con referencias, escala, cotas y detalles
   de otros planos. Si falta longitud, altura, sección o acero, solicitar
   revisión profesional y no inventar una cantidad.
5. Comparar hormigón, encofrado y acero por familia con una referencia manual
   de proyectos que no se usaron para entrenar.

La prueba inicial de preparación usó un PDF de Proyecto09, uno de Proyecto03
y el PDF multipágina Proyecto_8: 24 páginas inventariadas, sin revisiones ni
predicciones. Este resultado demuestra que la herramienta puede preparar esos
formatos de entrada; no representa precisión del detector, porque todavía
no hay tal detector entrenado.
