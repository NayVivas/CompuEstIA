# EXP16 - Auditoría de nuevos proyectos

## Resultado general

| Indicador | Resultado |
|---|---:|
| PDF recibidos | 357 |
| Páginas analizadas | 357 |
| Proyectos principales | 16 |
| Grupos topográficos | 10 |
| Páginas topográficas | 36 |
| Archivos con error | 0 |
| Páginas que requieren OCR | 46 |
| Grupos de archivos idénticos | 0 |
| Grupos de páginas visualmente idénticas | 0 |
| Pares casi duplicados para revisar | 4 |

## Conclusión de la auditoría

El conjunto es válido para continuar con EXP16. Los 357 PDF se pudieron abrir y
cada archivo contiene una página. La colección aporta 321 láminas de proyectos
de edificación y 36 láminas almacenadas como topografía. La variedad visual es
mayor que en el conjunto histórico y los grupos se mantuvieron separados por
proyecto.

De las 357 páginas, 311 tienen texto y geometría vectorial aprovechables. Las
46 páginas restantes requieren el flujo asistido: 44 son planos vectoriales con
texto nativo insuficiente y 2 son imágenes o escaneos.

La carpeta original se llama `Topogrefia`. Se conserva ese nombre para no
alterar los archivos recibidos, pero la disciplina se normalizará como
`topografia` dentro del anotador.

## Páginas por grupo de fuente

| Grupo | Páginas |
|---|---:|
| Proyecto01_Restaurante | 43 |
| Proyecto02_colegio | 75 |
| Proyecto03_edif_5pisos | 41 |
| Proyecto04_cafeteria | 8 |
| Proyecto05_edif | 14 |
| Proyecto06_edif2 | 7 |
| Proyecto07_CampoDeportivo | 32 |
| Proyecto08_Vivienda_3Niveles | 5 |
| Proyecto09_Vivienda_multi | 10 |
| Proyecto10_vivienda_vaca | 4 |
| Proyecto11_vivienda_uni | 6 |
| Proyecto12_gimnasio | 9 |
| Proyecto13_vivienda1 | 15 |
| Proyecto14_vivienda2 | 8 |
| Proyecto15_hotel | 10 |
| Proyecto16_ | 34 |
| Topogrefia/Proyecto01 | 4 |
| Topogrefia/Proyecto02 | 3 |
| Topogrefia/Proyecto03 | 3 |
| Topogrefia/Proyecto04 | 5 |
| Topogrefia/Proyecto05 | 2 |
| Topogrefia/Proyecto06 | 2 |
| Topogrefia/Proyecto07 | 2 |
| Topogrefia/Proyecto08 | 3 |
| Topogrefia/Proyecto09 | 3 |
| Topogrefia/Sueltos_fuente_desconocida | 9 |

## Tipo de contenido

| Tipo | Páginas |
|---|---:|
| escaneado_o_imagen | 2 |
| texto_y_vectores | 311 |
| vector_sin_texto_suficiente | 44 |

## Revisión de posibles duplicados

| Página 1 | Página 2 | Evaluación |
|---|---|---|
| `Proyecto02_colegio/plano23.pdf` | `Proyecto02_colegio/plano24.pdf` | Probable copia o revisión de la misma lámina |
| `Proyecto02_colegio/plano56.pdf` | `Proyecto02_colegio/plano57.pdf` | Probable copia o revisión de la misma lámina |
| `Proyecto05_edif/plano1.pdf` | `Proyecto05_edif/plano2.pdf` | Planos diferentes con la misma plantilla |
| `Proyecto16_/plano10.pdf` | `Proyecto16_/plano7.pdf` | Planos diferentes con una composición similar |

Los dos primeros pares deben mostrarse juntos durante la anotación. No se
eliminarán automáticamente porque podrían representar revisiones con pequeñas
diferencias técnicas.

## Criterio de separación

- Cada carpeta de proyecto principal se conserva como un grupo de fuente.
- Cada subcarpeta de `Topogrefia` se conserva como un proyecto independiente.
- Los PDF topográficos sueltos se agrupan conservadoramente como una única fuente desconocida.
- Los grupos de fuente completos deberán permanecer en un único conjunto: entrenamiento, validación o prueba.
- Una página con menos de 50 caracteres nativos queda marcada para OCR asistido.
- Estar dentro de la carpeta `Topogrefia` no confirma automáticamente la etiqueta: cada lámina se revisará individualmente.

## Próximo paso recomendado

1. Confirmar si los dos primeros pares son copias, revisiones o láminas independientes.
2. Corregir únicamente los agrupamientos de fuente que conozca el usuario.
3. Importar el manifiesto en el anotador como EXP16.
4. Etiquetar primero topografía y las clases históricamente escasas.
5. Crear la partición por grupo de fuente, nunca por página individual.
