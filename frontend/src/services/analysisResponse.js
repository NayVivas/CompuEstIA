export function validateAnalysisResponse(response) {
  if (!response || typeof response !== "object") {
    throw new Error("El backend devolvió una respuesta vacía. El análisis no se guardó como completado.");
  }
  if (response.estado === "requiere_revision" && response.analisis_id && response.resultado?.computos_disponibles === false && response.resultado?.incidencias?.length) return response;
  if (response.estado === "clasificacion_documental" && Array.isArray(response.enrutamiento?.documentos)) return response;
  if (response.estado === "requiere_revision_documental" && response.enrutamiento) return response;
  if (response.estado === "requiere_revision_cuadro" && response.revision_cuadro?.filas?.length) return response;
  if (response.estado === "requiere_revision_geometria" && response.revision_geometria?.elementos?.length && response.enrutamiento) return response;
  if (response.estado === "completado" && response.analisis_id && response.resultado && typeof response.resultado === "object" && !Array.isArray(response.resultado)) return response;
  throw new Error("El backend no devolvió resultados ni una revisión válida. Verificá que backend y frontend correspondan a la misma actualización y volvé a analizar.");
}
