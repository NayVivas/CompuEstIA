const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, options);
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try { const body = await res.json(); detail = body.detail || detail; } catch { /* La respuesta puede no ser JSON. */ }
    throw new Error(detail);
  }
  return res.json();
}

function datasetPath(dataset) {
  return dataset === "exp16" ? "exp16" : "exp02";
}

export function exp02Resumen(dataset = "exp02") {
  return request(`/${datasetPath(dataset)}/resumen`);
}
export function exp02Paginas(proyectoId, dataset = "exp02") {
  const q = proyectoId ? `?proyecto_id=${encodeURIComponent(proyectoId)}&limit=5000` : "?limit=5000";
  return request(`/${datasetPath(dataset)}/paginas${q}`);
}
export function exp02GuardarAnotacion(data, dataset = "exp02") {
  return request(`/${datasetPath(dataset)}/anotaciones`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
}
export function exp02ImagenUrl(proyectoId, documento, pagina, escala = 1.35, dataset = "exp02") {
  return `${API_BASE_URL}/${datasetPath(dataset)}/pagina-imagen?proyecto_id=${encodeURIComponent(proyectoId)}&documento=${encodeURIComponent(documento)}&pagina=${pagina}&escala=${escala}`;
}
export function exp02ExportarUrl(dataset = "exp02") {
  return `${API_BASE_URL}/${datasetPath(dataset)}/exportar`;
}
