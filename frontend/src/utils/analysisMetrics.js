export function latestCompletedByProject(analyses) {
  const latest = new Map();
  for (const analysis of analyses) {
    if (analysis.status !== "Completado" || !analysis.resultado) continue;
    const previous = latest.get(analysis.projectId);
    const date = Date.parse(analysis.date) || 0;
    if (!previous || date >= (Date.parse(previous.date) || 0)) {
      latest.set(analysis.projectId, analysis);
    }
  }
  return [...latest.values()];
}

export function confirmedConcreteVolume(analyses) {
  return latestCompletedByProject(analyses).reduce(
    (sum, analysis) => sum + Number(analysis.resultado.volumen_hormigon_m3 || 0), 0,
  );
}
