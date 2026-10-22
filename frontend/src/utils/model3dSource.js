/** Una escena estructural solo puede partir de ocurrencias ubicadas en planta. */
export function selectFoundationPlanRows(results) {
  if (!results || typeof results !== "object") return [];

  for (const key of ["fundaciones_planta", "ubicaciones_fundaciones"]) {
    const rows = results[key];
    if (Array.isArray(rows) && rows.length) {
      return rows.filter((row) => row && typeof row === "object" && !Array.isArray(row));
    }
  }

  // Algunos resultados antiguos guardan ocurrencias en `fundaciones`.
  // Solo se admiten si cada fila conserva una posición verificable.
  const rows = results.fundaciones;
  if (!Array.isArray(rows)) return [];
  return rows.filter((row) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) return false;
    const position = row.posicion ?? row.centro ?? row.coordenadas;
    if (Array.isArray(position)) return position.length >= 2;
    return Boolean(position && typeof position === "object" &&
      (position.x ?? position.X) != null &&
      (position.y ?? position.Y ?? position.z ?? position.Z) != null);
  });
}
