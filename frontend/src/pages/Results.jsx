import { useEffect, useMemo, useState } from "react";

import Icon from "../components/Icon";
import HormigonDetail from "../components/results/HormigonDetail";
import EncofradoDetail from "../components/results/EncofradoDetail";
import ArmadurasDetail from "../components/results/ArmadurasDetail";
import UbicacionesDetail from "../components/results/UbicacionesDetail";
import { getPdf } from "../services/documentReviewStorage";

const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

const numberFormatter = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 3,
});

const FOUNDATION_TABS = [
  {
    id: "hormigon",
    label: "Hormigón",
  },
  {
    id: "encofrado",
    label: "Encofrado",
  },
  {
    id: "acero",
    label: "Acero",
  },
  {
    id: "ubicaciones",
    label: "Ubicaciones",
  },
];

const DETAIL_TABS = {
  fundaciones: FOUNDATION_TABS,
  pedestales: [
    {
      id: "detalle",
      label: "Detalle por tipo",
    },
    {
      id: "validaciones",
      label: "Validaciones",
    },
  ],
  vigas: [
    {
      id: "tramos",
      label: "Tramos",
    },
    {
      id: "tipos",
      label: "Resumen por tipo",
    },
    {
      id: "acero",
      label: "Acero",
    },
    {
      id: "validaciones",
      label: "Validaciones",
    },
  ],
  columnas: [
    {
      id: "elementos",
      label: "Elementos",
    },
    {
      id: "directas",
      label: "Apoyos directos",
    },
    {
      id: "vinculadas",
      label: "Vinculadas por viga",
    },
    {
      id: "validaciones",
      label: "Validaciones",
    },
  ],
};

function formatNumber(value, unit = "") {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "—";
  }

  return `${numberFormatter.format(numericValue)}${
    unit ? ` ${unit}` : ""
  }`;
}

function parseLocalizedNumber(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  const normalized = String(value ?? "")
    .trim()
    .replace(/\s+/g, "")
    .replace(/,/g, ".");

  if (!normalized || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(normalized)) {
    return null;
  }

  const numericValue = Number(normalized);
  return Number.isFinite(numericValue)
    ? numericValue
    : null;
}

function formatDate(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "fecha no disponible";
  }

  return date.toLocaleString("es-AR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSection(width, height) {
  const numericWidth = Number(width);
  const numericHeight = Number(height);

  if (
    !Number.isFinite(numericWidth) ||
    !Number.isFinite(numericHeight)
  ) {
    return "No disponible";
  }

  return `${numericWidth.toFixed(2)} × ${numericHeight.toFixed(
    2
  )} m`;
}

function reviewKindForAlert(alert) {
  if (
    alert?.familia === "vigas" &&
    alert?.categoria === "inconsistencia_seccion"
  ) {
    return "beam_section";
  }

  if (
    alert?.familia === "vigas" &&
    [
      "sin_seccion",
      "pendiente_escala",
      "pendiente_revision_geometrica",
      "geometria_no_computada",
      "sin_longitud_vectorial",
    ].includes(alert?.categoria)
  ) {
    return "beam_geometry";
  }

  if (
    alert?.familia === "vigas" &&
    [
      "armadura_no_detectada",
      "armadura_ambigua",
      "pendiente_armadura",
      "pendiente_revision_detalle",
    ].includes(alert?.categoria)
  ) {
    return "beam_reinforcement";
  }

  if (
    alert?.familia === "columnas" &&
    alert?.categoria === "alturas_reales_no_disponibles"
  ) {
    return "column_heights";
  }

  if (
    alert?.familia === "columnas" &&
    alert?.categoria === "armadura_no_disponible"
  ) {
    return "column_reinforcement";
  }

  if (
    alert?.familia === "columnas" &&
    alert?.categoria === "inconsistencia_portico_columna"
  ) {
    return "portico_column_conflict";
  }

  if (
    alert?.familia === "columnas" &&
    alert?.categoria === "seccion_columna_portico_pendiente"
  ) {
    return "portico_column_section";
  }

  if (
    alert?.familia === "pedestales" &&
    alert?.categoria === "alturas_reales_no_disponibles"
  ) {
    return "pedestal_heights";
  }

  if (
    alert?.familia === "columnas" &&
    [
      "sin_columna_asociada",
      "sin_seccion_detectada",
      "pendiente_clasificacion_estructural",
      "vinculacion_geometrica_pendiente",
      "fundaciones_sin_columna",
      "fundaciones_sin_seccion",
      "columnas_pendientes_clasificacion",
    ].includes(alert?.categoria)
  ) {
    return "column_relationship";
  }

  return alert?.excluido_del_computo
    ? "observation"
    : "documented_confirmation";
}

const REQUIRED_DATA_CATEGORIES = new Set([
  "alturas_reales_no_disponibles",
  "armadura_no_disponible",
  "armadura_no_detectada",
  "pendiente_armadura",
  "sin_seccion",
  "pendiente_escala",
  "geometria_no_computada",
  "sin_longitud_vectorial",
  "inconsistencia_portico_columna",
  "seccion_columna_portico_pendiente",
]);

const OBSERVATION_CATEGORIES = new Set([
  "advertencia_lectura",
  "requiere_modo_asistido",
]);

const INCONSISTENCY_CATEGORIES = new Set([
  "inconsistencia_seccion",
  "conteo_ubicaciones_inconsistente",
  "conteo_inconsistente",
]);

function alertWorkflowClass(alert) {
  if (
    [
      "dato_requerido",
      "inconsistencia",
      "revision_tecnica",
      "observacion",
    ].includes(alert?.clase_alerta)
  ) {
    return alert.clase_alerta;
  }

  const category = String(alert?.categoria || "");

  if (REQUIRED_DATA_CATEGORIES.has(category)) {
    return "dato_requerido";
  }

  if (OBSERVATION_CATEGORIES.has(category)) {
    return "observacion";
  }

  if (
    INCONSISTENCY_CATEGORIES.has(category) ||
    category.includes("inconsisten")
  ) {
    return "inconsistencia";
  }

  return "revision_tecnica";
}

function alertActionLabel(alert) {
  const workflowClass = alertWorkflowClass(alert);

  if (workflowClass === "dato_requerido") {
    return "Completar datos";
  }

  if (workflowClass === "observacion") {
    return "Revisar observación";
  }

  if (workflowClass === "revision_tecnica") {
    return "Resolver revisión";
  }

  return "Revisar inconsistencia";
}

function buildAnalysisAlerts(results) {
  if (!results || typeof results !== "object") {
    return [];
  }

  const alerts = [];
  const identifiers = new Set();

  const addAlert = (alert) => {
    if (
      alert?.resuelta ||
      alert?.estado === "resuelta"
    ) {
      return;
    }

    const id = String(
      alert?.id || `alerta-${alerts.length + 1}`
    );

    if (identifiers.has(id)) {
      return;
    }

    identifiers.add(id);

    const rawEvidence = alert?.evidencia;
    const evidence = Array.isArray(rawEvidence)
      ? rawEvidence
      : rawEvidence && typeof rawEvidence === "object"
        ? Object.entries(rawEvidence).map(
            ([etiqueta, valor]) => ({
              etiqueta,
              valor,
            })
          )
        : [];

    alerts.push({
      id,
      severidad: alert?.severidad || "advertencia",
      familia: alert?.familia || "general",
      categoria: alert?.categoria || "inconsistencia",
      clase_alerta: alertWorkflowClass(alert),
      titulo: alert?.titulo || "Inconsistencia detectada",
      mensaje: alert?.mensaje || "Requiere revisión.",
      elemento_id: alert?.elemento_id || null,
      referencia: alert?.referencia || null,
      evidencia: evidence.filter(
        (item) =>
          item &&
          item.valor !== null &&
          item.valor !== undefined &&
          item.valor !== ""
      ),
      accion_recomendada:
        alert?.accion_recomendada || null,
      bloquea_resultado: Boolean(
        alert?.bloquea_resultado
      ),
      excluido_del_computo: Boolean(
        alert?.excluido_del_computo
      ),
      revisable: Boolean(alert?.revisable),
      estado_revision: alert?.estado_revision || null,
    });
  };

  const backendAlerts = Array.isArray(
    results.alertas_analisis
  )
    ? results.alertas_analisis
    : [];

  backendAlerts.forEach((alert) =>
    addAlert({
      ...alert,
      revisable: true,
    })
  );

  // Compatibilidad con análisis generados antes de incorporar
  // la lista normalizada de alertas en el backend.
  if (backendAlerts.length === 0) {
    const beamRows = Array.isArray(
      results.vigas_riostra_computo_detalle
    )
      ? results.vigas_riostra_computo_detalle
      : [];

    beamRows.forEach((row, index) => {
      const segmentId = String(
        row?.tramo_id ||
          row?.identificador ||
          `tramo-${index + 1}`
      );

      if (row?.estado && row.estado !== "computado") {
        addAlert({
          id: `vigas-geometria-${segmentId}`,
          severidad: "advertencia",
          familia: "vigas",
          categoria: row.estado,
          titulo: `Tramo de viga no computado — ${segmentId}`,
          mensaje:
            "El tramo quedó fuera de los totales hasta completar su validación geométrica.",
          elemento_id: segmentId,
          referencia: row.referencia,
          evidencia: [
            {
              etiqueta: "Rótulo",
              valor: row.texto_original,
            },
            {
              etiqueta: "Apoyos",
              valor: `${row.apoyo_inicial_id || "—"} → ${
                row.apoyo_final_id || "—"
              }`,
            },
            {
              etiqueta: "Estado",
              valor: row.estado,
            },
          ],
          accion_recomendada:
            "Revisar el rótulo, los apoyos y la escala del tramo.",
          excluido_del_computo: true,
        });
        return;
      }

      if (
        !row?.estado_acero ||
        row.estado_acero === "computado"
      ) {
        return;
      }

      const isSectionMismatch =
        row.estado_acero ===
        "seccion_no_coincide_con_detalle";

      const category = isSectionMismatch
        ? "inconsistencia_seccion"
        : row.estado_acero;

      addAlert({
        id: `vigas-acero-${segmentId}-${category}`,
        severidad: "advertencia",
        familia: "vigas",
        categoria: category,
        titulo: isSectionMismatch
          ? `Sección incompatible entre planta y detalle — ${segmentId}`
          : `Acero del tramo pendiente — ${segmentId}`,
        mensaje: isSectionMismatch
          ? "La sección de la planta no coincide con el detalle de armadura. El tramo fue excluido del subtotal de acero."
          : "Falta validar información necesaria para calcular el acero del tramo.",
        elemento_id: segmentId,
        referencia: row.referencia,
        evidencia: [
          {
            etiqueta: "Rótulo en planta",
            valor: row.texto_original,
          },
          {
            etiqueta: "Sección en planta",
            valor: formatSection(row.ancho_m, row.alto_m),
          },
          {
            etiqueta: "Detalle de armadura",
            valor: formatSection(
              row.armadura_viga?.ancho_m,
              row.armadura_viga?.alto_m
            ),
          },
          {
            etiqueta: "Apoyos",
            valor: `${row.apoyo_inicial_id || "—"} → ${
              row.apoyo_final_id || "—"
            }`,
          },
          {
            etiqueta: "Longitud entre ejes",
            valor:
              row.longitud_entre_ejes_m === null ||
              row.longitud_entre_ejes_m === undefined
                ? null
                : `${formatNumber(
                    row.longitud_entre_ejes_m
                  )} m`,
          },
        ],
        accion_recomendada: isSectionMismatch
          ? "Solicitar una aclaración del proyectista o registrar una corrección documentada."
          : "Revisar el detalle estructural correspondiente.",
        excluido_del_computo: true,
      });
    });

    const pendingColumns = Array.isArray(
      results.columnas_pendientes_clasificacion
    )
      ? results.columnas_pendientes_clasificacion
      : [];

    pendingColumns.forEach((row, index) => {
      addAlert({
        id: `columnas-pendiente-${
          row.fundacion_id || index + 1
        }-${row.referencia_columna || "sin-columna"}`,
        severidad: "advertencia",
        familia: "columnas",
        categoria:
          row.estado || "pendiente_clasificacion_estructural",
        titulo: `Asociación de columna pendiente — ${
          row.referencia_columna || row.fundacion_id || "elemento"
        }`,
        mensaje:
          "La relación entre columna y fundación todavía requiere validación geométrica.",
        elemento_id:
          row.referencia_columna || row.fundacion_id,
        referencia: row.referencia_columna,
        evidencia: [
          {
            etiqueta: "Fundación",
            valor: row.fundacion_id,
          },
          {
            etiqueta: "Columna",
            valor: row.referencia_columna,
          },
          {
            etiqueta: "Estado",
            valor: row.estado,
          },
        ],
        accion_recomendada:
          "Revisar la relación espacial en la planta.",
        excluido_del_computo: true,
      });
    });
  }

  const locationValidation =
    results.validacion_ubicaciones || {};

  if (
    locationValidation.coincide_con_resumen === false
  ) {
    const differences = Array.isArray(
      locationValidation.diferencias
    )
      ? locationValidation.diferencias
      : [];

    if (differences.length > 0) {
      differences.forEach((difference, index) => {
        addAlert({
          id: `fundaciones-ubicacion-${
            difference.referencia || index + 1
          }`,
          severidad: "advertencia",
          familia: "fundaciones",
          categoria: "conteo_ubicaciones_inconsistente",
          titulo: `Cantidad de ubicaciones incompatible — ${
            difference.referencia || "referencia"
          }`,
          mensaje:
            "La cantidad de rótulos ubicados en la planta no coincide con el resumen de fundaciones.",
          elemento_id: difference.referencia,
          referencia: difference.referencia,
          evidencia: [
            {
              etiqueta: "Cantidad esperada",
              valor: difference.cantidad_esperada,
            },
            {
              etiqueta: "Cantidad detectada",
              valor: difference.cantidad_detectada,
            },
          ],
          accion_recomendada:
            "Revisar los rótulos de fundación detectados en la planta.",
          excluido_del_computo: false,
        });
      });
    } else {
      addAlert({
        id: "fundaciones-ubicaciones-resumen",
        severidad: "advertencia",
        familia: "fundaciones",
        categoria: "conteo_ubicaciones_inconsistente",
        titulo: "Las ubicaciones no coinciden con el resumen",
        mensaje:
          "La cantidad de fundaciones ubicadas difiere de la cantidad computada.",
        evidencia: [
          {
            etiqueta: "Esperadas",
            valor: locationValidation.cantidad_esperada,
          },
          {
            etiqueta: "Detectadas",
            valor: locationValidation.cantidad_detectada,
          },
        ],
        accion_recomendada:
          "Revisar la detección de rótulos en la planta.",
      });
    }
  }

  const documents = Array.isArray(results.documentos)
    ? results.documentos
    : [];

  documents.forEach((document) => {
    if (!document?.requiere_modo_asistido) {
      return;
    }

    addAlert({
      id: `documento-modo-asistido-${document.nombre}`,
      severidad: "advertencia",
      familia: "documentos",
      categoria: "requiere_modo_asistido",
      titulo: `Documento que requiere revisión — ${document.nombre}`,
      mensaje:
        "El contenido del documento no pudo interpretarse completamente mediante el flujo vectorial automático.",
      elemento_id: document.nombre,
      evidencia: [
        {
          etiqueta: "Tipo de contenido",
          valor: document.tipo_contenido,
        },
        {
          etiqueta: "Páginas",
          valor: document.cantidad_paginas,
        },
      ],
      accion_recomendada:
        "Revisar el documento y utilizar el modo asistido.",
      excluido_del_computo: false,
    });
  });

  const priority = {
    error: 0,
    advertencia: 1,
    informacion: 2,
  };

  return alerts.sort(
    (first, second) =>
      (priority[first.severidad] ?? 9) -
        (priority[second.severidad] ?? 9) ||
      String(first.familia).localeCompare(
        String(second.familia),
        "es"
      ) ||
      String(first.id).localeCompare(String(second.id), "es")
  );
}

