/** Sólo muestra recorridos confirmados que conservan ambos extremos y escala. */
export function selectReviewedContinuousSegments(results) {
  const source = results?.cimientos_corridos_tramos;
  if (!Array.isArray(source)) return [];
  return source.filter((segment) => {
    const points = [segment?.inicio, segment?.fin];
    const width = Number(segment?.ancho_base_m);
    const topWidth = Number(segment?.ancho_superior_m);
    const height = Number(segment?.altura_m);
    const scale = Number(segment?.puntos_por_metro);
    const length = Number(segment?.longitud_m);
    if (!points.every((point) => point && [point.x, point.y].every((value) => Number.isFinite(Number(value))))) return false;
    if (![width, topWidth, height, scale, length].every((value) => Number.isFinite(value) && value > 0)) return false;
    if (width < topWidth || !segment.referencia || !segment.fuente?.sha256) return false;
    const measured = Math.hypot(
      Number(points[0].x) - Number(points[1].x),
      Number(points[0].y) - Number(points[1].y),
    ) / scale;
    return Math.abs(measured - length) <= Math.max(0.04, length * 0.01);
  });
}
