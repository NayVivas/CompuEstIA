# V12.3 — integración del lector de fichas 1.5

Fecha: 18 de octubre de 2026. API `0.4.4`, contrato `6`, build `2026-10-18-v12.3.1-cimientos-catalogo`.

## Flujo implementado

- El enrutador EXP22 sigue clasificando cada página y eligiendo fuentes estructurales. El lector 1.5 es ahora un módulo del backend: genera fichas documentales sobre los detalles seleccionados para **cimientos corridos**. Si la propuesta de sección queda incompleta, solicita OCR regional local. Asocia las fichas por documento, SHA-256, página y referencia; nunca altera longitud ni material. Ante fichas múltiples o dimensiones contradictorias conserva la propuesta anterior y pide revisión.
- El ingeniero puede abrir la planta o el detalle señalado, corregir sección, longitud, referencia y material y guardar la decisión antes del cómputo. Los motores tabular y de zapatas aisladas permanecen operativos sin inferir dimensiones rectangulares de fichas ambiguas.
- Los tipos que aparecen únicamente en el cuadro de detalles se listan en la revisión con su página de origen y sin longitud propuesta. Empiezan excluidos del total. Para incluirlos se requiere una longitud positiva y una justificación que identifique el recorrido verificado; su mera presencia en el detalle no permite atribuirles una ubicación en planta.
- En el proyecto de cimientos 09 se inspeccionaron las diez láminas; el detalle de C-1 y C-4 indica 0,30/0,70/0,40 y 0,30/0,50/0,40 m respectivamente como sección, no como longitud. La planta estructural rotula los recorridos C-2 y C-3; no se identificó otro recorrido etiquetado C-1 o C-4 en las demás láminas. Por eso esos tipos se muestran y no se cuantifican automáticamente.
- En la interfaz el recorrido visible es carga, clasificación, revisión, cálculo, análisis y modelo 3D. Al abrir un análisis se ven sus resultados directamente, sin una ficha intermedia repetida. Se quitaron entradas redundantes de navegación y cifras de ejemplo. La lista de proyectos y el dashboard muestran el hormigón confirmado del último análisis de cada proyecto; el volumen geométrico sin material se informa por separado en resultados de cimientos corridos. Los datos reales guardados en IndexedDB se conservan.
- El arranque de Windows y el frontend exigen el mismo build, para evitar conectar con un backend antiguo.

## Pruebas automatizadas

El backend ejecutó **167 pruebas**, todas correctas salvo cuatro omitidas por necesitar PDF históricos. Incluye pruebas de asociación de fichas, unidades, OCR condicional, conflicto, duplicación, rechazo de origen ajeno, tipos presentes solo en el detalle y búsqueda de referencias en dos plantas complementarias. El frontend aprobó ESLint, compilación de Vite y sus pruebas de persistencia y métricas. La compilación avisa que el paquete de JavaScript es grande; se conserva el visor 3D.

## Recorridos de API con PDF reales

Los archivos son entradas de prueba separadas y no se incluyen en este ZIP. La clasificación y el enrutamiento no recibieron roles asignados manualmente. Las decisiones usadas para llegar al cálculo son **simulaciones de la API**, no aprobaciones profesionales de esos proyectos.

| Proyecto | Documentos clasificados | Revisión resultante | Cómputo de la prueba |
| --- | ---: | --- | --- |
| Vivienda/cimientos 09 | 10 PDF, 10 páginas | 4 tipos C-1 a C-4 visibles en revisión; C-1 y C-4 figuran solo en el detalle y quedan excluidos por carecer de recorrido medido. C-2/C-3 tienen secciones 0,30/0,60 × 0,40 m y 0,30/0,80 × 0,40 m, longitudes propuestas 91,32 y 96,59 m; 6 fichas documentales 1.5 con OCR regional | 37,6874 m³ geométricos para C-2/C-3 tras confirmar propuestas y documentar las dos exclusiones. Hormigón: 0 m³ porque el material no quedó identificado. |
| Edificio 03 | 41 PDF, 41 páginas | 24 ocurrencias de zapatas; 22 con dimensiones propuestas completas y 2 Z6 pendientes | Se incluyeron solamente las 22 completas y se excluyeron las dos Z6 con motivo en la simulación: 54,096 m³ de hormigón. Cómputo parcial; no cubre referencias no interpretadas como Z-A. |
| Proyecto 8 | Un PDF, 22 páginas | Se solicitó revisión del cuadro por referencias e inconsistencias | La prueba se detuvo allí sin enviar corrección. La validación previa de V12.2 registró cómputo después de corregir la duplicidad F12/F13; ese resultado no se repite como prueba de esta entrega. |

Estos recorridos verifican que **más de un proyecto** alcanza revisión y cantidades cuando hay evidencia y decisiones válidas. No demuestran precisión universal ni cobertura completa de acero, columnas, pedestales y vigas en cualquier formato. No hay un modelo visual entrenado nuevo, ni conexión con una API paga. Tesseract puede leer cotas dibujadas, pero OCR por sí solo no interpreta toda la geometría.

Se probó también el respaldo regional directamente sobre `plano10.pdf`, vaciando las tres cotas propuestas de C-2 y C-3. Con Tesseract activo, el lector 1.5 recuperó 0,30/0,60/0,40 y 0,30/0,80/0,40 m respectivamente; dejó la longitud y el material intactos. Esta prueba de recuperación no sustituye la revisión de cotas en el proyecto.

## Instalación y límites

Desde una carpeta limpia: ejecutar `INSTALAR_WINDOWS.bat` y `VERIFICAR_ENTORNO.bat`, luego iniciar ambos servidores. También se puede iniciar cada uno desde terminal como explica `LEEME_V12_3.txt`. Los BAT no se ejecutaron en un Windows real en estas pruebas; el entorno de prueba fue Linux con Python 3.12 y Node 24. Para cómputos de infraestructura, comenzar con los PDF estructurales. Añadir arquitectura o instalaciones solo cuando aporten contexto necesario; actualmente no se computan sus partidas.

La carpeta `backend/data/modelos/exp19` es el artefacto operativo del clasificador y se conserva. El visor 3D existente se mantiene; esta versión no certifica que sus armaduras o conexiones reflejen todos los detalles de proyectos externos. Los datos desconocidos, los conflictos y los elementos no cubiertos siguen requiriendo revisión y, en su caso, cómputo externo.
