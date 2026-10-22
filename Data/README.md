# Datos de investigación y modelo operativo

Esta carpeta conserva los datasets, métricas y experimentos usados durante la
investigación. No forma parte del código que atiende las solicitudes de la
aplicación, salvo cuando se ejecutan scripts de entrenamiento o evaluación.

## Fuente única del modelo en producción

La única copia que usa la aplicación está en:

```text
backend/data/modelos/exp19/
```

El artefacto portátil se distribuye en cuatro partes y se valida con SHA-256.
Los `joblib` de esa misma carpeta son el respaldo local. No se deben copiar
modelos dentro de los experimentos archivados porque esas copias aumentan el
tamaño de la entrega y pueden quedar desactualizadas.

En la entrega comprimida se omiten por ese motivo los binarios duplicados de
EXP19 y EXP21 dentro de `Data/Entrenamiento`. Se mantienen sus configuraciones,
métricas, predicciones, documentación y scripts para conservar la trazabilidad
académica.

## Organización

- `Investigacion/`: experimentos históricos, datasets y evaluaciones.
- `Entrenamiento/EXP_19_Clasificador_mejorado/`: evidencia del entrenamiento
  seleccionado para EXP19.
- `Entrenamiento/EXP_21_HIBRIDA_SIN_API_PAGA/`: prototipo híbrido histórico;
  no es el backend que se ejecuta actualmente.
- `EXP_20_IA_GENERATIVA/`: experimento generativo histórico y opcional.

Las rutas guardadas en configuraciones son relativas a la raíz de
`ComputoEstIA`; no dependen de una carpeta temporal ni de un usuario de
Windows.