function ProgressSteps({ currentStep }) {
  const steps = [
    {
      number: "01",
      label: "Cargar planos",
    },
    {
      number: "02",
      label: "Procesar",
    },
    {
      number: "03",
      label: "Revisar resultados",
    },
  ];

  return (
    <div className="mb-8 flex items-center gap-3 overflow-x-auto pb-1">
      {steps.map((step, index) => {
        const active =
          index === currentStep;

        const completed =
          index < currentStep;

        return (
          <div
            key={step.number}
            className="flex items-center gap-3"
          >
            <div
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                active
                  ? "bg-slate-950 text-white"
                  : completed
                    ? "bg-accent text-white"
                    : "bg-slate-100 text-slate-400"
              }`}
            >
              {completed ? (
                <Icon
                  name="check"
                  size={16}
                />
              ) : (
                step.number
              )}
            </div>

            <span
              className={`whitespace-nowrap text-sm font-semibold ${
                active
                  ? "text-ink"
                  : completed
                    ? "text-slate-600"
                    : "text-slate-400"
              }`}
            >
              {step.label}
            </span>

            {index <
              steps.length - 1 && (
              <div className="mx-1 h-px w-8 bg-slate-200" />
            )}
          </div>
        );
      })}
    </div>
  );
}

function BeamMetric({ label, value, detail }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <span className="text-[9px] font-extrabold uppercase tracking-[0.13em] text-slate-400">
        {label}
      </span>

      <strong className="mt-2 block font-display text-xl font-bold tracking-tight text-ink">
        {value}
      </strong>

      <span className="mt-1 block text-[10px] leading-4 text-slate-400">
        {detail}
      </span>
    </div>
  );
}

function ComputationStatus({ status }) {
  const styles = {
    calculado:
      "border-emerald-200 bg-emerald-50 text-emerald-700",
    preliminar:
      "border-amber-200 bg-amber-50 text-amber-700",
    parcial:
      "border-cyan-200 bg-cyan-50 text-cyan-700",
    pendiente:
      "border-slate-200 bg-slate-100 text-slate-500",
  };

  const labels = {
    calculado: "Calculado",
    preliminar: "Preliminar",
    parcial: "Parcial",
    pendiente: "Pendiente",
  };

  return (
    <span
      className={`inline-flex rounded-full border px-2 py-1 text-[8px] font-extrabold uppercase tracking-wider ${
        styles[status] || styles.pendiente
      }`}
    >
      {labels[status] || labels.pendiente}
    </span>
  );
}

function MaterialSummary({ materials = [] }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {materials.map((material) => (
        <div
          key={material.label}
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_8px_24px_rgba(16,34,53,.045)]"
        >
          <div className="flex items-start justify-between gap-3">
            <span className="text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
              {material.label}
            </span>

            <ComputationStatus
              status={material.status}
            />
          </div>

          <strong className="mt-3 block font-display text-2xl font-black tracking-tight text-ink">
            {material.value}
          </strong>

          <span className="mt-1 block text-[10px] leading-4 text-slate-400">
            {material.detail}
          </span>
        </div>
      ))}
    </div>
  );
}

function DetailTabs({ tabs, activeTab, onChange }) {
  return (
    <div
      className="flex max-w-full overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-1"
      role="tablist"
      aria-label="Secciones del cómputo"
    >
      {tabs.map((tab) => {
        const selected = activeTab === tab.id;

        return (
          <button
            key={tab.id}
            className={`whitespace-nowrap rounded-lg px-4 py-2 text-[10px] font-extrabold uppercase tracking-wider transition ${
              selected
                ? "bg-white text-ink shadow-sm"
                : "text-slate-400 hover:text-ink"
            }`}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

function FamilyStatusBanner({ tone, title, description }) {
  const isSuccess = tone === "success";

  return (
    <div
      className={`flex items-start gap-3 rounded-2xl border p-4 ${
        isSuccess
          ? "border-emerald-200 bg-emerald-50"
          : "border-amber-200 bg-amber-50"
      }`}
    >
      <span
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-xs font-black shadow-sm ${
          isSuccess
            ? "text-emerald-600"
            : "text-amber-600"
        }`}
      >
        {isSuccess ? (
          <Icon name="check" size={17} />
        ) : (
          <span aria-hidden="true">!</span>
        )}
      </span>

      <div>
        <strong
          className={`block text-xs font-extrabold ${
            isSuccess
              ? "text-emerald-900"
              : "text-amber-900"
          }`}
        >
          {title}
        </strong>

        <span
          className={`mt-1 block text-[11px] leading-5 ${
            isSuccess
              ? "text-emerald-800/80"
              : "text-amber-800/80"
          }`}
        >
          {description}
        </span>
      </div>
    </div>
  );
}

function AlertSeverityBadge({ severity }) {
  const styles = {
    error:
      "border-red-200 bg-red-50 text-red-700",
    advertencia:
      "border-amber-200 bg-amber-50 text-amber-700",
    informacion:
      "border-sky-200 bg-sky-50 text-sky-700",
  };

  const labels = {
    error: "Error",
    advertencia: "Advertencia",
    informacion: "Información",
  };

  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[8px] font-extrabold uppercase tracking-wider ${
        styles[severity] || styles.advertencia
      }`}
    >
      {labels[severity] || labels.advertencia}
    </span>
  );
}

function AnalysisAlerts({
  alerts = [],
  title = "Alertas del análisis",
  description =
    "Estas observaciones requieren revisión antes de aprobar el cómputo.",
  onReviewAlert,
}) {
  if (alerts.length === 0) {
    return null;
  }

  const familyLabels = {
    fundaciones: "Fundaciones",
    pedestales: "Pedestales",
    vigas: "Vigas de riostra",
    columnas: "Columnas",
    documentos: "Documentos",
    general: "General",
  };

  const excludedCount = alerts.filter(
    (alert) => alert.excluido_del_computo
  ).length;

  return (
    <section className="mt-6 overflow-hidden rounded-3xl border border-amber-200 bg-white shadow-[0_16px_40px_rgba(120,53,15,.07)]">
      <div className="flex flex-col justify-between gap-3 border-b border-amber-100 bg-amber-50/70 px-5 py-4 sm:flex-row sm:items-center">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-sm font-black text-amber-600 shadow-sm">
            !
          </span>

          <div>
            <h2 className="font-display text-base font-bold text-amber-950">
              {title}
            </h2>

            <p className="mt-1 text-[11px] leading-5 text-amber-800/80">
              {description}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <span className="rounded-full border border-amber-200 bg-white px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-amber-700">
            {alerts.length} {alerts.length === 1 ? "alerta" : "alertas"}
          </span>

          {excludedCount > 0 && (
            <span className="rounded-full border border-red-200 bg-red-50 px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-red-700">
              {excludedCount} fuera del cómputo
            </span>
          )}
        </div>
      </div>

      <div className="max-h-[560px] space-y-3 overflow-auto p-4 sm:p-5">
        {alerts.map((alert) => (
          <article
            key={alert.id}
            className={`rounded-2xl border p-4 ${
              alert.severidad === "error"
                ? "border-red-200 bg-red-50/45"
                : alert.severidad === "informacion"
                  ? "border-sky-200 bg-sky-50/45"
                  : "border-amber-200 bg-amber-50/45"
            }`}
          >
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <AlertSeverityBadge
                    severity={alert.severidad}
                  />

                  <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[8px] font-extrabold uppercase tracking-wider text-slate-500">
                    {familyLabels[alert.familia] ||
                      alert.familia}
                  </span>

                  {alert.excluido_del_computo && (
                    <span className="rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-[8px] font-extrabold uppercase tracking-wider text-red-700">
                      Excluido del cómputo
                    </span>
                  )}

                  {alert.estado_revision ===
                    "revisada_sin_resolver" && (
                    <span className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-[8px] font-extrabold uppercase tracking-wider text-violet-700">
                      Revisada · seguimiento abierto
                    </span>
                  )}
                </div>

                <h3 className="mt-3 font-display text-sm font-bold text-ink">
                  {alert.titulo}
                </h3>

                <p className="mt-1 text-[11px] leading-5 text-slate-600">
                  {alert.mensaje}
                </p>
              </div>

              {(alert.elemento_id || alert.referencia) && (
                <span className="shrink-0 rounded-xl border border-slate-200 bg-white px-3 py-2 text-[10px] font-black text-ink shadow-sm">
                  {alert.elemento_id || alert.referencia}
                </span>
              )}
            </div>

            {alert.evidencia.length > 0 && (
              <dl className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {alert.evidencia.map((item, index) => (
                  <div
                    key={`${alert.id}-${item.etiqueta}-${index}`}
                    className="rounded-xl border border-white/80 bg-white/80 px-3 py-2.5"
                  >
                    <dt className="text-[8px] font-extrabold uppercase tracking-wider text-slate-400">
                      {item.etiqueta}
                    </dt>

                    <dd className="mt-1 break-words text-[11px] font-bold text-slate-700">
                      {String(item.valor)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}

            {alert.accion_recomendada && (
              <div className="mt-3 rounded-xl border border-slate-200/80 bg-white px-3 py-2.5 text-[10px] leading-5 text-slate-600">
                <strong className="text-ink">
                  Acción recomendada:
                </strong>{" "}
                {alert.accion_recomendada}
              </div>
            )}

            {alert.revisable && onReviewAlert && (
                <div className="mt-4 flex justify-end">
                  <button
                    className="inline-flex min-h-10 items-center justify-center rounded-xl bg-amber-600 px-4 text-[10px] font-extrabold uppercase tracking-wider text-white shadow-sm transition hover:-translate-y-px hover:bg-amber-700"
                    type="button"
                    onClick={() =>
                      onReviewAlert(alert)
                    }
                  >
                    {alertActionLabel(alert)}
                  </button>
                </div>
              )}
          </article>
        ))}
      </div>
    </section>
  );
}

function PreviousReviewStatus({ audit }) {
  if (!audit || !Array.isArray(audit.incidencias)) {
    return null;
  }

  const resolved = audit.incidencias.filter(
    (item) => item?.resuelta
  );
  const pending = audit.incidencias.filter(
    (item) => !item?.resuelta
  );

  if (resolved.length === 0 && pending.length === 0) {
    return null;
  }

  const isComplete = pending.length === 0;

  return (
    <section
      className={`mt-6 rounded-2xl border px-5 py-4 ${
        isComplete
          ? "border-emerald-200 bg-emerald-50"
          : "border-amber-200 bg-amber-50"
      }`}
    >
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <p
            className={`text-[9px] font-extrabold uppercase tracking-[0.18em] ${
              isComplete
                ? "text-emerald-700"
                : "text-amber-700"
            }`}
          >
            Revisión anterior al cómputo
          </p>
          <h2
            className={`mt-1 font-display text-base font-bold ${
              isComplete
                ? "text-emerald-950"
                : "text-amber-950"
            }`}
          >
            {isComplete
              ? "Las correcciones fueron conservadas"
              : "Hay hallazgos documentales todavía abiertos"}
          </h2>
          <p
            className={`mt-1 text-[11px] leading-5 ${
              isComplete
                ? "text-emerald-800/80"
                : "text-amber-800/80"
            }`}
          >
            {isComplete
              ? "El motor recibió las decisiones profesionales y no volvió a abrir los conflictos documentales ya resueltos."
              : "El cómputo parcial conservó las decisiones aplicadas, pero estos hallazgos previos aún requieren revisión."}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          {resolved.length > 0 && (
            <span className="rounded-full border border-emerald-200 bg-white px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-emerald-700">
              {resolved.length} {resolved.length === 1 ? "corrección aplicada" : "correcciones aplicadas"}
            </span>
          )}
          {pending.length > 0 && (
            <span className="rounded-full border border-amber-200 bg-white px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-amber-700">
              {pending.length} {pending.length === 1 ? "hallazgo abierto" : "hallazgos abiertos"}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

function SectionReviewDialog({
  alert,
  segment,
  saving = false,
  error = "",
  onClose,
  onConfirm,
}) {
  const [source, setSource] = useState("detalle");
  const [manualWidth, setManualWidth] = useState(
    segment?.ancho_m ?? ""
  );
  const [manualHeight, setManualHeight] = useState(
    segment?.alto_m ?? ""
  );
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [confirmReinforcement, setConfirmReinforcement] =
    useState(false);

  const detail = segment?.armadura_viga || {};
  const manualIsValid =
    source !== "manual" ||
    (Number(manualWidth) > 0 &&
      Number(manualHeight) > 0);
  const formIsValid =
    reviewer.trim().length >= 2 &&
    reason.trim().length >= 10 &&
    confirmReinforcement &&
    manualIsValid;

  const sourceOptions = [
    {
      id: "planta",
      title: "Usar sección de planta",
      value: formatSection(
        segment?.ancho_m,
        segment?.alto_m
      ),
      description:
        "Conserva la sección leída en el rótulo del tramo.",
    },
    {
      id: "detalle",
      title: "Usar sección del detalle",
      value: formatSection(
        detail?.ancho_m,
        detail?.alto_m
      ),
      description:
        "Alinea la geometría con el detalle de armadura detectado.",
    },
    {
      id: "manual",
      title: "Ingresar sección verificada",
      value: "Definida por el profesional",
      description:
        "Para una aclaración, plano corregido o verificación externa.",
    },
  ];

  const handleSubmit = (event) => {
    event.preventDefault();

    if (!formIsValid || saving) {
      return;
    }

    onConfirm({
      alerta_id: alert.id,
      tramo_id: alert.elemento_id,
      fuente_seleccionada: source,
      ancho_m:
        source === "manual"
          ? Number(manualWidth)
          : null,
      alto_m:
        source === "manual"
          ? Number(manualHeight)
          : null,
      motivo: reason.trim(),
      revisor: reviewer.trim(),
      confirmar_armadura_detalle:
        confirmReinforcement,
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) {
          onClose();
        }
      }}
    >
      <section
        aria-labelledby="section-review-title"
        aria-modal="true"
        className="max-h-[92vh] w-full max-w-3xl overflow-auto rounded-3xl border border-slate-200 bg-white shadow-2xl"
        role="dialog"
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-100 bg-white/95 px-5 py-4 backdrop-blur sm:px-7">
          <div>
            <p className="text-[9px] font-extrabold uppercase tracking-[0.18em] text-amber-600">
              Decisión profesional auditable
            </p>
            <h2
              className="mt-1 font-display text-xl font-bold text-ink"
              id="section-review-title"
            >
              Validar sección de {alert.elemento_id}
            </h2>
            <p className="mt-1 text-[11px] leading-5 text-slate-500">
              La decisión recalculará hormigón, encofrado y acero
              únicamente para este tramo.
            </p>
          </div>

          <button
            aria-label="Cerrar revisión"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-lg text-slate-400 transition hover:bg-slate-50 hover:text-ink disabled:opacity-50"
            disabled={saving}
            type="button"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <form
          className="space-y-6 p-5 sm:p-7"
          noValidate
          onSubmit={handleSubmit}
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <BeamMetric
              label="Tramo"
              value={segment?.tramo_id || "—"}
              detail={segment?.texto_original || "Rótulo no disponible"}
            />
            <BeamMetric
              label="Sección en planta"
              value={formatSection(
                segment?.ancho_m,
                segment?.alto_m
              )}
              detail="Lectura del rótulo"
            />
            <BeamMetric
              label="Sección del detalle"
              value={formatSection(
                detail?.ancho_m,
                detail?.alto_m
              )}
              detail="Detalle de armadura asociado"
            />
          </div>

          <fieldset>
            <legend className="text-xs font-extrabold text-ink">
              1. Seleccioná la sección válida
            </legend>

            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              {sourceOptions.map((option) => (
                <label
                  key={option.id}
                  className={`cursor-pointer rounded-2xl border p-4 transition ${
                    source === option.id
                      ? "border-accent bg-accent/5 shadow-[0_0_0_1px_rgba(36,183,166,.15)]"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <span className="flex items-start gap-3">
                    <input
                      checked={source === option.id}
                      className="mt-0.5 accent-teal-600"
                      name="section-source"
                      type="radio"
                      value={option.id}
                      onChange={() => setSource(option.id)}
                    />
                    <span>
                      <strong className="block text-[11px] text-ink">
                        {option.title}
                      </strong>
                      <span className="mt-1 block text-xs font-black text-accent-dark">
                        {option.value}
                      </span>
                      <span className="mt-1 block text-[9px] leading-4 text-slate-400">
                        {option.description}
                      </span>
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          {source === "manual" && (
            <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:grid-cols-2">
              <label className="text-[10px] font-bold text-slate-600">
                Ancho verificado (m)
                <input
                  className="mt-2 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs outline-none focus:border-accent"
                  min="0.01"
                  required
                  step="0.01"
                  type="number"
                  value={manualWidth}
                  onChange={(event) =>
                    setManualWidth(event.target.value)
                  }
                />
              </label>

              <label className="text-[10px] font-bold text-slate-600">
                Alto verificado (m)
                <input
                  className="mt-2 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs outline-none focus:border-accent"
                  min="0.01"
                  required
                  step="0.01"
                  type="number"
                  value={manualHeight}
                  onChange={(event) =>
                    setManualHeight(event.target.value)
                  }
                />
              </label>
            </div>
          )}

          <div>
            <h3 className="text-xs font-extrabold text-ink">
              2. Registrá el responsable y el criterio
            </h3>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-[10px] font-bold text-slate-600">
                Profesional revisor
                <input
                  className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent"
                  placeholder="Nombre y matrícula, si corresponde"
                  required
                  value={reviewer}
                  onChange={(event) =>
                    setReviewer(event.target.value)
                  }
                />
              </label>

              <label className="text-[10px] font-bold text-slate-600 sm:row-span-2">
                Motivo de la decisión
                <textarea
                  className="mt-2 min-h-24 w-full resize-y rounded-xl border border-slate-200 p-3 text-xs outline-none focus:border-accent"
                  minLength={10}
                  placeholder="Ej.: verificado contra plano estructural revisado..."
                  required
                  value={reason}
                  onChange={(event) =>
                    setReason(event.target.value)
                  }
                />
              </label>
            </div>
          </div>

          <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <input
              checked={confirmReinforcement}
              className="mt-0.5 accent-amber-600"
              type="checkbox"
              onChange={(event) =>
                setConfirmReinforcement(event.target.checked)
              }
            />
            <span className="text-[10px] leading-5 text-amber-900">
              Confirmo que la armadura extraída del detalle asociado
              corresponde a este tramo y puede utilizarse para el
              recálculo con la sección validada.
            </span>
          </label>

          {error && (
            <div
              className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[11px] font-semibold text-red-700"
              role="alert"
            >
              {error}
            </div>
          )}

          <div className="flex flex-col-reverse gap-2 border-t border-slate-100 pt-5 sm:flex-row sm:justify-end">
            <button
              className="min-h-11 rounded-xl border border-slate-200 px-5 text-xs font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
              disabled={saving}
              type="button"
              onClick={onClose}
            >
              Cancelar
            </button>

            <button
              className="min-h-11 rounded-xl bg-accent px-5 text-xs font-extrabold text-white shadow-sm transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!formIsValid || saving}
              type="submit"
            >
              {saving
                ? "Recalculando…"
                : "Validar y recalcular tramo"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function alertEvidenceValue(alert, label) {
  const target = String(label).toLocaleLowerCase("es");

  return alert?.evidencia?.find(
    (item) =>
      String(item?.etiqueta || "").toLocaleLowerCase(
        "es"
      ) === target
  )?.valor;
}

function referencesFromAlertEvidence(alert) {
  const labels = new Set([
    "referencias pendientes",
    "referencias afectadas",
  ]);

  return [
    ...new Set(
      (alert?.evidencia || [])
        .filter((item) =>
          labels.has(
            String(item?.etiqueta || "")
              .trim()
              .toLocaleLowerCase("es")
          )
        )
        .flatMap((item) =>
          String(item?.valor || "")
            .split(/[,;\n]/)
            .map((reference) =>
              reference.trim().toUpperCase()
            )
            .filter(Boolean)
        )
    ),
  ];
}

function reviewReferences(results, family, alert) {
  const rows =
    family === "columnas"
      ? [
          ...(results?.columnas_porticos_segmentos || []).filter(
            (item) => item?.apto_revision_altura
          ),
          ...(results?.columnas_fundaciones || []),
          ...(results?.columnas_vinculadas_por_viga || []),
        ]
      : results?.pedestales_computo_detalle || [];

  const rowReferences = [
    ...new Set(
      rows
        .map((item) =>
          String(
            item?.referencia_columna ||
              item?.referencia_columna_vinculada ||
              item?.referencia ||
              ""
          )
            .trim()
            .toUpperCase()
        )
        .filter(Boolean)
    ),
  ].sort((first, second) =>
    first.localeCompare(second, "es", {
      numeric: true,
    })
  );

  if (rowReferences.length > 0) {
    return rowReferences;
  }

  return referencesFromAlertEvidence(alert).sort(
    (first, second) =>
      first.localeCompare(second, "es", {
        numeric: true,
      })
  );
}

function GeneralEngineeringReviewForm({
  alert,
  results,
  segment,
  saving,
  error,
  onClose,
  onConfirm,
}) {
  const kind = reviewKindForAlert(alert);
  const heightFamily =
    kind === "column_heights"
      ? "columnas"
      : "pedestales";
  const heightReferences = useMemo(
    () =>
      ["column_heights", "pedestal_heights"].includes(
        kind
      )
        ? reviewReferences(results, heightFamily, alert)
        : [],
    [results, heightFamily, kind, alert]
  );
  const heightSegments = useMemo(
    () =>
      kind === "column_heights"
        ? (results?.columnas_porticos_segmentos || []).filter(
            (item) => item?.apto_revision_altura
          )
        : [],
    [results, kind]
  );
  const heightItems = useMemo(
    () =>
      heightSegments.length > 0
        ? heightSegments.map((item) => ({
            id: item.tramo_id,
            label: [
              item.referencia,
              item.eje_global,
              item.nivel_inferior && item.nivel_superior
                ? `${item.nivel_inferior}–${item.nivel_superior}`
                : null,
            ]
              .filter(Boolean)
              .join(" · "),
            proposedHeight: item.altura_detectada_m,
            pages: item.paginas || [],
          }))
        : heightReferences.map((reference) => ({
            id: reference,
            label: reference,
            proposedHeight: null,
            pages: [],
          })),
    [heightSegments, heightReferences]
  );
  const columnReinforcementReferences = useMemo(
    () =>
      kind === "column_reinforcement"
        ? reviewReferences(results, "columnas", alert)
        : [],
    [results, kind, alert]
  );
  const columnReinforcements = useMemo(
    () =>
      new Map(
        (results?.armaduras_columnas || [])
          .filter((item) => item?.referencia)
          .map((item) => [
            String(item.referencia).trim().toUpperCase(),
            item,
          ])
      ),
    [results]
  );
  const incompleteColumnReinforcements = useMemo(
    () =>
      columnReinforcementReferences.filter((reference) => {
        const candidate = columnReinforcements.get(reference);
        const stirrup = candidate?.estribo;

        return !(
          candidate?.estado === "CORRECTO" &&
          Array.isArray(candidate?.grupos_longitudinales) &&
          candidate.grupos_longitudinales.length > 0 &&
          stirrup &&
          parseLocalizedNumber(stirrup.separacion_m) > 0 &&
          parseLocalizedNumber(stirrup.longitud_indicada_m) > 0 &&
          stirrup.diametro_pulgadas
        );
      }),
    [
      columnReinforcementReferences,
      columnReinforcements,
    ]
  );
  const columnHeightsReady =
    results?.validacion_columnas
      ?.altura_real_disponible === true;
  const pendingPorticoConflicts = (
    results?.alertas_analisis || []
  ).filter(
    (item) =>
      item?.familia === "columnas" &&
      [
        "inconsistencia_portico_columna",
        "seccion_columna_portico_pendiente",
      ].includes(item?.categoria)
  ).length;
  const reinforcementOptions = useMemo(
    () =>
      (results?.armaduras_vigas_riostra || []).filter(
        (item) => item?.estado === "CORRECTO"
      ),
    [results]
  );
  const foundationId = alertEvidenceValue(
    alert,
    "Fundación"
  );
  const relationshipRows = [
    ...(results?.relaciones_columnas_fundaciones || []),
    ...(results?.columnas_pendientes_clasificacion || []),
    ...(results?.columnas_vinculadas_por_viga || []),
    ...(results?.columnas_fundaciones || []),
  ];
  const relationship = relationshipRows.find((item) => {
    const reference =
      item?.referencia_columna_vinculada ||
      item?.referencia_columna;
    const referenceMatches =
      !alert?.referencia ||
      String(reference) === String(alert.referencia);
    const foundationMatches =
      !foundationId ||
      String(item?.fundacion_id) === String(foundationId);

    return referenceMatches && foundationMatches;
  });
  const porticoConflict = (
    results?.columnas_porticos_segmentos || []
  ).find(
    (item) =>
      String(item?.tramo_id || "") ===
        String(alert?.elemento_id || "") ||
      (kind === "portico_column_section" &&
        String(item?.referencia || "") ===
          String(alert?.referencia || alert?.elemento_id || ""))
  );
  const porticoCandidateReferences = [
    ...new Set(
      [
        ...(porticoConflict?.referencias_candidatas || []),
        porticoConflict?.referencia,
      ].filter(Boolean)
    ),
  ];
  const porticoCandidateHeights = [
    ...new Set(
      [
        ...(porticoConflict?.alturas_candidatas_m || []),
        porticoConflict?.altura_detectada_m,
      ].filter((value) => value !== null && value !== undefined)
    ),
  ];
  const porticoSections = useMemo(
    () =>
      new Map(
        (results?.secciones_columnas || [])
          .filter(
            (item) =>
              item?.estado === "CORRECTO" && item?.referencia
          )
          .map((item) => [
            String(item.referencia).trim().toUpperCase(),
            item,
          ])
      ),
    [results]
  );
  const initialPorticoReference =
    porticoConflict?.referencia ||
    alert?.referencia ||
    porticoCandidateReferences[0] ||
    "";
  const initialPorticoSection = porticoSections.get(
    String(initialPorticoReference).toUpperCase()
  );

  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [sourceError, setSourceError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [width, setWidth] = useState(
    segment?.ancho_m ?? ""
  );
  const [height, setHeight] = useState(
    segment?.alto_m ?? ""
  );
  const [axisLength, setAxisLength] = useState(
    segment?.longitud_entre_ejes_m ??
      segment?.longitud_m ??
      ""
  );
  const [clearLength, setClearLength] = useState(
    segment?.longitud_libre_entre_caras_m ?? ""
  );
  const [reinforcementReference, setReinforcementReference] =
    useState(
      segment?.referencia ||
        reinforcementOptions[0]?.referencia ||
        ""
    );
  const [heights, setHeights] = useState(() =>
    Object.fromEntries(
      heightItems.map((item) => [
        item.id,
        item.proposedHeight ?? "",
      ])
    )
  );
  const [additionalColumnLength, setAdditionalColumnLength] =
    useState("0");
  const [relationshipDecision, setRelationshipDecision] =
    useState("confirmar");
  const [columnReference, setColumnReference] = useState(
    relationship?.referencia_columna_vinculada ||
      relationship?.referencia_columna ||
      alert?.referencia ||
      ""
  );
  const [columnWidth, setColumnWidth] = useState(
    relationship?.ancho_m ?? ""
  );
  const [columnDepth, setColumnDepth] = useState(
    relationship?.largo_m ?? ""
  );
  const [supportType, setSupportType] = useState(
    relationship?.referencia_columna_vinculada ||
      relationship?.tipo_asociacion ===
        "adicional_por_proximidad"
      ? "vinculada_por_viga"
      : "apoyo_directo"
  );
  const [porticoReference, setPorticoReference] = useState(
    initialPorticoReference
  );
  const [porticoHeight, setPorticoHeight] = useState(
    porticoConflict?.altura_detectada_m ??
      porticoCandidateHeights[0] ??
      ""
  );
  const [porticoWidth, setPorticoWidth] = useState(
    initialPorticoSection?.dimension_1_m ?? ""
  );
  const [porticoDepth, setPorticoDepth] = useState(
    initialPorticoSection?.dimension_2_m ?? ""
  );

  async function openPorticoSource(pageNumber) {
    setSourceError("");
    const popup = window.open("about:blank", "_blank");

    try {
      const documents =
        results?.enrutamiento_documentos?.documentos || [];
      const document = documents.find((item) =>
        (item?.paginas || []).some(
          (page) => Number(page?.pagina) === Number(pageNumber)
        )
      );

      if (!document?.sha256) {
        throw new Error(
          `No se encontró el documento asociado a la página ${pageNumber}.`
        );
      }

      const storedPdf = await getPdf(document.sha256);
      if (!storedPdf) {
        throw new Error(
          `El PDF original ${document.nombre || "del proyecto"} no está disponible en este navegador. Volvé a cargarlo para abrir su evidencia.`
        );
      }

      const url = URL.createObjectURL(storedPdf);
      if (!popup) {
        URL.revokeObjectURL(url);
        throw new Error(
          "El navegador bloqueó la nueva pestaña. Habilitá las ventanas emergentes para abrir el plano."
        );
      }
      popup.location.href = `${url}#page=${pageNumber}`;
      setTimeout(() => URL.revokeObjectURL(url), 300000);
    } catch (openError) {
      popup?.close();
      setSourceError(
        openError.message || "No se pudo abrir la página del plano."
      );
    }
  }

  const commonIsValid =
    reviewer.trim().length >= 2 &&
    reason.trim().length >= 10;
  const positive = (value) =>
    (parseLocalizedNumber(value) ?? 0) > 0;
  const nonNegative = (value) =>
    (parseLocalizedNumber(value) ?? -1) >= 0;
  const specificIsValid = (() => {
    if (kind === "beam_geometry") {
      return (
        positive(width) &&
        positive(height) &&
        positive(axisLength) &&
        positive(clearLength)
      );
    }

    if (kind === "beam_reinforcement") {
      return Boolean(reinforcementReference) && confirmed;
    }

    if (kind === "column_reinforcement") {
      return (
        columnHeightsReady &&
        columnReinforcementReferences.length > 0 &&
        incompleteColumnReinforcements.length === 0 &&
        nonNegative(additionalColumnLength) &&
        confirmed
      );
    }

    if (kind === "portico_column_conflict") {
      return (
        Boolean(porticoReference.trim()) &&
        positive(porticoHeight) &&
        positive(porticoWidth) &&
        positive(porticoDepth) &&
        confirmed
      );
    }

    if (kind === "portico_column_section") {
      return (
        Boolean(porticoReference.trim()) &&
        positive(porticoWidth) &&
        positive(porticoDepth) &&
        confirmed
      );
    }

    if (
      kind === "column_heights" ||
      kind === "pedestal_heights"
    ) {
      return (
        (kind !== "column_heights" || pendingPorticoConflicts === 0) &&
        heightItems.length > 0 &&
        heightItems.every((item) =>
          positive(heights[item.id])
        )
      );
    }

    if (kind === "column_relationship") {
      return relationshipDecision === "descartar"
        ? confirmed
        : Boolean(columnReference.trim()) &&
            positive(columnWidth) &&
            positive(columnDepth) &&
            confirmed;
    }

    return confirmed;
  })();
  const formIsValid = commonIsValid && specificIsValid;
  const validationIssues = [];

  if (reviewer.trim().length < 2) {
    validationIssues.push(
      "Indicá el nombre del profesional revisor."
    );
  }

  if (reason.trim().length < 10) {
    validationIssues.push(
      "Explicá el motivo y el documento verificado (mínimo 10 caracteres)."
    );
  }

  if (
    kind === "column_heights" ||
    kind === "pedestal_heights"
  ) {
    const missingHeights = heightItems.filter(
      (item) => !positive(heights[item.id])
    );

    if (heightItems.length === 0) {
      validationIssues.push(
        "No se encontraron referencias asociadas a esta alerta."
      );
    } else if (missingHeights.length > 0) {
      validationIssues.push(
        `Completá una altura mayor que cero para ${missingHeights.length} tramo(s).`
      );
    }
    if (kind === "column_heights" && pendingPorticoConflicts > 0) {
      validationIssues.push(
        `Completá primero ${pendingPorticoConflicts} revisión(es) de pórticos y secciones.`
      );
    }
  }

  if (kind === "beam_geometry") {
    if (
      !positive(width) ||
      !positive(height) ||
      !positive(axisLength) ||
      !positive(clearLength)
    ) {
      validationIssues.push(
        "Completá todas las dimensiones con valores mayores que cero."
      );
    }
  }

  if (kind === "beam_reinforcement") {
    if (!reinforcementReference) {
      validationIssues.push(
        "Seleccioná el detalle de armadura correspondiente."
      );
    }

    if (!confirmed) {
      validationIssues.push(
        "Confirmá que revisaste la armadura seleccionada."
      );
    }
  }

  if (kind === "column_reinforcement") {
    if (!columnHeightsReady) {
      validationIssues.push(
        "Primero validá la alerta de alturas reales de columnas."
      );
    }

    if (columnReinforcementReferences.length === 0) {
      validationIssues.push(
        "No se encontraron columnas asociadas para confirmar."
      );
    }

    if (incompleteColumnReinforcements.length > 0) {
      validationIssues.push(
        `Falta una armadura completa para: ${incompleteColumnReinforcements.join(
          ", "
        )}.`
      );
    }

    if (!nonNegative(additionalColumnLength)) {
      validationIssues.push(
        "La longitud adicional por extremo debe ser cero o un valor positivo."
      );
    }

    if (!confirmed) {
      validationIssues.push(
        "Confirmá las armaduras y el criterio de longitud antes de calcular."
      );
    }
  }

  if (kind === "portico_column_conflict") {
    if (
      !porticoReference.trim() ||
      !positive(porticoHeight) ||
      !positive(porticoWidth) ||
      !positive(porticoDepth)
    ) {
      validationIssues.push(
        "Indicá la referencia, la altura y la sección verificadas del tramo."
      );
    }
    if (!confirmed) {
      validationIssues.push(
        "Confirmá que comparaste las vistas del pórtico."
      );
    }
  }
  if (kind === "portico_column_section") {
    if (
      !porticoReference.trim() ||
      !positive(porticoWidth) ||
      !positive(porticoDepth)
    ) {
      validationIssues.push(
        "Indicá el ancho y el largo verificados de la sección."
      );
    }
    if (!confirmed) {
      validationIssues.push(
        "Confirmá que revisaste el detalle de la sección."
      );
    }
  }

  if (kind === "column_relationship") {
    if (
      relationshipDecision !== "descartar" &&
      (!columnReference.trim() ||
        !positive(columnWidth) ||
        !positive(columnDepth))
    ) {
      validationIssues.push(
        "Completá la referencia y las dos dimensiones de la columna."
      );
    }

    if (!confirmed) {
      validationIssues.push(
        "Confirmá la decisión sobre la asociación estructural."
      );
    }
  }

  if (
    ["documented_confirmation", "observation"].includes(
      kind
    ) &&
    !confirmed
  ) {
    validationIssues.push(
      "Confirmá que revisaste la evidencia documental."
    );
  }

  const handleSubmit = (event) => {
    event.preventDefault();

    setAttempted(true);

    if (!formIsValid || saving) {
      return;
    }

    let accion = alert.excluido_del_computo
      ? "registrar_observacion"
      : "confirmar_revision";
    let valores = {};
    let confirmaciones = {};

    if (kind === "beam_geometry") {
      accion = "validar_geometria";
      valores = {
        ancho_m: parseLocalizedNumber(width),
        alto_m: parseLocalizedNumber(height),
        longitud_m: parseLocalizedNumber(axisLength),
        longitud_entre_ejes_m:
          parseLocalizedNumber(axisLength),
        longitud_libre_m:
          parseLocalizedNumber(clearLength),
      };
    } else if (kind === "beam_reinforcement") {
      accion = "asignar_armadura";
      valores = {
        referencia_armadura: reinforcementReference,
      };
      confirmaciones = {
        confirmar_armadura: confirmed,
      };
    } else if (kind === "column_reinforcement") {
      accion = "asignar_armadura";
      valores = {
        referencias_confirmadas:
          columnReinforcementReferences,
        longitud_adicional_por_extremo_m:
          parseLocalizedNumber(additionalColumnLength),
      };
      confirmaciones = {
        confirmar_armaduras: confirmed,
      };
    } else if (kind === "portico_column_conflict") {
      accion = "resolver_inconsistencia_portico";
      valores = {
        referencia_columna: porticoReference.trim().toUpperCase(),
        altura_m: parseLocalizedNumber(porticoHeight),
        ancho_m: parseLocalizedNumber(porticoWidth),
        largo_m: parseLocalizedNumber(porticoDepth),
      };
      confirmaciones = {
        confirmar_conflicto_portico: confirmed,
      };
    } else if (kind === "portico_column_section") {
      accion = "validar_seccion_portico";
      valores = {
        referencia_columna: porticoReference.trim().toUpperCase(),
        ancho_m: parseLocalizedNumber(porticoWidth),
        largo_m: parseLocalizedNumber(porticoDepth),
      };
      confirmaciones = {
        confirmar_seccion_portico: confirmed,
      };
    } else if (
      kind === "column_heights" ||
      kind === "pedestal_heights"
    ) {
      accion = "validar_alturas";
      valores = heightSegments.length
        ? {
            alturas_por_tramo: Object.fromEntries(
              heightItems.map((item) => [
                item.id,
                parseLocalizedNumber(heights[item.id]),
              ])
            ),
          }
        : {
            alturas_por_referencia: Object.fromEntries(
              Object.entries(heights).map(
                ([reference, value]) => [
                  reference,
                  parseLocalizedNumber(value),
                ]
              )
            ),
          };
    } else if (kind === "column_relationship") {
      accion =
        relationshipDecision === "descartar"
          ? "descartar_asociacion"
          : "confirmar_asociacion";
      valores = {
        fundacion_id: foundationId || null,
        referencia_columna: columnReference.trim(),
        ancho_m: parseLocalizedNumber(columnWidth),
        largo_m: parseLocalizedNumber(columnDepth),
        tipo_apoyo: supportType,
      };
    }

    onConfirm({
      alerta_id: alert.id,
      accion,
      motivo: reason.trim(),
      revisor: reviewer.trim(),
      valores,
      confirmaciones,
    });
  };

  const titleByKind = {
    beam_geometry: "Validar geometría del tramo",
    beam_reinforcement: "Asignar detalle de armadura",
    column_heights: "Validar alturas de columnas",
    column_reinforcement: "Confirmar armaduras de columnas",
    portico_column_conflict: "Resolver inconsistencia entre pórticos",
    portico_column_section: "Validar sección de columna",
    pedestal_heights: "Validar alturas de pedestales",
    column_relationship: "Revisar asociación estructural",
    documented_confirmation: "Confirmar revisión documental",
    observation: "Registrar seguimiento técnico",
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) {
          onClose();
        }
      }}
    >
      <section
        aria-modal="true"
        className="max-h-[92vh] w-full max-w-3xl overflow-auto rounded-3xl border border-slate-200 bg-white shadow-2xl"
        role="dialog"
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-100 bg-white/95 px-5 py-4 backdrop-blur sm:px-7">
          <div>
            <p className="text-[9px] font-extrabold uppercase tracking-[0.18em] text-amber-600">
              Decisión profesional auditable
            </p>
            <h2 className="mt-1 font-display text-xl font-bold text-ink">
              {titleByKind[kind] || "Revisar inconsistencia"}
            </h2>
            <p className="mt-1 text-[11px] leading-5 text-slate-500">
              {alert.titulo}
            </p>
          </div>

          <button
            aria-label="Cerrar revisión"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-lg text-slate-400 transition hover:bg-slate-50 hover:text-ink disabled:opacity-50"
            disabled={saving}
            type="button"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <form
          className="space-y-6 p-5 sm:p-7"
          onSubmit={handleSubmit}
        >
          {kind === "beam_geometry" && (
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                ["Ancho (m)", width, setWidth],
                ["Alto (m)", height, setHeight],
                ["Longitud entre ejes (m)", axisLength, setAxisLength],
                ["Longitud libre (m)", clearLength, setClearLength],
              ].map(([label, value, setter]) => (
                <label
                  className="text-[10px] font-bold text-slate-600"
                  key={label}
                >
                  {label}
                  <input
                    className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent"
                    min="0.01"
                    required
                    step="0.001"
                    type="number"
                    value={value}
                    onChange={(event) => setter(event.target.value)}
                  />
                </label>
              ))}
            </div>
          )}

          {kind === "beam_reinforcement" && (
            <div className="space-y-3">
              <label className="text-[10px] font-bold text-slate-600">
                Detalle de armadura validado
                <select
                  className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs outline-none focus:border-accent"
                  required
                  value={reinforcementReference}
                  onChange={(event) =>
                    setReinforcementReference(event.target.value)
                  }
                >
                  <option value="">Seleccionar detalle…</option>
                  {reinforcementOptions.map((item, index) => (
                    <option
                      key={`${item.referencia}-${index}`}
                      value={item.referencia}
                    >
                      {item.referencia} · {formatSection(
                        item.ancho_m,
                        item.alto_m
                      )}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {kind === "column_reinforcement" && (
            <div className="space-y-4">
              <div
                className={`rounded-2xl border p-4 text-[10px] leading-5 ${
                  columnHeightsReady
                    ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                    : "border-amber-200 bg-amber-50 text-amber-900"
                }`}
              >
                {columnHeightsReady
                  ? "Las alturas reales ya están validadas. Al confirmar estas armaduras se calculará el peso de acero de las columnas."
                  : "Primero resolvé la alerta de alturas reales. El acero necesita esas longitudes para calcular barras y cantidad de estribos."}
              </div>

              <div>
                <h3 className="text-xs font-extrabold text-ink">
                  Armadura detectada por referencia
                </h3>
                <p className="mt-1 text-[10px] leading-5 text-slate-500">
                  Solo se aceptan candidatos completos: barras
                  longitudinales, diámetro y separación de estribos,
                  y longitud indicada del estribo.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {columnReinforcementReferences.map(
                  (reference) => {
                    const candidate =
                      columnReinforcements.get(reference);
                    const isIncomplete =
                      incompleteColumnReinforcements.includes(
                        reference
                      );
                    const longitudinal = (
                      candidate?.grupos_longitudinales || []
                    )
                      .map(
                        (group) =>
                          `${group.cantidad} Ø ${group.diametro_pulgadas}"`
                      )
                      .join(" + ");
                    const stirrup = candidate?.estribo;

                    return (
                      <article
                        className={`rounded-xl border p-3 ${
                          isIncomplete
                            ? "border-red-200 bg-red-50"
                            : "border-emerald-200 bg-emerald-50/60"
                        }`}
                        key={reference}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <strong className="text-xs text-ink">
                            {reference}
                          </strong>
                          <span
                            className={`rounded-full border px-2 py-1 text-[8px] font-extrabold uppercase tracking-wider ${
                              isIncomplete
                                ? "border-red-200 bg-white text-red-700"
                                : "border-emerald-200 bg-white text-emerald-700"
                            }`}
                          >
                            {isIncomplete
                              ? "Incompleta"
                              : "Lista"}
                          </span>
                        </div>
                        <p className="mt-2 text-[10px] font-semibold text-slate-700">
                          {longitudinal ||
                            "Sin barras longitudinales"}
                        </p>
                        <p className="mt-1 text-[9px] leading-4 text-slate-500">
                          {stirrup
                            ? `Estribo Ø ${stirrup.diametro_pulgadas || "—"}" c/${formatNumber(
                                stirrup.separacion_m,
                                "m"
                              )} · L ${formatNumber(
                                stirrup.longitud_indicada_m,
                                "m"
                              )}`
                            : "Sin estribo detectado"}
                        </p>
                        <p className="mt-1 text-[8px] text-slate-400">
                          {candidate?.origen ||
                            "Fuente no disponible"}
                          {candidate?.pagina
                            ? ` · página ${candidate.pagina}`
                            : ""}
                        </p>
                      </article>
                    );
                  }
                )}
              </div>

              <label className="block text-[10px] font-bold text-slate-600">
                Longitud adicional por extremo de cada barra (m)
                <input
                  className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent sm:max-w-xs"
                  inputMode="decimal"
                  placeholder="Ej. 0,00"
                  type="text"
                  value={additionalColumnLength}
                  onChange={(event) =>
                    setAdditionalColumnLength(
                      event.target.value
                    )
                  }
                />
                <span className="mt-1 block font-normal leading-4 text-slate-400">
                  Usá 0 si el detalle no exige prolongación. El
                  criterio queda registrado en la revisión.
                </span>
              </label>
            </div>
          )}

          {(kind === "column_heights" ||
            kind === "pedestal_heights") && (
            <div>
              <h3 className="text-xs font-extrabold text-ink">
                {heightSegments.length
                  ? "Altura real por tramo de pórtico"
                  : "Altura real por referencia"}
              </h3>
              <p className="mt-1 text-[10px] leading-5 text-slate-500">
                {heightSegments.length
                  ? "Las cotas detectadas están precargadas. Revisá cada eje y nivel antes de confirmar; las vistas ortogonales ya fueron deduplicadas."
                  : "Todas las referencias deben completarse para reemplazar el estado pendiente o preliminar."}
              </p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {heightItems.map((item) => (
                  <label
                    className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-[10px] font-bold text-slate-600"
                    key={item.id}
                  >
                    {item.label} · altura (m)
                    {item.pages.length > 0 && (
                      <span className="mt-1 block font-normal text-slate-400">
                        Página(s) {item.pages.join(", ")}
                      </span>
                    )}
                    <input
                      className="mt-2 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs outline-none focus:border-accent"
                      inputMode="decimal"
                      placeholder="Ej. 3,20"
                      type="text"
                      value={heights[item.id] || ""}
                      onChange={(event) =>
                        setHeights((current) => ({
                          ...current,
                          [item.id]: event.target.value,
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          )}

          {(kind === "portico_column_conflict" ||
            kind === "portico_column_section") && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-[10px] leading-5 text-amber-950">
                <strong className="block text-xs">
                  {kind === "portico_column_section"
                    ? porticoReference || "Columna"
                    : `${porticoConflict?.eje_global || "Tramo"} · ${
                        porticoConflict?.nivel_inferior || "nivel inferior"
                      }–${
                        porticoConflict?.nivel_superior || "nivel superior"
                      }`}
                </strong>
                {kind === "portico_column_section"
                  ? "La geometría y la altura del tramo ya fueron leídas. Confirmá la sección que corresponde a esta referencia."
                  : "Las vistas indican datos distintos. Elegí los valores que corresponden al plano estructural vigente; la decisión quedará vinculada a este tramo."}
              </div>

              {kind === "portico_column_conflict" &&
                Array.isArray(porticoConflict?.evidencias) &&
                porticoConflict.evidencias.length > 0 && (
                  <div>
                    <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">
                      Comparación de las vistas que originaron el conflicto
                    </p>
                    <div className="mt-2 grid gap-3 sm:grid-cols-2">
                      {porticoConflict.evidencias.map((evidence) => (
                        <article
                          className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-[10px] text-slate-600"
                          key={evidence.observacion_id}
                        >
                          <strong className="block text-xs text-ink">
                            Página {evidence.pagina_origen} · Pórtico {evidence.portico}
                          </strong>
                          <dl className="mt-2 space-y-1">
                            <div className="flex justify-between gap-3">
                              <dt>Eje local</dt>
                              <dd className="font-bold">{evidence.eje_local || "—"}</dd>
                            </div>
                            <div className="flex justify-between gap-3">
                              <dt>Columna indicada</dt>
                              <dd className="font-bold text-amber-700">{evidence.referencia || "—"}</dd>
                            </div>
                            <div className="flex justify-between gap-3">
                              <dt>Tramo</dt>
                              <dd className="font-bold">
                                {evidence.nivel_inferior || "—"}–{evidence.nivel_superior || "—"}
                              </dd>
                            </div>
                            <div className="flex justify-between gap-3">
                              <dt>Altura leída</dt>
                              <dd className="font-bold">{formatNumber(evidence.altura_detectada_m, "m")}</dd>
                            </div>
                          </dl>
                          <button
                            className="mt-3 w-full rounded-lg border border-blue-200 bg-white px-3 py-2 font-extrabold text-blue-700 transition hover:bg-blue-50"
                            type="button"
                            onClick={() => openPorticoSource(evidence.pagina_origen)}
                          >
                            Abrir página {evidence.pagina_origen} del plano
                          </button>
                        </article>
                      ))}
                    </div>
                    {sourceError && (
                      <p className="mt-2 rounded-lg border border-red-200 bg-red-50 p-3 text-[10px] text-red-700">
                        {sourceError}
                      </p>
                    )}
                  </div>
                )}

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-[10px] font-bold text-slate-600">
                  Referencia verificada
                  <input
                    className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs uppercase outline-none focus:border-accent"
                    list={`portico-references-${alert.id}`}
                    value={porticoReference}
                    onChange={(event) => {
                      const value = event.target.value.toUpperCase();
                      const section = porticoSections.get(value);
                      setPorticoReference(value);
                      if (section) {
                        setPorticoWidth(section.dimension_1_m ?? "");
                        setPorticoDepth(section.dimension_2_m ?? "");
                      }
                    }}
                  />
                  <datalist id={`portico-references-${alert.id}`}>
                    {porticoCandidateReferences.map((reference) => (
                      <option key={reference} value={reference} />
                    ))}
                  </datalist>
                  <span className="mt-1 block font-normal text-slate-400">
                    Candidatas: {porticoCandidateReferences.join(", ") || "sin propuesta"}
                  </span>
                </label>

                {kind === "portico_column_conflict" && (
                  <label className="text-[10px] font-bold text-slate-600">
                    Altura verificada (m)
                    <input
                      className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent"
                      inputMode="decimal"
                      value={porticoHeight}
                      onChange={(event) => setPorticoHeight(event.target.value)}
                    />
                    <span className="mt-1 block font-normal text-slate-400">
                      Candidatas: {porticoCandidateHeights.join(", ") || "sin propuesta"}
                    </span>
                  </label>
                )}

                <label className="text-[10px] font-bold text-slate-600">
                  Ancho de sección (m)
                  <input
                    className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent"
                    inputMode="decimal"
                    value={porticoWidth}
                    onChange={(event) => setPorticoWidth(event.target.value)}
                  />
                </label>

                <label className="text-[10px] font-bold text-slate-600">
                  Largo de sección (m)
                  <input
                    className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent"
                    inputMode="decimal"
                    value={porticoDepth}
                    onChange={(event) => setPorticoDepth(event.target.value)}
                  />
                </label>
              </div>
            </div>
          )}

          {kind === "column_relationship" && (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="rounded-xl border border-slate-200 p-3 text-[10px] font-bold text-slate-600">
                  <input
                    checked={relationshipDecision === "confirmar"}
                    className="mr-2 accent-teal-600"
                    name="relationship-decision"
                    type="radio"
                    onChange={() =>
                      setRelationshipDecision("confirmar")
                    }
                  />
                  Confirmar o corregir asociación
                </label>
                <label className="rounded-xl border border-slate-200 p-3 text-[10px] font-bold text-slate-600">
                  <input
                    checked={relationshipDecision === "descartar"}
                    className="mr-2 accent-red-600"
                    name="relationship-decision"
                    type="radio"
                    onChange={() =>
                      setRelationshipDecision("descartar")
                    }
                  />
                  Descartar candidata incorrecta
                </label>
              </div>

              {relationshipDecision === "confirmar" && (
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="text-[10px] font-bold text-slate-600">
                    Referencia de columna
                    <input
                      className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs uppercase outline-none focus:border-accent"
                      required
                      value={columnReference}
                      onChange={(event) =>
                        setColumnReference(event.target.value)
                      }
                    />
                  </label>
                  <label className="text-[10px] font-bold text-slate-600">
                    Tipo de apoyo
                    <select
                      className="mt-2 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs outline-none focus:border-accent"
                      value={supportType}
                      onChange={(event) =>
                        setSupportType(event.target.value)
                      }
                    >
                      <option value="apoyo_directo">Apoyo directo</option>
                      <option value="vinculada_por_viga">
                        Vinculada por viga
                      </option>
                    </select>
                  </label>
                  <label className="text-[10px] font-bold text-slate-600">
                    Ancho (m)
                    <input
                      className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent"
                      min="0.01"
                      required
                      step="0.01"
                      type="number"
                      value={columnWidth}
                      onChange={(event) =>
                        setColumnWidth(event.target.value)
                      }
                    />
                  </label>
                  <label className="text-[10px] font-bold text-slate-600">
                    Largo (m)
                    <input
                      className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent"
                      min="0.01"
                      required
                      step="0.01"
                      type="number"
                      value={columnDepth}
                      onChange={(event) =>
                        setColumnDepth(event.target.value)
                      }
                    />
                  </label>
                </div>
              )}
            </div>
          )}

          {(kind === "observation" ||
            kind === "documented_confirmation") && (
            <div
              className={`rounded-2xl border p-4 text-[10px] leading-5 ${
                kind === "observation"
                  ? "border-amber-200 bg-amber-50 text-amber-900"
                  : "border-sky-200 bg-sky-50 text-sky-900"
              }`}
            >
              {kind === "observation"
                ? "Esta inconsistencia mantiene cantidades fuera del cómputo. La nota quedará auditada, pero la alerta seguirá abierta hasta completar los datos técnicos."
                : "La confirmación cerrará esta advertencia documental y conservará la identidad, fecha y motivo de la decisión."}
            </div>
          )}

          <div>
            <h3 className="text-xs font-extrabold text-ink">
              Responsable y fundamento
            </h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-[10px] font-bold text-slate-600">
                Profesional revisor
                <input
                  className="mt-2 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-accent"
                  placeholder="Nombre y matrícula, si corresponde"
                  required
                  value={reviewer}
                  onChange={(event) => setReviewer(event.target.value)}
                />
              </label>
              <label className="text-[10px] font-bold text-slate-600 sm:row-span-2">
                Motivo y documento verificado
                <textarea
                  className="mt-2 min-h-24 w-full resize-y rounded-xl border border-slate-200 p-3 text-xs outline-none focus:border-accent"
                  minLength={10}
                  required
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
              </label>
            </div>
          </div>

          {kind !== "beam_geometry" &&
            kind !== "column_heights" &&
            kind !== "pedestal_heights" && (
              <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <input
                  checked={confirmed}
                  className="mt-0.5 accent-amber-600"
                  type="checkbox"
                  onChange={(event) =>
                    setConfirmed(event.target.checked)
                  }
                />
                <span className="text-[10px] leading-5 text-amber-900">
                  {kind === "column_reinforcement"
                    ? "Confirmo que revisé las barras longitudinales, los estribos y el criterio de longitud utilizado para calcular el acero de columnas."
                    : kind === "portico_column_conflict"
                      ? "Confirmo que comparé las vistas del pórtico y que la referencia, altura y sección indicadas corresponden a este eje y nivel."
                      : kind === "portico_column_section"
                        ? "Confirmo que la sección indicada fue revisada contra el detalle estructural correspondiente."
                    : "Confirmo que revisé la evidencia y que la decisión registrada corresponde a la documentación estructural."}
                </span>
              </label>
            )}

          {attempted && validationIssues.length > 0 && (
            <div
              className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3"
              role="alert"
            >
              <strong className="text-[10px] font-extrabold text-amber-950">
                Falta completar lo siguiente:
              </strong>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-[10px] leading-5 text-amber-900">
                {validationIssues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <div
              className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[11px] font-semibold text-red-700"
              role="alert"
            >
              {error}
            </div>
          )}

          <div className="flex flex-col-reverse gap-2 border-t border-slate-100 pt-5 sm:flex-row sm:justify-end">
            <button
              className="min-h-11 rounded-xl border border-slate-200 px-5 text-xs font-bold text-slate-600 disabled:opacity-50"
              disabled={saving}
              type="button"
              onClick={onClose}
            >
              Cancelar
            </button>
            <button
              className="min-h-11 rounded-xl bg-accent px-5 text-xs font-extrabold text-white disabled:cursor-not-allowed disabled:opacity-50"
              disabled={saving}
              type="submit"
            >
              {saving
                ? "Aplicando revisión…"
                : attempted && !formIsValid
                  ? "Revisar datos faltantes"
                : kind === "observation"
                  ? "Registrar seguimiento"
                  : "Validar y actualizar"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function EngineeringReviewDialog(props) {
  const kind = reviewKindForAlert(props.alert);

  if (kind === "beam_section") {
    return (
      <SectionReviewDialog
        {...props}
        onConfirm={(payload) =>
          props.onConfirm({
            alerta_id: payload.alerta_id,
            accion: "validar_seccion",
            motivo: payload.motivo,
            revisor: payload.revisor,
            valores: {
              fuente_seleccionada:
                payload.fuente_seleccionada,
              ancho_m: payload.ancho_m,
              alto_m: payload.alto_m,
            },
            confirmaciones: {
              confirmar_armadura_detalle:
                payload.confirmar_armadura_detalle,
            },
          })
        }
      />
    );
  }

  return <GeneralEngineeringReviewForm {...props} />;
}

function EngineeringReviews({ items = [] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-5">
      <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
        <div>
          <p className="text-[9px] font-extrabold uppercase tracking-[0.18em] text-emerald-700">
            Trazabilidad profesional
          </p>
          <h3 className="mt-1 font-display text-base font-bold text-emerald-950">
            Historial de revisiones
          </h3>
        </div>

        <span className="w-fit rounded-full border border-emerald-200 bg-white px-3 py-1.5 text-[9px] font-extrabold text-emerald-700">
          {items.length} {items.length === 1 ? "decisión" : "decisiones"}
        </span>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {items.map((item) => {
          const isOpen =
            item.estado === "observacion_registrada" ||
            item.resuelve_alerta === false;
          const title =
            item.tramo_id ||
            item.elemento_id ||
            item.referencia ||
            item.familia ||
            "Revisión";

          return (
          <article
            key={item.revision_id}
            className={`rounded-xl border bg-white p-4 ${
              isOpen
                ? "border-amber-200"
                : "border-emerald-200/80"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <strong className="block text-xs text-ink">
                  {title}
                </strong>
                <span className="mt-1 block text-[9px] text-slate-400">
                  {formatDate(item.fecha_revision)} · {item.familia || "general"}
                </span>
              </div>

              <span
                className={`rounded-full border px-2.5 py-1 text-[8px] font-extrabold uppercase tracking-wider ${
                  isOpen
                    ? "border-amber-200 bg-amber-50 text-amber-700"
                    : "border-emerald-200 bg-emerald-50 text-emerald-700"
                }`}
              >
                {isOpen ? "Seguimiento abierto" : "Validado"}
              </span>
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-2 text-[10px]">
              {item.seccion_validada_m && (
                <div>
                  <dt className="text-slate-400">Sección aplicada</dt>
                  <dd className="mt-0.5 font-bold text-ink">
                    {formatSection(
                      item.seccion_validada_m?.ancho,
                      item.seccion_validada_m?.alto
                    )}
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-slate-400">Decisión</dt>
                <dd className="mt-0.5 font-bold capitalize text-ink">
                  {String(
                    item.accion ||
                      item.tipo_revision ||
                      item.fuente_seleccionada ||
                      "—"
                  ).replaceAll("_", " ")}
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="text-slate-400">Revisor</dt>
                <dd className="mt-0.5 font-bold text-ink">
                  {item.revisor || "—"}
                </dd>
              </div>
            </dl>

            <p className="mt-3 border-t border-slate-100 pt-3 text-[10px] leading-5 text-slate-500">
              {item.motivo}
            </p>
          </article>
          );
        })}
      </div>
    </section>
  );
}

function ValidationPanel({ metrics = [], warnings = [] }) {
  return (
    <div className="p-5 sm:p-7">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <BeamMetric
            key={metric.label}
            label={metric.label}
            value={metric.value}
            detail={metric.detail}
          />
        ))}
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <h3 className="font-display text-base font-bold text-ink">
          Observaciones del procesamiento
        </h3>

        {warnings.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {warnings.map((warning, index) => (
              <li
                key={`${warning}-${index}`}
                className="flex gap-2 text-[11px] leading-5 text-slate-500"
              >
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-[11px] text-slate-400">
            No se informaron advertencias para esta familia.
          </p>
        )}
      </div>
    </div>
  );
}

function BeamConfidence({ value }) {
  const normalized = String(
    value || "sin_dato"
  ).toLowerCase();

  const styles =
    normalized === "alta"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : normalized === "media"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-slate-200 bg-slate-50 text-slate-500";

  return (
    <span
      className={`inline-flex rounded-full border px-2 py-1 text-[9px] font-extrabold uppercase tracking-wider ${styles}`}
    >
      {normalized.replaceAll("_", " ")}
    </span>
  );
}

function VigasRiostraDetail({
  items = [],
  summary = [],
  steelSummary = [],
  validation = {},
  steelValidation = {},
  totals = {},
  view = "tramos",
}) {
  const [referenceFilter, setReferenceFilter] =
    useState("todas");

  const [search, setSearch] = useState("");

  const references = useMemo(
    () =>
      [...new Set(
        items
          .map((item) => item.referencia)
          .filter(Boolean)
      )].sort((first, second) =>
        String(first).localeCompare(
          String(second),
          "es",
          {
            numeric: true,
          }
        )
      ),
    [items]
  );

  const filteredItems = useMemo(() => {
    const normalizedSearch = search
      .trim()
      .toLowerCase();

    return items.filter((item) => {
      const matchesReference =
        referenceFilter === "todas" ||
        item.referencia === referenceFilter;

      if (!matchesReference) {
        return false;
      }

      if (!normalizedSearch) {
        return true;
      }

      const searchableText = [
        item.tramo_id,
        item.referencia,
        item.apoyo_inicial_id,
        item.referencia_apoyo_inicial,
        item.apoyo_final_id,
        item.referencia_apoyo_final,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return searchableText.includes(
        normalizedSearch
      );
    });
  }, [items, referenceFilter, search]);

  if (!items.length) {
    return (
      <div className="p-8 text-center sm:p-12">
        <h3 className="font-display text-lg font-bold text-ink">
          No hay vigas de riostra computadas
        </h3>

        <p className="mx-auto mt-2 max-w-xl text-xs leading-5 text-slate-500">
          El análisis actual no devolvió el campo
          vigas_riostra_computo_detalle. Volvé a procesar los
          planos con la versión actualizada del backend.
        </p>
      </div>
    );
  }

  if (view === "validaciones") {
    return (
      <ValidationPanel
        metrics={[
          {
            label: "Cobertura de tramos",
            value: formatNumber(
              validation.cobertura_tramos_porcentaje,
              "%"
            ),
            detail: "tramos vinculados con rótulos",
          },
          {
            label: "Confianza alta",
            value: formatNumber(
              validation.tramos_confianza_geometrica_alta
            ),
            detail: "tramos confirmados geométricamente",
          },
          {
            label: "Confianza media",
            value: formatNumber(
              validation.tramos_confianza_geometrica_media
            ),
            detail: "tramos que conviene revisar",
          },
          {
            label: "Pendientes",
            value: formatNumber(
              validation.tramos_pendientes_revision
            ),
            detail: "tramos todavía no confirmados",
          },
          {
            label: "Acero computado",
            value: formatNumber(
              steelValidation.tramos_acero_computado
            ),
            detail: "tramos incluidos en el subtotal",
          },
          {
            label: "Acero pendiente",
            value: formatNumber(
              steelValidation.tramos_acero_pendiente
            ),
            detail: "tramos excluidos hasta validar",
          },
        ]}
        warnings={[
          ...(validation.advertencias || []),
          ...(steelValidation.advertencias || []),
        ]}
      />
    );
  }

  return (
    <div className="p-5 sm:p-7">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <BeamMetric
          label="Tramos computados"
          value={formatNumber(
            validation.tramos_computados ??
              items.length
          )}
          detail={`${formatNumber(
            validation.apoyos_columnas_detectados
          )} apoyos vectoriales`}
        />

        <BeamMetric
          label="Longitud entre ejes"
          value={formatNumber(
            totals.lengthBetweenAxes,
            "m"
          )}
          detail="distancia de centro a centro"
        />

        <BeamMetric
          label="Longitud libre"
          value={formatNumber(
            totals.clearLength,
            "m"
          )}
          detail="distancia entre caras de apoyos"
        />

        <BeamMetric
          label="Confianza geométrica"
          value={`${formatNumber(
            validation.tramos_confianza_geometrica_alta
          )} alta`}
          detail={`${formatNumber(
            validation.tramos_confianza_geometrica_media
          )} tramos con confianza media`}
        />
      </div>

      {view === "acero" && (
        <div className="mt-7">
          <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
            <div>
              <h3 className="font-display text-lg font-bold text-ink">
                Acero por diámetro
              </h3>

              <p className="mt-1 text-[11px] text-slate-400">
                Subtotal de los tramos cuya sección coincide con
                el detalle de armadura.
              </p>
            </div>

            <ComputationStatus
              status={
                steelValidation.resultado_completo
                  ? "calculado"
                  : steelValidation.tramos_acero_computado > 0
                    ? "parcial"
                    : "pendiente"
              }
            />
          </div>

          {steelSummary.length > 0 ? (
            <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200">
              <table className="min-w-[720px] w-full border-collapse text-left">
                <thead className="bg-slate-50">
                  <tr className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                    <th className="px-4 py-3">Diámetro</th>
                    <th className="px-4 py-3 text-right">Longitudinales</th>
                    <th className="px-4 py-3 text-right">Estribos</th>
                    <th className="px-4 py-3 text-right">Total</th>
                    <th className="px-4 py-3 text-right">Peso</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {steelSummary.map((row) => (
                    <tr
                      key={row.diametro_pulgadas}
                      className="text-xs text-slate-600"
                    >
                      <td className="px-4 py-3 font-extrabold text-ink">
                        Ø {row.diametro_pulgadas}&quot;
                      </td>
                      <td className="px-4 py-3 text-right">
                        {formatNumber(
                          row.metros_longitudinales,
                          "m"
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {formatNumber(
                          row.metros_estribos,
                          "m"
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {formatNumber(
                          row.metros_totales,
                          "m"
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-ink">
                        {formatNumber(row.peso_kg, "kg")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-xs leading-5 text-amber-700">
              No hay tramos con armadura validada para mostrar.
            </div>
          )}
        </div>
      )}

      {view === "tipos" && (
      <div className="mt-7">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
          <div>
            <h3 className="font-display text-lg font-bold text-ink">
              Resumen por tipo y sección
            </h3>

            <p className="mt-1 text-[11px] text-slate-400">
              Una misma referencia puede aparecer en más de una
              fila cuando cambia su sección.
            </p>
          </div>

          <span className="text-[10px] font-bold text-slate-400">
            {summary.length} grupos
          </span>
        </div>

        <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200">
          <table className="min-w-[1040px] w-full border-collapse text-left">
            <thead className="bg-slate-50">
              <tr className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                <th className="px-4 py-3">Viga</th>
                <th className="px-4 py-3">Sección</th>
                <th className="px-4 py-3 text-right">Tramos</th>
                <th className="px-4 py-3 text-right">Entre ejes</th>
                <th className="px-4 py-3 text-right">Longitud libre</th>
                <th className="px-4 py-3 text-right">Hormigón</th>
                <th className="px-4 py-3 text-right">Acero</th>
                <th className="px-4 py-3 text-right">Encofrado</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {summary.map((row, index) => (
                <tr
                  key={`${row.referencia}-${row.ancho_m}-${row.alto_m}-${index}`}
                  className="text-xs text-slate-600 transition hover:bg-slate-50/70"
                >
                  <td className="px-4 py-3 font-extrabold text-ink">
                    {row.referencia || "—"}
                  </td>
                  <td className="px-4 py-3 font-semibold">
                    {formatNumber(row.ancho_m)} ×{" "}
                    {formatNumber(row.alto_m)} m
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {formatNumber(row.cantidad_tramos)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {formatNumber(
                      row.longitud_total_entre_ejes_m,
                      "m"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {formatNumber(
                      row.longitud_total_libre_m,
                      "m"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-ink">
                    {formatNumber(
                      row.volumen_hormigon_m3,
                      "m³"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <strong className="block text-ink">
                      {formatNumber(row.peso_acero_kg, "kg")}
                    </strong>
                    <ComputationStatus
                      status={
                        row.estado_acero === "computado"
                          ? "calculado"
                          : row.estado_acero === "parcial"
                            ? "parcial"
                            : "pendiente"
                      }
                    />
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-ink">
                    {formatNumber(
                      row.encofrado_total_m2,
                      "m²"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      )}

      {view === "tramos" && (
      <div className="mt-8 border-t border-slate-100 pt-7">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <h3 className="font-display text-lg font-bold text-ink">
              Tramos columna a columna
            </h3>

            <p className="mt-1 text-[11px] text-slate-400">
              {filteredItems.length} de {items.length} tramos
              visibles.
            </p>
          </div>

          <div className="grid gap-2 sm:grid-cols-[170px_260px]">
            <select
              className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 outline-none transition focus:border-accent"
              value={referenceFilter}
              onChange={(event) =>
                setReferenceFilter(event.target.value)
              }
              aria-label="Filtrar por referencia de viga"
            >
              <option value="todas">
                Todas las vigas
              </option>

              {references.map((reference) => (
                <option
                  key={reference}
                  value={reference}
                >
                  {reference}
                </option>
              ))}
            </select>

            <input
              className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-600 outline-none transition placeholder:text-slate-300 focus:border-accent"
              type="search"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Buscar tramo, viga o apoyo"
              aria-label="Buscar tramos de vigas"
            />
          </div>
        </div>

        <div className="mt-3 max-h-[560px] overflow-auto rounded-2xl border border-slate-200">
          <table className="min-w-[1400px] w-full border-collapse text-left">
            <thead className="sticky top-0 z-10 bg-slate-50 shadow-[0_1px_0_rgba(226,232,240,1)]">
              <tr className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                <th className="px-4 py-3">Tramo</th>
                <th className="px-4 py-3">Viga / sección</th>
                <th className="px-4 py-3">Apoyo inicial</th>
                <th className="px-4 py-3">Apoyo final</th>
                <th className="px-4 py-3 text-right">Entre ejes</th>
                <th className="px-4 py-3 text-right">Longitud libre</th>
                <th className="px-4 py-3 text-right">Hormigón</th>
                <th className="px-4 py-3 text-right">Acero</th>
                <th className="px-4 py-3 text-right">Encofrado</th>
                <th className="px-4 py-3">Confianza</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {filteredItems.map((item) => (
                <tr
                  key={item.tramo_id}
                  className={`text-[11px] text-slate-600 transition ${
                    item.revision_ingeniero
                      ? "bg-emerald-50/70 hover:bg-emerald-50"
                      : item.estado_acero &&
                    item.estado_acero !== "computado"
                        ? "bg-amber-50/70 hover:bg-amber-50"
                        : "hover:bg-slate-50/70"
                  }`}
                >
                  <td className="px-4 py-3 font-extrabold text-ink">
                    {item.tramo_id || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <strong className="block text-ink">
                      {item.referencia || "—"}
                    </strong>
                    <span className="mt-0.5 block text-[9px] text-slate-400">
                      {formatNumber(item.ancho_m)} ×{" "}
                      {formatNumber(item.alto_m)} m
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <strong className="block text-ink">
                      {item.referencia_apoyo_inicial || "—"}
                    </strong>
                    <span className="mt-0.5 block text-[9px] text-slate-400">
                      {item.apoyo_inicial_id || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <strong className="block text-ink">
                      {item.referencia_apoyo_final || "—"}
                    </strong>
                    <span className="mt-0.5 block text-[9px] text-slate-400">
                      {item.apoyo_final_id || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {formatNumber(
                      item.longitud_entre_ejes_m,
                      "m"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {formatNumber(
                      item.longitud_libre_entre_caras_m,
                      "m"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {formatNumber(
                      item.volumen_hormigon_m3,
                      "m³"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <strong className="block text-ink">
                      {formatNumber(
                        item.peso_acero_total_kg,
                        "kg"
                      )}
                    </strong>
                    {item.estado_acero === "computado" ? (
                      <>
                        <span className="mt-0.5 block text-[9px] text-slate-400">
                          {formatNumber(
                            item.cantidad_estribos
                          )}{" "}
                          estribos
                        </span>

                        {item.revision_ingeniero && (
                          <span className="mt-1 inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[8px] font-extrabold uppercase tracking-wider text-emerald-700">
                            Validado por ingeniero
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="mt-1 inline-flex rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-[8px] font-extrabold uppercase tracking-wider text-amber-700">
                        {String(
                          item.estado_acero || "pendiente"
                        ).replaceAll("_", " ")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {formatNumber(
                      item.encofrado_total_m2,
                      "m²"
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <BeamConfidence
                      value={item.confianza_geometria}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {filteredItems.length === 0 && (
            <div className="p-8 text-center text-xs text-slate-400">
              No hay tramos que coincidan con los filtros.
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  );
}

function PedestalesDetail({
  items = [],
  validation = {},
  view = "detalle",
}) {
  if (!items.length) {
    return (
      <div className="p-8 text-center sm:p-12">
        <h3 className="font-display text-lg font-bold text-ink">
          No hay pedestales computados
        </h3>

        <p className="mx-auto mt-2 max-w-xl text-xs leading-5 text-slate-500">
          Volvé a ejecutar el análisis con el backend actualizado.
          Los pedestales se generan únicamente para columnas con
          apoyo directo sobre una fundación.
        </p>
      </div>
    );
  }

  if (view === "validaciones") {
    return (
      <ValidationPanel
        metrics={[
          {
            label: "Apoyos directos",
            value: formatNumber(
              validation.cantidad_apoyos_directos
            ),
            detail: "columnas apoyadas sobre fundaciones",
          },
          {
            label: "Pedestales computados",
            value: formatNumber(
              validation.cantidad_pedestales_computados
            ),
            detail: "incluidos en el resultado preliminar",
          },
          {
            label: "Tipos computados",
            value: formatNumber(
              validation.cantidad_tipos_computados
            ),
            detail: "secciones distintas de pedestal",
          },
          {
            label: validation.altura_real_disponible
              ? "Alturas reales"
              : "Altura utilizada",
            value: validation.altura_real_disponible
              ? formatNumber(
                  validation.referencias_con_altura?.length
                )
              : formatNumber(
                  validation.altura_utilizada_m,
                  "m"
                ),
            detail: validation.altura_real_disponible
              ? "referencias validadas por el profesional"
              : "altura mínima configurada",
          },
          {
            label: "Acero computado",
            value: `${formatNumber(
              validation.cantidad_tipos_acero_computados || 0
            )} / ${formatNumber(
              validation.cantidad_tipos_computados || 0
            )}`,
            detail: validation.acero_resultado_completo
              ? "tipos con armadura disponible"
              : "solo las referencias válidas integran el subtotal",
          },
          {
            label: "Armaduras heredadas",
            value: formatNumber(
              validation.referencias_armadura_heredada?.length || 0
            ),
            detail: "usan el acero de la columna asociada",
          },
        ]}
        warnings={validation.advertencias || []}
      />
    );
  }

  return (
    <div className="p-5 sm:p-7">
      <div className="grid gap-3 sm:grid-cols-2">
        <BeamMetric
          label="Pedestales"
          value={formatNumber(
            validation.cantidad_pedestales_computados
          )}
          detail={`${formatNumber(
            validation.cantidad_tipos_computados
          )} tipos computados`}
        />

        <BeamMetric
          label="Incremento de sección"
          value={formatNumber(
            validation.incremento_pedestal_cm,
            "cm"
          )}
          detail="respecto de la columna"
        />
      </div>

      <div className="mt-7">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
          <div>
            <h3 className="font-display text-lg font-bold text-ink">
              Cómputo por tipo de pedestal
            </h3>

            <p className="mt-1 text-[11px] text-slate-400">
              Se incluyen solamente apoyos directos sobre
              fundaciones.
            </p>
          </div>

          <span className="text-[10px] font-bold text-slate-400">
            {items.length} tipos
          </span>
        </div>

        <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200">
          <table className="min-w-[1420px] w-full border-collapse text-left">
            <thead className="bg-slate-50">
              <tr className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                <th className="px-4 py-3">Columna</th>
                <th className="px-4 py-3 text-right">Cantidad</th>
                <th className="px-4 py-3">Sección columna</th>
                <th className="px-4 py-3">Sección pedestal</th>
                <th className="px-4 py-3 text-right">Altura</th>
                <th className="px-4 py-3 text-right">Hormigón unitario</th>
                <th className="px-4 py-3 text-right">Hormigón total</th>
                <th className="px-4 py-3 text-right">Encofrado total</th>
                <th className="px-4 py-3">Armadura aplicada</th>
                <th className="px-4 py-3 text-right">Acero total</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {items.map((item, index) => (
                <tr
                  key={`${item.referencia_columna}-${index}`}
                  className="text-[11px] text-slate-600 transition hover:bg-slate-50/70"
                >
                  <td className="px-4 py-3 font-extrabold text-ink">
                    {item.referencia_columna || "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    {formatNumber(item.cantidad)}
                  </td>
                  <td className="px-4 py-3">
                    {formatNumber(
                      item.dimension_columna_1_m
                    )}{" "}
                    ×{" "}
                    {formatNumber(
                      item.dimension_columna_2_m
                    )}{" "}
                    m
                  </td>
                  <td className="px-4 py-3 font-semibold text-ink">
                    {formatNumber(
                      item.dimension_pedestal_1_m
                    )}{" "}
                    ×{" "}
                    {formatNumber(
                      item.dimension_pedestal_2_m
                    )}{" "}
                    m
                  </td>
                  <td className="px-4 py-3 text-right">
                    {formatNumber(
                      item.altura_real_m ??
                        item.altura_m ??
                        item.altura_minima_m,
                      "m"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {formatNumber(
                      item.volumen_unitario_m3,
                      "m³"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-ink">
                    {formatNumber(
                      item.volumen_total_m3,
                      "m³"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-ink">
                    {formatNumber(
                      item.encofrado_total_m2,
                      "m²"
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <strong className="block text-[10px] text-ink">
                      {(item.armadura_pedestal
                        ?.grupos_longitudinales || [])
                        .map(
                          (group) =>
                            `${group.cantidad} Ø ${group.diametro_pulgadas}"`
                        )
                        .join(" + ") || "Pendiente"}
                    </strong>
                    <span className="mt-1 block text-[9px] leading-4 text-slate-400">
                      {item.origen_armadura_pedestal ===
                      "heredada_de_columna"
                        ? "Heredada de la columna"
                        : item.origen_armadura_pedestal ===
                            "especifica_pedestal"
                          ? "Específica del pedestal"
                          : "Sin fuente válida"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-ink">
                    {item.acero_disponible
                      ? formatNumber(
                          item.peso_acero_total_kg ??
                            item.acero_kg,
                          "kg"
                        )
                      : "Pendiente"}
                    {item.acero_disponible &&
                      item.usa_altura_minima_para_acero && (
                        <span className="mt-1 block text-[8px] font-semibold uppercase tracking-wider text-amber-600">
                          Preliminar
                        </span>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StructureCard({
  active,
  code,
  title,
  description,
  mainValue,
  mainLabel,
  stats,
  status,
  alertCount = 0,
  tone = "foundation",
  onClick,
}) {
  const tones = {
    foundation: {
      active:
        "border-accent bg-accent/[0.045] ring-2 ring-accent/15",
      code: "bg-accent text-white",
      status:
        "border-emerald-200 bg-emerald-50 text-emerald-700",
    },
    pedestal: {
      active:
        "border-amber-400 bg-amber-50/60 ring-2 ring-amber-100",
      code: "bg-amber-500 text-white",
      status:
        "border-amber-200 bg-amber-50 text-amber-700",
    },
    beam: {
      active:
        "border-indigo-400 bg-indigo-50/60 ring-2 ring-indigo-100",
      code: "bg-indigo-600 text-white",
      status:
        "border-indigo-200 bg-indigo-50 text-indigo-700",
    },
    column: {
      active:
        "border-violet-400 bg-violet-50/60 ring-2 ring-violet-100",
      code: "bg-violet-600 text-white",
      status:
        "border-amber-200 bg-amber-50 text-amber-700",
    },
  };

  const selectedTone =
    tones[tone] || tones.foundation;

  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`group flex min-h-[245px] w-full flex-col rounded-3xl border p-5 text-left shadow-[0_14px_35px_rgba(16,34,53,.055)] transition duration-200 hover:-translate-y-1 hover:shadow-[0_20px_45px_rgba(16,34,53,.10)] sm:p-6 ${
        active
          ? selectedTone.active
          : "border-slate-200 bg-white hover:border-slate-300"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <span
          className={`flex h-11 min-w-11 items-center justify-center rounded-2xl px-3 text-xs font-black tracking-wider shadow-sm ${selectedTone.code}`}
        >
          {code}
        </span>

        <div className="flex flex-wrap justify-end gap-1.5">
          {alertCount > 0 && (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[8px] font-extrabold uppercase tracking-wider text-amber-700">
              {alertCount} {alertCount === 1 ? "alerta" : "alertas"}
            </span>
          )}

          <span
            className={`rounded-full border px-2.5 py-1 text-[8px] font-extrabold uppercase tracking-wider ${selectedTone.status}`}
          >
            {status}
          </span>
        </div>
      </div>

      <div className="mt-5">
        <h2 className="font-display text-xl font-bold tracking-tight text-ink">
          {title}
        </h2>

        <p className="mt-1 min-h-10 text-[11px] leading-5 text-slate-400">
          {description}
        </p>
      </div>

      <div className="mt-4 flex items-end justify-between gap-4 border-t border-slate-200/80 pt-4">
        <div>
          <strong className="block font-display text-3xl font-black tracking-tight text-ink">
            {mainValue}
          </strong>

          <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
            {mainLabel}
          </span>
        </div>

        <span
          className={`text-lg font-bold transition group-hover:translate-x-1 ${
            active
              ? "text-ink"
              : "text-slate-300"
          }`}
          aria-hidden="true"
        >
          →
        </span>
      </div>

      <div className="mt-4 grid w-full grid-cols-3 gap-2">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="min-w-0 rounded-xl bg-white/75 px-2.5 py-2"
          >
            <span className="block truncate text-[8px] font-extrabold uppercase tracking-wider text-slate-400">
              {stat.label}
            </span>

            <strong className="mt-1 block truncate text-[11px] font-extrabold text-ink">
              {stat.value}
            </strong>
          </div>
        ))}
      </div>
    </button>
  );
}

function ColumnasDetail({
  directItems = [],
  linkedItems = [],
  validation = {},
  view = "elementos",
}) {
  const [search, setSearch] = useState("");

  const columns = useMemo(() => {
    const normalized = [
      ...directItems.map((item) => ({
        ...item,
        relationType: "directa",
        columnReference:
          item.referencia_columna,
      })),
      ...linkedItems.map((item) => ({
        ...item,
        relationType: "viga",
        columnReference:
          item.referencia_columna_vinculada ||
          item.referencia_columna,
      })),
    ].filter((item) => item.columnReference);

    const seen = new Set();

    return normalized.filter((item) => {
      const position =
        item.posicion_rotulo_columna_vinculada_pdf ||
        item.posicion_rotulo_columna_pdf ||
        {};

      const key = [
        item.fundacion_id,
        item.columnReference,
        position.x,
        position.y,
      ].join("|");

      if (seen.has(key)) {
        return false;
      }

      seen.add(key);
      return true;
    });
  }, [directItems, linkedItems]);

  const visibleColumns = useMemo(() => {
    if (view === "directas") {
      return columns.filter(
        (item) => item.relationType === "directa"
      );
    }

    if (view === "vinculadas") {
      return columns.filter(
        (item) => item.relationType === "viga"
      );
    }

    return columns;
  }, [columns, view]);

  const filteredColumns = useMemo(() => {
    const normalizedSearch = search
      .trim()
      .toLowerCase();

    if (!normalizedSearch) {
      return visibleColumns;
    }

    return visibleColumns.filter((item) =>
      [
        item.fundacion_id,
        item.referencia_fundacion,
        item.columnReference,
        item.referencia_viga,
        item.origen_seccion,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(normalizedSearch)
    );
  }, [search, visibleColumns]);

  const sectionReferences = Array.isArray(
    validation.referencias_con_seccion
  )
    ? validation.referencias_con_seccion.length
    : 0;

  const realHeightAvailable =
    validation.altura_real_disponible === true;

  if (!columns.length) {
    return (
      <div className="p-8 text-center sm:p-12">
        <h3 className="font-display text-lg font-bold text-ink">
          No hay columnas asociadas
        </h3>

        <p className="mx-auto mt-2 max-w-xl text-xs leading-5 text-slate-500">
          El análisis todavía no devolvió asociaciones de
          columnas para mostrar en esta sección.
        </p>
      </div>
    );
  }

  if (view === "validaciones") {
    return (
      <ValidationPanel
        metrics={[
          {
            label: "Rótulos detectados",
            value: formatNumber(
              validation.rotulos_columnas_detectados
            ),
            detail: "columnas localizadas en planta",
          },
          {
            label: "Apoyos directos",
            value: formatNumber(
              validation.columnas_directas_asociadas ??
                directItems.length
            ),
            detail: "columnas asociadas a fundaciones",
          },
          {
            label: "Vinculadas por vigas",
            value: formatNumber(
              validation.columnas_vinculadas_por_viga ??
                linkedItems.length
            ),
            detail: "confirmadas geométricamente",
          },
          {
            label: "Pendientes",
            value: formatNumber(
              validation.columnas_pendientes_clasificacion
            ),
            detail: "relaciones sin clasificar",
          },
        ]}
        warnings={validation.advertencias || []}
      />
    );
  }

  return (
    <div className="p-5 sm:p-7">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <BeamMetric
          label="Rótulos detectados"
          value={formatNumber(
            validation.rotulos_columnas_detectados
          )}
          detail="columnas localizadas en planta"
        />

        <BeamMetric
          label="Apoyos directos"
          value={formatNumber(
            validation.columnas_directas_asociadas ??
              directItems.length
          )}
          detail="asociados a fundaciones"
        />

        <BeamMetric
          label="Vinculadas por vigas"
          value={formatNumber(
            validation.columnas_vinculadas_por_viga ??
              linkedItems.length
          )}
          detail="confirmadas geométricamente"
        />

        <BeamMetric
          label="Tipos con sección"
          value={formatNumber(sectionReferences)}
          detail="referencias dimensionales"
        />

        <BeamMetric
          label="Altura real"
          value={
            realHeightAvailable
              ? "Disponible"
              : "Pendiente"
          }
          detail="necesaria para el cómputo"
        />
      </div>

      <div className="mt-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h3 className="font-display text-lg font-bold text-ink">
            Columnas relacionadas con fundaciones
          </h3>

          <p className="mt-1 text-[11px] text-slate-400">
            {filteredColumns.length} de {visibleColumns.length}{" "}
            columnas visibles.
          </p>
        </div>

        <input
          className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-600 outline-none transition placeholder:text-slate-300 focus:border-accent sm:w-[280px]"
          type="search"
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
          placeholder="Buscar columna, fundación o viga"
          aria-label="Buscar columnas"
        />
      </div>

      <div className="mt-3 max-h-[560px] overflow-auto rounded-2xl border border-slate-200">
        <table className="min-w-[1160px] w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-slate-50 shadow-[0_1px_0_rgba(226,232,240,1)]">
            <tr className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
              <th className="px-4 py-3">Columna</th>
              <th className="px-4 py-3">Fundación</th>
              <th className="px-4 py-3">Relación</th>
              <th className="px-4 py-3">Sección real</th>
              <th className="px-4 py-3 text-right">Altura</th>
              <th className="px-4 py-3 text-right">Hormigón</th>
              <th className="px-4 py-3 text-right">Encofrado</th>
              <th className="px-4 py-3 text-right">Acero</th>
              <th className="px-4 py-3">Plano de origen</th>
              <th className="px-4 py-3">Estado</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100">
            {filteredColumns.map((item, index) => (
              <tr
                key={`${item.fundacion_id}-${item.columnReference}-${item.relationType}-${index}`}
                className="text-[11px] text-slate-600 transition hover:bg-slate-50/70"
              >
                <td className="px-4 py-3 font-extrabold text-ink">
                  {item.columnReference}
                </td>
                <td className="px-4 py-3 font-semibold">
                  {item.fundacion_id || "—"}
                </td>
                <td className="px-4 py-3">
                  {item.relationType === "viga"
                    ? `Vinculada por ${
                        item.referencia_viga || "viga"
                      }`
                    : "Apoyo directo"}
                </td>
                <td className="px-4 py-3 font-semibold text-ink">
                  {formatNumber(item.ancho_m)} ×{" "}
                  {formatNumber(item.largo_m)} m
                </td>
                <td className="px-4 py-3 text-right font-semibold">
                  {formatNumber(item.altura_m, "m")}
                </td>
                <td className="px-4 py-3 text-right font-semibold text-ink">
                  {formatNumber(
                    item.volumen_hormigon_m3,
                    "m³"
                  )}
                </td>
                <td className="px-4 py-3 text-right font-semibold text-ink">
                  {formatNumber(
                    item.encofrado_total_m2,
                    "m²"
                  )}
                </td>
                <td className="px-4 py-3 text-right font-semibold text-ink">
                  {formatNumber(
                    item.peso_acero_total_kg,
                    "kg"
                  )}
                </td>
                <td className="px-4 py-3">
                  {item.origen_seccion || "—"}
                </td>
                <td className="px-4 py-3">
                  <BeamConfidence
                    value={
                      item.requiere_revision_geometrica ||
                      item.requiere_revision_asociacion
                        ? "media"
                        : "alta"
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredColumns.length === 0 && (
          <div className="p-8 text-center text-xs text-slate-400">
            No hay columnas que coincidan con la búsqueda.
          </div>
        )}
      </div>
    </div>
  );
}

function Results({
  results: externalResults,
  error,
  onBack,
  onNewAnalysis,
  onDownload,
  onResultsChange,
  apiBaseUrl = DEFAULT_API_BASE_URL,
}) {
  const [reviewedResults, setReviewedResults] =
    useState(null);

  const [reviewDialog, setReviewDialog] =
    useState(null);

  const [savingReview, setSavingReview] =
    useState(false);

  const [reviewError, setReviewError] =
    useState("");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReviewedResults(null);
    setReviewDialog(null);
    setReviewError("");
  }, [externalResults]);

  const results =
    reviewedResults || externalResults;

  const [activeStructure, setActiveStructure] =
    useState(null);

  const [detailTab, setDetailTab] =
    useState("hormigon");

  const analysisAlerts = useMemo(
    () => buildAnalysisAlerts(results),
    [results]
  );

  const groupedAnalysisAlerts = useMemo(
    () =>
      analysisAlerts.reduce(
        (groups, alert) => {
          groups[alertWorkflowClass(alert)].push(alert);
          return groups;
        },
        {
          inconsistencia: [],
          dato_requerido: [],
          revision_tecnica: [],
          observacion: [],
        }
      ),
    [analysisAlerts]
  );

  if (!results) {
    return (
      <main className="mx-auto w-full max-w-[1440px] px-5 py-10 sm:px-8 lg:px-10">
        <div className="rounded-3xl border border-slate-200 bg-white p-10 text-center">
          <h1 className="font-display text-2xl font-bold text-ink">
            No hay resultados disponibles
          </h1>
          <p role={error ? "alert" : undefined} className="mx-auto mt-3 max-w-xl text-sm text-slate-600">
            {error || "Todavía no hay un análisis completado guardado para este proyecto. Cargá los PDF e iniciá el análisis; si aparece una revisión pendiente, resolvela para continuar."}
          </p>

          <button
            className="mt-5 rounded-xl bg-accent px-5 py-3 text-xs font-extrabold text-white"
            type="button"
            onClick={onNewAnalysis}
          >
            Cargar planos
          </button>
        </div>
      </main>
    );
  }

  const foundations =
    results.fundaciones || [];

  const formwork =
    results.encofrado_zapatas_detalle || [];

  const reinforcements =
    results.armaduras || [];

  const foundationSteelAvailable =
    results.peso_acero_kg !== null &&
    results.peso_acero_kg !== undefined;

  const locations =
    results.ubicaciones_fundaciones || [];

  const locationValidation =
    results.validacion_ubicaciones || {};

  const pedestalItems =
    results.pedestales_computo_detalle || [];

  const pedestalValidation =
    results.validacion_pedestales || {};

  const beamSegments =
    results.vigas_riostra_computo_detalle || [];

  const beamSummary =
    results.resumen_vigas_riostra_por_tipo || [];

  const beamSteelSummary =
    results.resumen_acero_vigas_riostra || [];

  const beamValidation =
    results.validacion_computo_vigas_riostra || {};

  const beamSteelValidation =
    results.validacion_acero_vigas_riostra || {};

  const beamSteelAvailable =
    Boolean(beamValidation.acero_disponible) ||
    (beamSteelValidation.tramos_acero_computado || 0) > 0;

  const beamSteelComplete = Boolean(
    beamValidation.acero_resultado_completo ??
      beamSteelValidation.resultado_completo
  );

  const directColumns =
    results.columnas_fundaciones || [];

  const linkedColumns =
    results.columnas_vinculadas_por_viga || [];

  const columnValidation =
    results.validacion_columnas || {};

  const pedestalHeightsValidated = Boolean(
    pedestalValidation.altura_real_disponible
  );

  const pedestalSteelAvailable =
    results.acero_pedestales_kg !== null &&
    results.acero_pedestales_kg !== undefined &&
    Boolean(pedestalValidation.acero_disponible);

  const pedestalSteelComplete = Boolean(
    pedestalValidation.acero_resultado_completo
  );

  const pedestalSteelConfirmed = Boolean(
    pedestalValidation.armaduras_pedestales_confirmadas
  );

  const columnHeightsValidated = Boolean(
    columnValidation.altura_real_disponible
  );

  const columnSteelAvailable =
    results.acero_columnas_kg !== null &&
    results.acero_columnas_kg !== undefined &&
    columnValidation.armaduras_columnas_confirmadas ===
      true;

  const corrections =
    results.correcciones_referencias_aplicadas ||
    [];

  const engineeringReviews = Array.isArray(
    results.revisiones_ingeniero
  )
    ? results.revisiones_ingeniero
    : [];

  const previousTechnicalAudit =
    results.enrutamiento_documentos?.auditoria_tecnica || null;

  const previousAuditIncidents = Array.isArray(
    previousTechnicalAudit?.incidencias
  )
    ? previousTechnicalAudit.incidencias
    : [];

  const previousResolvedCount = previousAuditIncidents.filter(
    (item) => item?.resuelta
  ).length;

  const previousPendingCount = previousAuditIncidents.filter(
    (item) => !item?.resuelta
  ).length;

  const inconsistencyCount =
    groupedAnalysisAlerts.inconsistencia.length;
  const requiredDataCount =
    groupedAnalysisAlerts.dato_requerido.length;
  const technicalReviewCount =
    groupedAnalysisAlerts.revision_tecnica.length;
  const observationCount =
    groupedAnalysisAlerts.observacion.length;

  const alertsByFamily = analysisAlerts.reduce(
    (groups, alert) => {
      const family = alert.familia || "general";

      if (!groups[family]) {
        groups[family] = [];
      }

      groups[family].push(alert);

      return groups;
    },
    {}
  );

  const activeAlerts = activeStructure
    ? alertsByFamily[activeStructure] || []
    : [];

  const activeEngineeringReviews = activeStructure
    ? engineeringReviews.filter((item) => {
        const family =
          item?.familia ||
          (item?.tipo_revision === "seccion_viga"
            ? "vigas"
            : "general");

        return family === activeStructure;
      })
    : engineeringReviews;

  const errorAlertCount = analysisAlerts.filter(
    (alert) => alert.severidad === "error"
  ).length;

  const excludedAlertCount = analysisAlerts.filter(
    (alert) => alert.excluido_del_computo
  ).length;

  const hasAnalysisAlerts = analysisAlerts.length > 0;

  const resultStatusTitle = errorAlertCount > 0
    ? "Procesamiento finalizado con errores"
    : inconsistencyCount > 0
      ? "Cómputo realizado con inconsistencias nuevas"
      : hasAnalysisAlerts
        ? "Cómputo realizado con tareas pendientes"
        : "Procesamiento finalizado correctamente";

  const resultStatusParts = [];

  if (previousResolvedCount > 0) {
    resultStatusParts.push(
      `Se conservaron ${previousResolvedCount} ${
        previousResolvedCount === 1
          ? "corrección previa"
          : "correcciones previas"
      }.`
    );
  }

  if (previousPendingCount > 0) {
    resultStatusParts.push(
      `${previousPendingCount} ${
        previousPendingCount === 1
          ? "hallazgo documental previo sigue abierto"
          : "hallazgos documentales previos siguen abiertos"
      }.`
    );
  }

  if (inconsistencyCount > 0) {
    resultStatusParts.push(
      `${inconsistencyCount} ${
        inconsistencyCount === 1
          ? "inconsistencia nueva fue detectada por el motor"
          : "inconsistencias nuevas fueron detectadas por el motor"
      }.`
    );
  }

  if (requiredDataCount > 0) {
    resultStatusParts.push(
      `${requiredDataCount} ${
        requiredDataCount === 1
          ? "dato técnico falta para completar cantidades"
          : "datos técnicos faltan para completar cantidades"
      }.`
    );
  }

  if (technicalReviewCount > 0) {
    resultStatusParts.push(
      `${technicalReviewCount} ${
        technicalReviewCount === 1
          ? "validación técnica sigue pendiente"
          : "validaciones técnicas siguen pendientes"
      }.`
    );
  }

  if (observationCount > 0) {
    resultStatusParts.push(
      `${observationCount} ${
        observationCount === 1
          ? "observación de lectura requiere confirmación"
          : "observaciones de lectura requieren confirmación"
      }.`
    );
  }

  if (resultStatusParts.length === 0) {
    resultStatusParts.push(
      "No se detectaron inconsistencias ni datos pendientes en los resultados generados."
    );
  }

  if (excludedAlertCount > 0) {
    resultStatusParts.push(
      `${excludedAlertCount} ${
        excludedAlertCount === 1
          ? "cantidad quedó fuera de su subtotal afectado"
          : "cantidades quedaron fuera de sus subtotales afectados"
      }.`
    );
  }

  const sectionTitles = {
    fundaciones: {
      eyebrow: "Cómputo de fundaciones",
      title: "Fundaciones",
      description:
        foundationSteelAvailable
          ? "Hormigón, encofrado, acero y ubicación de cada elemento."
          : "Hormigón y encofrado verificados; el acero permanece pendiente de una fuente suficiente.",
    },
    pedestales: {
      eyebrow: "Cómputo preliminar de pedestales",
      title: "Pedestales",
      description:
        "Hormigón, encofrado y acero para apoyos directos sobre fundaciones.",
    },
    vigas: {
      eyebrow: "Cómputo de vigas de riostra",
      title: "Vigas de riostra",
      description:
        "Resumen por sección y detalle de cada tramo entre apoyos.",
    },
    columnas: {
      eyebrow: "Lectura y asociación de columnas",
      title: "Columnas",
      description:
        "Secciones detectadas y relación espacial con las fundaciones.",
    },
  };

  const activeSectionTitle = activeStructure
    ? sectionTitles[activeStructure]
    : null;

  const activeTabs = activeStructure
    ? DETAIL_TABS[activeStructure]
    : [];

  const materialsByStructure = {
    fundaciones: [
      {
        label: "Hormigón",
        value: formatNumber(
          results.volumen_hormigon_m3,
          "m³"
        ),
        detail: "volumen total calculado",
        status: "calculado",
      },
      {
        label: "Acero",
        value: foundationSteelAvailable
          ? formatNumber(results.peso_acero_kg, "kg")
          : "Pendiente",
        detail: foundationSteelAvailable
          ? "peso total de armaduras"
          : "sin detalle de armadura inequívoco",
        status: foundationSteelAvailable ? "calculado" : "pendiente",
      },
      {
        label: "Encofrado",
        value: formatNumber(
          results.encofrado_zapatas_m2,
          "m²"
        ),
        detail: "superficie total calculada",
        status: "calculado",
      },
    ],
    pedestales: [
      {
        label: "Hormigón",
        value: formatNumber(
          results.hormigon_pedestales_m3,
          "m³"
        ),
        detail: pedestalHeightsValidated
          ? "calculado con alturas validadas"
          : "calculado con altura mínima",
        status: pedestalHeightsValidated
          ? "calculado"
          : "preliminar",
      },
      {
        label: "Acero",
        value: pedestalSteelAvailable
          ? formatNumber(
              results.acero_pedestales_kg,
              "kg"
            )
          : "Pendiente",
        detail: pedestalSteelComplete
          ? pedestalHeightsValidated && pedestalSteelConfirmed
            ? "armadura explícita o heredada de la columna asociada"
            : "subtotal preliminar; usa la altura mínima o una armadura aún por confirmar"
          : pedestalSteelAvailable
            ? `${formatNumber(
                pedestalValidation.cantidad_tipos_acero_computados
              )} tipos computados; quedan referencias pendientes`
            : "sin armadura válida para computar",
        status:
          pedestalSteelComplete &&
          pedestalHeightsValidated &&
          pedestalSteelConfirmed
            ? "calculado"
            : pedestalSteelAvailable
              ? pedestalSteelComplete
                ? "preliminar"
                : "parcial"
              : "pendiente",
      },
      {
        label: "Encofrado",
        value: formatNumber(
          results.encofrado_pedestales_m2,
          "m²"
        ),
        detail: "cuatro caras laterales",
        status: pedestalHeightsValidated
          ? "calculado"
          : "preliminar",
      },
    ],
    vigas: [
      {
        label: "Hormigón",
        value: formatNumber(
          results.hormigon_vigas_riostra_m3,
          "m³"
        ),
        detail: "volumen de los tramos computados",
        status: "calculado",
      },
      {
        label: "Acero",
        value: beamSteelAvailable
          ? formatNumber(
              results.acero_vigas_riostra_kg,
              "kg"
            )
          : "Pendiente",
        detail: beamSteelComplete
          ? "peso total de armaduras"
          : beamSteelAvailable
            ? `${formatNumber(
                beamSteelValidation.tramos_acero_computado
              )} de ${formatNumber(
                beamSteelValidation.tramos_geometria_computada
              )} tramos validados`
            : "armadura todavía no interpretada",
        status: beamSteelComplete
          ? "calculado"
          : beamSteelAvailable
            ? "parcial"
            : "pendiente",
      },
      {
        label: "Encofrado",
        value: formatNumber(
          results.encofrado_vigas_riostra_m2,
          "m²"
        ),
        detail: "superficie lateral calculada",
        status: "calculado",
      },
    ],
    columnas: [
      {
        label: "Hormigón",
        value: columnHeightsValidated
          ? formatNumber(
              results.hormigon_columnas_m3,
              "m³"
            )
          : "Pendiente",
        detail: columnHeightsValidated
          ? "calculado con alturas validadas"
          : "requiere altura real",
        status: columnHeightsValidated
          ? "calculado"
          : "pendiente",
      },
      {
        label: "Acero",
        value: columnSteelAvailable
          ? formatNumber(
              results.acero_columnas_kg,
              "kg"
            )
          : "Pendiente",
        detail: columnSteelAvailable
          ? "armaduras confirmadas por el profesional"
          : "requiere confirmar armaduras",
        status: columnSteelAvailable
          ? "calculado"
          : "pendiente",
      },
      {
        label: "Encofrado",
        value: columnHeightsValidated
          ? formatNumber(
              results.encofrado_columnas_m2,
              "m²"
            )
          : "Pendiente",
        detail: columnHeightsValidated
          ? "cuatro caras laterales"
          : "requiere altura real",
        status: columnHeightsValidated
          ? "calculado"
          : "pendiente",
      },
    ],
  };

  const statusByStructure = {
    fundaciones: {
      tone: foundationSteelAvailable ? "success" : "warning",
      title: foundationSteelAvailable
        ? "Cómputo completo de fundaciones"
        : "Geometría verificada · acero pendiente",
      description:
        foundationSteelAvailable
          ? "El hormigón, el acero y el encofrado fueron calculados a partir del cuadro y las armaduras detectadas."
          : "El hormigón y el encofrado usan dimensiones confirmadas por ocurrencia. No se inventó acero donde falta una fuente verificable.",
    },
    pedestales: {
      tone:
        pedestalHeightsValidated &&
        pedestalSteelComplete &&
        pedestalSteelConfirmed
          ? "success"
          : "warning",
      title:
        pedestalHeightsValidated &&
        pedestalSteelComplete &&
        pedestalSteelConfirmed
          ? "Cómputo de pedestales validado"
          : pedestalHeightsValidated
            ? "Geometría validada · acero en revisión"
            : "Cómputo preliminar de pedestales",
      description:
        pedestalHeightsValidated &&
        pedestalSteelComplete &&
        pedestalSteelConfirmed
          ? "El hormigón, el encofrado y el acero fueron calculados con alturas validadas. Cuando no existe detalle propio del pedestal, se usa la armadura confirmada de su columna asociada."
          : pedestalHeightsValidated
            ? "El hormigón y el encofrado usan alturas validadas. El acero disponible se obtiene del detalle propio del pedestal o, si falta, de la columna con la misma referencia."
            : `El hormigón, el encofrado y el acero preliminar utilizan una altura mínima de ${formatNumber(
                pedestalValidation.altura_utilizada_m,
                "m"
              )}. La procedencia de cada armadura queda identificada.`,
    },
    vigas: {
      tone:
        beamValidation.resultado_completo &&
        beamSteelComplete
        ? "success"
        : "warning",
      title:
        beamValidation.resultado_completo &&
        beamSteelComplete
          ? "Cómputo completo de vigas de riostra"
          : beamSteelAvailable
            ? "Geometría completa · acero parcial"
            : "La red de vigas requiere revisión",
      description: beamSteelComplete
        ? "Cada tramo está delimitado por apoyos consecutivos y su armadura fue validada contra el detalle correspondiente."
        : beamSteelAvailable
          ? `El subtotal de acero incluye ${formatNumber(
              beamSteelValidation.tramos_acero_computado
            )} tramos; ${formatNumber(
              beamSteelValidation.tramos_acero_pendiente
            )} permanecen fuera del total hasta validar su sección.`
          : "Cada tramo está delimitado por apoyos consecutivos. El acero permanece pendiente hasta interpretar las armaduras.",
    },
    columnas: {
      tone:
        columnHeightsValidated && columnSteelAvailable
          ? "success"
          : "warning",
      title:
        columnHeightsValidated && columnSteelAvailable
          ? "Cómputo de columnas validado"
          : columnHeightsValidated
            ? "Geometría de columnas validada"
            : "Secciones disponibles · cómputos pendientes",
      description:
        columnHeightsValidated && columnSteelAvailable
          ? "El hormigón, el encofrado y el acero fueron calculados con alturas y armaduras confirmadas por el profesional."
          : columnHeightsValidated
            ? "El hormigón y el encofrado fueron recalculados con alturas validadas. El acero permanece pendiente."
            : "Las secciones fueron detectadas, pero la altura y las armaduras todavía no están disponibles para calcular materiales.",
    },
  };

  const activeMaterials = activeStructure
    ? materialsByStructure[activeStructure]
    : [];

  const baseActiveStatus = activeStructure
    ? statusByStructure[activeStructure]
    : null;

  const activeStatus =
    baseActiveStatus && activeAlerts.length > 0
      ? {
          ...baseActiveStatus,
          tone: "warning",
          title: `${baseActiveStatus.title} · requiere revisión`,
          description: `${baseActiveStatus.description} Hay ${
            activeAlerts.length
          } ${
            activeAlerts.length === 1
              ? "alerta asociada"
              : "alertas asociadas"
          } a esta familia.`,
        }
      : baseActiveStatus;

  const openStructure = (structure) => {
    setActiveStructure(structure);
    setDetailTab(
      DETAIL_TABS[structure][0].id
    );

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const returnToSummary = () => {
    setActiveStructure(null);

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const openEngineeringReview = (alert) => {
    const segment = beamSegments.find(
      (item) =>
        String(item?.tramo_id) ===
        String(alert?.elemento_id)
    );

    setReviewError("");
    setReviewDialog({
      alert,
      segment,
    });
  };

  const closeEngineeringReview = () => {
    if (savingReview) {
      return;
    }

    setReviewDialog(null);
    setReviewError("");
  };

  const confirmEngineeringReview = async (payload) => {
    const analysisId =
      results.analisis_id || results.analysis_id;

    if (!analysisId) {
      setReviewError(
        "El análisis no tiene identificador. Ejecutá nuevamente el análisis con la API actualizada."
      );
      return;
    }

    setSavingReview(true);
    setReviewError("");

    try {
      const baseUrl = String(apiBaseUrl).replace(
        /\/$/,
        ""
      );
      const response = await fetch(
        `${baseUrl}/api/analisis/${analysisId}/revisiones/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );
      const body = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = Array.isArray(body?.detail)
          ? body.detail
              .map((item) => item?.msg)
              .filter(Boolean)
              .join(" ")
          : body?.detail;

        throw new Error(
          detail ||
            "No se pudo registrar la revisión profesional."
        );
      }

      const updatedResults = body?.resultado;

      if (!updatedResults) {
        throw new Error(
          "La API no devolvió los resultados recalculados."
        );
      }

      setReviewedResults(updatedResults);
      onResultsChange?.(updatedResults);
      setReviewDialog(null);
    } catch (error) {
      setReviewError(
        error instanceof Error
          ? error.message
          : "No se pudo registrar la revisión."
      );
    } finally {
      setSavingReview(false);
    }
  };

  const downloadCurrentResults = () => {
    if (!reviewedResults && onDownload) {
      onDownload(results);
      return;
    }

    const content = JSON.stringify(
      results,
      null,
      2
    );
    const blob = new Blob([content], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const suffix = results.analisis_id
      ? `_${results.analisis_id.slice(0, 8)}`
      : "";

    anchor.href = url;
    anchor.download = `resumen_computoestia${suffix}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="mx-auto w-full max-w-[1440px] px-5 py-10 sm:px-8 lg:px-10 lg:py-12">
      <ProgressSteps currentStep={2} />

      {results.revisiones_cuadro?.length > 0 && (
        <section className="mt-6 rounded-2xl border border-teal-200 bg-teal-50 p-5">
          <h2 className="font-bold text-teal-950">Correcciones del cuadro aplicadas</h2>
          {results.revisiones_cuadro.map((revision) => (
            <div key={revision.revision_id} className="mt-3 text-sm text-teal-950">
              <p className="font-semibold">{revision.revisor} · {new Date(revision.fecha_revision).toLocaleString("es-AR")}</p>
              {revision.correcciones.map((item) => (
                <p key={`${item.referencia_original}:${item.aparicion}`} className="mt-1">
                  {item.referencia_original}, aparición {item.aparicion} → <strong>{item.referencia_correcta}</strong>. {item.motivo}
                </p>
              ))}
            </div>
          ))}
        </section>
      )}

      {/* ENCABEZADO */}

      <div className="mt-10 flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
        <div>
          <div className="inline-flex items-center gap-3 text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">
            <span className="h-px w-8 bg-accent" />

            {activeSectionTitle
              ? `Resultados · ${activeSectionTitle.eyebrow}`
              : "Análisis completado"}

            {!activeSectionTitle && (
              <>
                {" · "}
                {formatDate(
                  results.fecha_analisis
                )}
              </>
            )}
          </div>

          <h1 className="mt-3 font-display text-4xl font-bold tracking-[-0.035em] text-ink sm:text-5xl">
            {activeSectionTitle?.title ||
              "Resultados del análisis"}
          </h1>

          <p className="mt-3 text-sm text-slate-500">
            {activeSectionTitle?.description || (
              <>
                Cómputos trazables calculados por el backend
                Python a partir de los PDF cargados.
              </>
            )}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button className="inline-flex min-h-11 items-center rounded-lg border border-slate-300 bg-white px-4 text-xs font-bold text-ink" type="button" onClick={onBack}>Volver a análisis</button>
          <button
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-xs font-bold text-ink transition hover:-translate-y-px hover:border-accent hover:text-accent-dark"
            type="button"
            onClick={downloadCurrentResults}
          >
            <Icon
              name="arrowUp"
              size={17}
            />
            Descargar JSON
          </button>

          <button
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-accent bg-accent px-4 text-xs font-bold text-white shadow-[0_8px_18px_rgba(36,183,166,.18)] transition hover:-translate-y-px hover:bg-accent-dark"
            type="button"
            onClick={onNewAnalysis}
          >
            Nuevo análisis

            <Icon
              name="plus"
              size={17}
            />
          </button>
        </div>
      </div>

      {/* RESUMEN DEL ANÁLISIS */}

      {activeStructure === null && (
        <>
      <div
        className={`mt-7 flex flex-col justify-between gap-4 rounded-2xl border px-4 py-4 sm:flex-row sm:items-center ${
          hasAnalysisAlerts
            ? errorAlertCount > 0
              ? "border-red-200 bg-red-50"
              : "border-amber-200 bg-amber-50"
            : "border-emerald-200 bg-emerald-50"
        }`}
      >
        <div className="flex items-start gap-3">
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-sm font-black shadow-sm ${
              hasAnalysisAlerts
                ? errorAlertCount > 0
                  ? "text-red-600"
                  : "text-amber-600"
                : "text-emerald-600"
            }`}
          >
            {hasAnalysisAlerts ? (
              <span aria-hidden="true">!</span>
            ) : (
              <Icon
                name="check"
                size={17}
              />
            )}
          </span>

          <div>
            <strong
              className={`block text-xs font-extrabold ${
                hasAnalysisAlerts
                  ? errorAlertCount > 0
                    ? "text-red-900"
                    : "text-amber-900"
                  : "text-emerald-900"
              }`}
            >
              {resultStatusTitle}
            </strong>

            <span
              className={`mt-0.5 block text-[11px] leading-5 ${
                hasAnalysisAlerts
                  ? errorAlertCount > 0
                    ? "text-red-800/80"
                    : "text-amber-800/80"
                  : "text-emerald-800/75"
              }`}
            >
              {resultStatusParts.join(" ")}
            </span>
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
          {engineeringReviews.length > 0 && (
            <span className="rounded-full border border-emerald-200 bg-white px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-emerald-700">
              {engineeringReviews.length}{" "}
              {engineeringReviews.length === 1
                ? "decisión registrada"
                : "decisiones registradas"}
            </span>
          )}

          {previousResolvedCount > 0 && (
            <span className="rounded-full border border-emerald-200 bg-white px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-emerald-700">
              {previousResolvedCount} {previousResolvedCount === 1 ? "corrección previa aplicada" : "correcciones previas aplicadas"}
            </span>
          )}

          {hasAnalysisAlerts && (
            <span className="rounded-full border border-amber-200 bg-white px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-amber-700">
              {analysisAlerts.length} alertas
            </span>
          )}

          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-slate-600">
            {formatNumber(
              results.cantidad_documentos
            )}{" "}
            documentos
          </span>

          <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[9px] font-extrabold uppercase tracking-wider text-slate-600">
            {formatNumber(
              results.confianza_lectura_porcentaje,
              "%"
            )}{" "}
            confianza
          </span>
        </div>
      </div>

      <PreviousReviewStatus audit={previousTechnicalAudit} />

      <AnalysisAlerts
        alerts={groupedAnalysisAlerts.inconsistencia}
        title="Inconsistencias nuevas del cómputo"
        description="Son contradicciones detectadas durante el cálculo. No corresponden a correcciones documentales que ya habían sido cerradas."
        onReviewAlert={openEngineeringReview}
      />

      <AnalysisAlerts
        alerts={groupedAnalysisAlerts.dato_requerido}
        title="Datos requeridos para completar cantidades"
        description="El cálculo disponible ya fue realizado; estas cantidades permanecen pendientes hasta ingresar o confirmar los datos indicados."
        onReviewAlert={openEngineeringReview}
      />

      <AnalysisAlerts
        alerts={groupedAnalysisAlerts.revision_tecnica}
        title="Validaciones técnicas pendientes"
        description="Son asociaciones o interpretaciones que el profesional debe revisar antes de aprobar la familia afectada."
        onReviewAlert={openEngineeringReview}
      />

      <AnalysisAlerts
        alerts={groupedAnalysisAlerts.observacion}
        title="Observaciones de lectura"
        description="Son advertencias de trazabilidad; se muestran separadas de las inconsistencias y de los datos faltantes."
        onReviewAlert={openEngineeringReview}
      />

      {/* FAMILIAS ESTRUCTURALES */}

      <section className="mt-9">
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">
            Resumen por familia estructural
          </div>

          <h2 className="mt-1 font-display text-2xl font-bold tracking-tight text-ink">
            ¿Qué querés revisar?
          </h2>

          <p className="mt-1 text-xs text-slate-400">
            Seleccioná una tarjeta para ver solamente sus
            cantidades y elementos.
          </p>
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-2 2xl:grid-cols-4">
          <StructureCard
            active={activeStructure === "fundaciones"}
            code="F"
            title="Fundaciones"
            description={foundationSteelAvailable
              ? "Cómputo completo de bases, armaduras y ubicación en planta."
              : "Geometría revisada por ocurrencia; acero pendiente."}
            mainValue={formatNumber(
              results.cantidad_fundaciones
            )}
            mainLabel="elementos detectados"
            status={`${formatNumber(
              results.cantidad_tipos
            )} tipos`}
            alertCount={
              (alertsByFamily.fundaciones || []).length
            }
            tone="foundation"
            stats={[
              {
                label: "Hormigón",
                value: formatNumber(
                  results.volumen_hormigon_m3,
                  "m³"
                ),
              },
              {
                label: "Encofrado",
                value: formatNumber(
                  results.encofrado_zapatas_m2,
                  "m²"
                ),
              },
              {
                label: "Acero",
                value: formatNumber(
                  results.peso_acero_kg,
                  "kg"
                ),
              },
            ]}
            onClick={() =>
              openStructure("fundaciones")
            }
          />

          <StructureCard
            active={activeStructure === "pedestales"}
            code="P"
            title="Pedestales"
            description="Apoyos directos con acero propio o heredado de su columna asociada."
            mainValue={formatNumber(
              results.cantidad_pedestales ??
                pedestalValidation.cantidad_pedestales_computados
            )}
            mainLabel={
              pedestalHeightsValidated
                ? "pedestales validados"
                : "pedestales preliminares"
            }
            status={
              pedestalHeightsValidated &&
              pedestalSteelComplete &&
              pedestalSteelConfirmed
                ? "Completo"
                : pedestalSteelAvailable
                  ? pedestalSteelComplete
                    ? "Preliminar"
                    : "Acero parcial"
                  : "Revisar"
            }
            alertCount={
              (alertsByFamily.pedestales || []).length
            }
            tone="pedestal"
            stats={[
              {
                label: "Hormigón",
                value: formatNumber(
                  results.hormigon_pedestales_m3,
                  "m³"
                ),
              },
              {
                label: "Acero",
                value: pedestalSteelAvailable
                  ? formatNumber(
                      results.acero_pedestales_kg,
                      "kg"
                    )
                  : "Pendiente",
              },
              {
                label: "Encofrado",
                value: formatNumber(
                  results.encofrado_pedestales_m2,
                  "m²"
                ),
              },
            ]}
            onClick={() =>
              openStructure("pedestales")
            }
          />

          <StructureCard
            active={activeStructure === "vigas"}
            code="VR"
            title="Vigas de riostra"
            description="Cada tramo reconstruido entre dos apoyos consecutivos."
            mainValue={formatNumber(
              beamValidation.tramos_computados ??
                beamSegments.length
            )}
            mainLabel="tramos computados"
            status={
              beamValidation.resultado_completo &&
              beamSteelComplete
                ? "Completo"
                : beamSteelAvailable
                  ? "Acero parcial"
                  : "Revisar"
            }
            alertCount={
              (alertsByFamily.vigas || []).length
            }
            tone="beam"
            stats={[
              {
                label: "Hormigón",
                value: formatNumber(
                  results.hormigon_vigas_riostra_m3,
                  "m³"
                ),
              },
              {
                label: "Acero",
                value: beamSteelAvailable
                  ? formatNumber(
                      results.acero_vigas_riostra_kg,
                      "kg"
                    )
                  : "Pendiente",
              },
              {
                label: "Encofrado",
                value: formatNumber(
                  results.encofrado_vigas_riostra_m2,
                  "m²"
                ),
              },
            ]}
            onClick={() =>
              openStructure("vigas")
            }
          />

          <StructureCard
            active={activeStructure === "columnas"}
            code="C"
            title="Columnas"
            description="Secciones reales y vínculos detectados con fundaciones y vigas."
            mainValue={formatNumber(
              columnValidation.rotulos_columnas_detectados ??
                directColumns.length + linkedColumns.length
            )}
            mainLabel="rótulos detectados"
            status={
              columnHeightsValidated && columnSteelAvailable
                ? "Completo"
                : columnHeightsValidated
                  ? "Geometría validada"
                : "Geometría lista"
            }
            alertCount={
              (alertsByFamily.columnas || []).length
            }
            tone="column"
            stats={[
              {
                label: "Hormigón",
                value: columnHeightsValidated
                  ? formatNumber(
                      results.hormigon_columnas_m3,
                      "m³"
                    )
                  : "Pendiente",
              },
              {
                label: "Acero",
                value: columnSteelAvailable
                  ? formatNumber(
                      results.acero_columnas_kg,
                      "kg"
                    )
                  : "Pendiente",
              },
              {
                label: "Encofrado",
                value: columnHeightsValidated
                  ? formatNumber(
                      results.encofrado_columnas_m2,
                      "m²"
                    )
                  : "Pendiente",
              },
            ]}
            onClick={() =>
              openStructure("columnas")
            }
          />
        </div>
      </section>
        </>
      )}

      {/* DETALLE DE LA FAMILIA SELECCIONADA */}

      {activeStructure !== null && (
        <>
      <button
        className="mt-8 inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-xs font-extrabold text-slate-600 shadow-sm transition hover:-translate-y-px hover:border-accent hover:text-accent-dark"
        type="button"
        onClick={returnToSummary}
      >
        <span aria-hidden="true">←</span>
        Volver al resumen
      </button>

      <section className="mt-6 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_20px_50px_rgba(16,34,53,.07)]">
        <div className="flex flex-col justify-between gap-4 border-b border-slate-100 p-5 sm:p-7 lg:flex-row lg:items-center">
          <div>
            <div className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">
              {activeSectionTitle.eyebrow}
            </div>

            <h2 className="mt-1 font-display text-xl font-bold tracking-tight text-ink sm:text-2xl">
              {activeSectionTitle.title}
            </h2>

            <p className="mt-1 text-[11px] text-slate-400">
              {activeSectionTitle.description}
            </p>
          </div>

          <DetailTabs
            tabs={activeTabs}
            activeTab={detailTab}
            onChange={setDetailTab}
          />
        </div>

        <div className="space-y-4 border-b border-slate-100 bg-slate-50/60 p-5 sm:p-7">
          <AnalysisAlerts
            alerts={activeAlerts}
            title={`Pendientes de ${
              activeSectionTitle.title.toLowerCase()
            }`}
            description="Aquí se distinguen inconsistencias, datos requeridos, validaciones técnicas y observaciones de esta familia."
            onReviewAlert={openEngineeringReview}
          />

          {activeEngineeringReviews.length > 0 && (
            <EngineeringReviews
              items={activeEngineeringReviews}
            />
          )}

          <FamilyStatusBanner
            tone={activeStatus.tone}
            title={activeStatus.title}
            description={activeStatus.description}
          />

          <MaterialSummary
            materials={activeMaterials}
          />
        </div>

        <div role="tabpanel">
          {activeStructure === "fundaciones" &&
            detailTab === "hormigon" && (
              <HormigonDetail
                items={foundations}
                totalGeneral={
                  results.volumen_hormigon_m3
                }
              />
            )}

          {activeStructure === "fundaciones" &&
            detailTab === "encofrado" && (
              <EncofradoDetail
                items={formwork}
                totalGeneral={
                  results.encofrado_zapatas_m2
                }
              />
            )}

          {activeStructure === "fundaciones" &&
            detailTab === "acero" && (
              <ArmadurasDetail
                items={reinforcements}
                totalGeneral={
                  results.peso_acero_kg
                }
              />
            )}

          {activeStructure === "fundaciones" &&
            detailTab === "ubicaciones" && (
              <UbicacionesDetail
                locations={locations}
                foundations={foundations}
                formwork={formwork}
                reinforcements={reinforcements}
                validation={locationValidation}
              />
            )}

          {activeStructure === "vigas" && (
            <VigasRiostraDetail
              items={beamSegments}
              summary={beamSummary}
              steelSummary={beamSteelSummary}
              validation={beamValidation}
              steelValidation={beamSteelValidation}
              view={detailTab}
              totals={{
                lengthBetweenAxes:
                  results.longitud_total_entre_ejes_vigas_riostra_m,
                clearLength:
                  results.longitud_total_libre_vigas_riostra_m,
                concrete:
                  results.hormigon_vigas_riostra_m3,
                formwork:
                  results.encofrado_vigas_riostra_m2,
              }}
            />
          )}

          {activeStructure === "pedestales" && (
            <PedestalesDetail
              items={pedestalItems}
              validation={pedestalValidation}
              view={detailTab}
            />
          )}

          {activeStructure === "columnas" && (
            <ColumnasDetail
              directItems={directColumns}
              linkedItems={linkedColumns}
              validation={columnValidation}
              view={detailTab}
            />
          )}
        </div>
      </section>
        </>
      )}

      {/* CORRECCIONES DE FUNDACIONES */}

      {activeStructure === "fundaciones" &&
        corrections.length > 0 && (
        <section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <h3 className="text-xs font-extrabold text-amber-900">
            Correcciones auditadas aplicadas
          </h3>

          <ul className="mt-3 space-y-2">
            {corrections.map(
              (correction) => (
                <li
                  key={`${correction.numero_fila}-${correction.referencia_correcta}`}
                  className="text-[11px] leading-5 text-amber-800"
                >
                  Fila{" "}
                  {correction.numero_fila}:{" "}
                  {
                    correction.referencia_original
                  }{" "}
                  →{" "}
                  {
                    correction.referencia_correcta
                  }
                  . {correction.motivo}
                </li>
              )
            )}
          </ul>
        </section>
      )}

      {reviewDialog && (
        <EngineeringReviewDialog
          key={reviewDialog.alert.id}
          alert={reviewDialog.alert}
          results={results}
          segment={reviewDialog.segment}
          saving={savingReview}
          error={reviewError}
          onClose={closeEngineeringReview}
          onConfirm={confirmEngineeringReview}
        />
      )}
    </main>
  );
}

export default Results;
