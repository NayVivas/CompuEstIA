# Navegación v19

La navegación de proyecto se consolidó en seis módulos:

1. Resumen — estado general y métricas.
2. Documentación — archivos, clasificación y evidencia.
3. Análisis y cómputos — resultado del núcleo y cómputos especializados.
4. Revisión profesional — decisiones que requieren intervención del ingeniero.
5. Alertas — registro persistente y filtrable de alertas pendientes, informativas y resueltas.
6. Modelo 3D — visualización del modelo validado.
7. Reportes — salida/exportación del proyecto.

La antigua sección independiente `Resultados` fue retirada de la navegación y su componente fue eliminado. Los accesos históricos que intentaban abrir `Resultados` ahora vuelven a `Análisis y cómputos`.

`Revisión profesional` y `Alertas` no son fuentes alternativas de resultados: ambas leen las alertas del último resultado del núcleo. `Análisis y cómputos` es la fuente de presentación de resultados y cómputos.
