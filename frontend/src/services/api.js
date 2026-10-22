import { fileHash, getDecisions, getRowCorrections, getTechnicalResolutions } from "./documentReviewStorage";

const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";
import { validateAnalysisResponse } from "./analysisResponse";

export const EXPECTED_API_CONTRACT = 6;
export const EXPECTED_API_BUILD = "2026-10-19-v12.3.2-revision-planta";

async function readError(response) {
  try {
    const body = await response.json();

    if (typeof body?.detail === "string") {
      return body.detail;
    }

    if (Array.isArray(body?.detail)) {
      return body.detail
        .map((item) => item.msg || "Dato inválido")
        .join(" · ");
    }

    return body?.message || "No se pudo completar la solicitud.";
  } catch {
    return `El servidor respondió con el estado ${response.status}.`;
  }
}

async function apiFetch(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error(
      "No se pudo conectar con el backend. Verificá que Uvicorn esté ejecutándose en el puerto 8000."
    );
  }

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export function consultarEstado() {
  return apiFetch("/estado");
}

export function assertCompatibleBackend(status) {
  if (status?.version_contrato !== EXPECTED_API_CONTRACT) {
    const received = status?.version_contrato ?? "sin identificar";
    throw new Error(
      `Backend incompatible: esta interfaz requiere el contrato ${EXPECTED_API_CONTRACT}, pero respondió ${received}. Cerrá el servidor anterior e iniciá el backend incluido en esta misma carpeta.`
    );
  }
  if (status?.build !== EXPECTED_API_BUILD) {
    const received = status?.build ?? "sin identificar";
    throw new Error(
      `Hay otro backend ejecutándose en el puerto 8000 (${received}). Cerrá sus terminales e iniciá INICIAR_BACKEND.bat de esta carpeta; debe mostrar ${EXPECTED_API_BUILD}.`
    );
  }
  return status;
}

export async function iniciarAnalisis(files, assignments = null, revision = null, projectId = null, executeCalculation = false, rowOverrides = null, technicalOverrides = null, geometryDecision = null) {
  const savedDecisions = await getDecisions(projectId);
  const hashes = new Set(await Promise.all(files.map(fileHash)));
  const decisions = savedDecisions.filter(d => hashes.has(d.sha256));
  const rowCorrections = rowOverrides ?? await getRowCorrections(projectId);
  const technicalResolutions = technicalOverrides ?? await getTechnicalResolutions(projectId);
  const form = new FormData();
  form.append("correcciones_tecnicas", JSON.stringify(rowCorrections.filter(d => hashes.has(d.sha256))));
  form.append("resoluciones_tecnicas", JSON.stringify(technicalResolutions.filter(d => hashes.has(d.sha256))));
  if (decisions.length) form.append("revision_documental", JSON.stringify(decisions));
  if (geometryDecision) form.append("revision_geometria", JSON.stringify(geometryDecision));
  form.append("ejecutar_computo", String(executeCalculation));

  files.forEach((file) => {
    form.append("archivos", file);
  });

  if (assignments) {
    form.append(
      "asignaciones",
      JSON.stringify(assignments)
    );
  }
  if (revision) form.append("revision_cuadro", JSON.stringify(revision));
  if (projectId !== null) form.append("proyecto_id", String(projectId));

  return validateAnalysisResponse(await apiFetch("/analisis/automatico/", {
    method: "POST",
    body: form,
  }));
}

export function consultarResultados(analysisId) {
  return apiFetch(`/analisis/${analysisId}/resultados/`);
}

export function documentarIncidencia(analysisId, incidentId, data) {
  return apiFetch(`/analisis/${encodeURIComponent(analysisId)}/incidencias/${encodeURIComponent(incidentId)}/documentar`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
  });
}
