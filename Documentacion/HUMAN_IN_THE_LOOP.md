# Human-in-the-loop en CómputoEstIA

CómputoEstIA no debe forzar decisiones técnicas cuando la documentación es ambigua.

## Flujo

1. El sistema analiza los PDFs y detecta una inconsistencia.
2. La inconsistencia se devuelve como una decisión pendiente.
3. El ingeniero selecciona la interpretación correcta desde la interfaz.
4. La decisión exige motivo y profesional revisor.
5. La API guarda los PDFs de la sesión y registra la decisión.
6. El sistema vuelve a ejecutar el cómputo con la corrección explícita.
7. El resultado final conserva la trazabilidad de la decisión.

## Ejemplo: referencia duplicada

Si el cuadro contiene `F12` dos veces, el sistema no inventa cuál es correcta. Devuelve las dos apariciones y permite que el ingeniero asigne, por ejemplo:

- aparición 1 → F12
- aparición 2 → F13

La interfaz exige documentar el motivo. La API convierte esa decisión en una corrección de configuración para la ejecución y vuelve a procesar el proyecto.

## Rol de Ciencia de Datos

Este patrón separa tres responsabilidades:

- **DS/IA:** detectar patrones, clasificar documentos y señalar incertidumbres.
- **Ingeniería:** resolver ambigüedades que requieren criterio profesional.
- **Motor determinista:** ejecutar las cantidades usando la decisión documentada.

Así el sistema evita presentar una inferencia como si fuera una verdad técnica y, al mismo tiempo, evita bloquear el flujo de trabajo ante una inconsistencia resoluble.
