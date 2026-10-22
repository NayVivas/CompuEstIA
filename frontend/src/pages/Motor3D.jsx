import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { MOUSE, TOUCH, Vector3 } from "three";
import {
  Edges,
  GizmoHelper,
  GizmoViewport,
  Grid,
  Html,
  Instance,
  Instances,
  OrbitControls,
} from "@react-three/drei";

import Icon from "../components/Icon";
import { selectFoundationPlanRows } from "../utils/model3dSource.js";
import ContinuousFoundation3D from "./ContinuousFoundation3D";
import { getPdf } from "../services/documentReviewStorage";

const PALETTE = [
  "#38bdf8",
  "#22d3ee",
  "#818cf8",
  "#a78bfa",
  "#f472b6",
  "#fb7185",
  "#fb923c",
  "#facc15",
  "#4ade80",
  "#2dd4bf",
];

const COLUMN_VISUAL_HEIGHT_M = 1.2;
const PEDESTAL_VISUAL_HEIGHT_M = 0.6;
const BEAM_VISUAL_WIDTH_M = 0.25;
const BEAM_VISUAL_HEIGHT_M = 0.4;

const STATUS_PRESENTATION = {
  validated: {
    label: "Validado",
    color: "#22c55e",
  },
  review: {
    label: "Requiere revisión",
    color: "#f59e0b",
  },
  conflict: {
    label: "Inconsistencia",
    color: "#ef4444",
  },
  incomplete: {
    label: "Dato incompleto",
    color: "#94a3b8",
  },
};

function firstDefined(...values) {
  return (
    values.find(
      (value) =>
        value !== undefined &&
        value !== null &&
        value !== ""
    ) ?? null
  );
}

function parseNumber(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (value === null || value === undefined) {
    return null;
  }

  const match = String(value)
    .replace(",", ".")
    .match(/-?\d+(?:\.\d+)?/);

  return match ? Number(match[0]) : null;
}

function diameterInchesToMillimeters(value) {
  const normalized = String(value || "")
    .replaceAll("\"", "")
    .replace(",", ".")
    .replaceAll(" ", "")
    .trim();

  if (!normalized) {
    return null;
  }

  const fraction = normalized.match(
    /^(\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?)$/
  );
  const inches = fraction
    ? Number(fraction[1]) / Number(fraction[2])
    : Number(normalized);

  return Number.isFinite(inches) && inches > 0
    ? inches * 25.4
    : null;
}

function normalizeReference(value) {
  return String(value || "")
    .trim()
    .toUpperCase();
}

function normalizeReinforcementLevel(value) {
  const level = normalizeReference(value);

  if (level.includes("SUP")) {
    return "SUPERIOR";
  }

  if (level.includes("INF")) {
    return "INFERIOR";
  }

  return level || "INFERIOR";
}

function inferTechnicalStatus(source, complete = true) {
  const state = String(
    firstDefined(
      source?.estado,
      source?.estado_extraccion,
      source?.estado_validacion,
      source?.tipo_resultado,
      ""
    )
  ).toLowerCase();

  if (
    source?.tiene_inconsistencia === true ||
    state.includes("conflic") ||
    state.includes("inconsisten") ||
    state.includes("error")
  ) {
    return "conflict";
  }

  if (
    source?.requiere_revision === true ||
    source?.requiere_revision_geometrica === true ||
    source?.requiere_revision_asociacion === true ||
    state.includes("pendiente") ||
    state.includes("revis")
  ) {
    return "review";
  }

  if (!complete) {
    return "incomplete";
  }

  return "validated";
}

function extractEvidence(source) {
  const page = parseNumber(
    firstDefined(
      source?.pagina_origen,
      source?.pagina_fuente,
      source?.pagina_seccion,
      source?.pagina_documento,
      source?.pagina_planta,
      source?.pagina,
      source?.page
    )
  );

  return {
    page,
    documentName: firstDefined(
      source?.documento_origen,
      source?.nombre_documento,
      source?.archivo_origen,
      source?.origen_seccion,
      source?.origen
    ),
    documentSha: firstDefined(
      source?.sha256_documento,
      source?.documento_sha256,
      source?.sha256
    ),
    box: firstDefined(
      source?.posicion_rotulo_pdf,
      source?.posicion_rotulo_columna_pdf,
      source?.caja_pdf
    ),
  };
}

function resolveEvidenceLocation(results, evidence) {
  const routing = results?.enrutamiento_documentos || {};
  const roleSource =
    routing?.fuentes_por_rol?.[evidence?.role];
  const localPage = Number(evidence?.page);
  const routedSource =
    (roleSource?.fuentes || [roleSource]).filter(Boolean)[
      Math.max(0, localPage - 1)
    ];

  const page = Number(
    routedSource?.pagina ?? evidence?.page
  );

  return {
    page: Number.isFinite(page) && page > 0 ? page : null,
    documentId: routedSource?.documento_id,
    documentSha:
      routedSource?.sha256 ?? evidence?.documentSha,
    documentName:
      routedSource?.archivo ?? evidence?.documentName,
  };
}

function toMeters(value, fallback) {
  const number = parseNumber(value);

  if (number === null) {
    return fallback;
  }

  return Math.abs(number) > 10
    ? number / 100
    : number;
}

function readDimension(
  row,
  directKeys,
  nestedKeys,
  arrayIndex,
  fallback
) {
  const dimensions =
  row?.dimensiones_m ??
  row?.dimensiones ??
  row?.dimension ??
  row?.tamanio ??
  row?.tamano;

  let nestedValues = [];

  if (Array.isArray(dimensions)) {
    nestedValues = [dimensions[arrayIndex]];
  } else if (typeof dimensions === "string") {
    nestedValues = [
      dimensions.split(/[x×]/i)[arrayIndex],
    ];
  } else if (
    dimensions &&
    typeof dimensions === "object"
  ) {
    nestedValues = nestedKeys.flatMap((key) => [
      dimensions[key],
      dimensions[key.toUpperCase()],
    ]);
  }

  const rawValue = firstDefined(
    ...directKeys.map((key) => row?.[key]),
    ...nestedValues
  );

  return toMeters(rawValue, fallback);
}

function colorForType(type, index) {
  const number = String(type).match(/\d+/);
  const paletteIndex = number
    ? Number(number[0]) - 1
    : index;

  return PALETTE[
    Math.abs(paletteIndex) % PALETTE.length
  ];
}

function buildSupportAssignments(results) {
  const columns = readResultArray(
    results,
    "columnas_fundaciones"
  );
  const supports = readResultArray(
    results,
    "apoyos_columnas_vigas"
  );
  const assignments = new Map();
  const consumedSupports = new Set();

  columns.forEach((column, columnIndex) => {
    const foundationId = String(
      column?.fundacion_id || ""
    ).trim();
    const reference = normalizeReference(
      firstDefined(
        column?.referencia_columna,
        column?.referencia
      )
    );

    if (!foundationId || !reference) {
      return;
    }

    const labelPoint = readPdfPoint(
      column?.posicion_rotulo_columna_pdf
    );
    const columnPage = parseNumber(column?.pagina);
    const candidates = supports
      .map((support, supportIndex) => ({
        support,
        supportIndex,
      }))
      .filter(({ support, supportIndex }) => {
        if (consumedSupports.has(supportIndex)) {
          return false;
        }

        if (
          normalizeReference(support?.referencia) !==
          reference
        ) {
          return false;
        }

        const supportPage = parseNumber(support?.pagina);
        return (
          columnPage === null ||
          supportPage === null ||
          columnPage === supportPage
        );
      })
      .map((candidate) => {
        const supportLabel = readPdfPoint({
          x: firstDefined(
            candidate.support?.centro_rotulo_x,
            candidate.support?.centro_x
          ),
          y: firstDefined(
            candidate.support?.centro_rotulo_y,
            candidate.support?.centro_y
          ),
        });

        return {
          ...candidate,
          distance:
            labelPoint && supportLabel
              ? pointDistance(labelPoint, supportLabel)
              : candidate.supportIndex,
        };
      })
      .sort(
        (first, second) =>
          first.distance - second.distance
      );

    const selected = candidates[0];
    const sourceX = parseNumber(
      selected?.support?.centro_x
    );
    const sourceZ = parseNumber(
      selected?.support?.centro_y
    );

    if (
      !selected ||
      sourceX === null ||
      sourceZ === null
    ) {
      return;
    }

    consumedSupports.add(selected.supportIndex);
    const current = assignments.get(foundationId) || [];
    current.push({
      columnIndex,
      reference,
      sourceX,
      sourceZ,
      supportId: firstDefined(
        selected.support?.apoyo_id,
        `${reference}-${selected.supportIndex + 1}`
      ),
      method:
        "centro_vectorial_apoyo_asociado_al_rotulo_columna",
    });
    assignments.set(foundationId, current);
  });

  return assignments;
}

function extractRows(results) {
  if (!results || typeof results !== "object") {
    return [];
  }

  const rows = selectFoundationPlanRows(results);

  if (!rows.length) return [];

  const supportAssignments = buildSupportAssignments(results);

  return rows.map((row) => {
    const foundationId = String(
      firstDefined(
        row?.identificador,
        row?.foundation_id,
        row?.id
      ) || ""
    ).trim();
    const supports =
      supportAssignments.get(foundationId) || [];

    if (!supports.length) {
      return row;
    }

    const sourceX =
      supports.reduce(
        (total, support) => total + support.sourceX,
        0
      ) / supports.length;
    const sourceZ =
      supports.reduce(
        (total, support) => total + support.sourceZ,
        0
      ) / supports.length;

    return {
      ...row,
      posicion_rotulo_fundacion_pdf: firstDefined(
        row?.posicion,
        row?.centro,
        row?.coordenadas
      ),
      posicion: {
        x: sourceX,
        y: sourceZ,
      },
      posicion_estructural_confirmada: true,
      metodo_posicion_3d:
        "centro_vectorial_de_apoyo",
      apoyos_vectoriales_3d: supports.map(
        (support) => support.supportId
      ),
    };
  });
}

function buildColumnsByFoundation(results) {
  const directRows = readResultArray(
    results,
    "columnas_fundaciones"
  );
  const computedRows = readResultArray(
    results,
    "columnas_computo_detalle"
  );
  const consumedComputedRows = new Set();
  const supportAssignments = buildSupportAssignments(results);
  const supportUseCounter = new Map();

  const mergedRows = directRows.map((row) => {
    const foundationId = normalizeReference(
      row?.fundacion_id
    );
    const reference = normalizeReference(
      firstDefined(
        row?.referencia_columna,
        row?.referencia
      )
    );
    const supportKey = `${foundationId}|${reference}`;
    const matchingSupports = (
      supportAssignments.get(foundationId) || []
    ).filter(
      (support) => support.reference === reference
    );
    const supportIndex =
      supportUseCounter.get(supportKey) || 0;
    const structuralSupport =
      matchingSupports[supportIndex] || null;

    if (structuralSupport) {
      supportUseCounter.set(
        supportKey,
        supportIndex + 1
      );
    }
    const computedIndex = computedRows.findIndex(
      (candidate, index) =>
        !consumedComputedRows.has(index) &&
        normalizeReference(candidate?.fundacion_id) ===
          foundationId &&
        normalizeReference(
          firstDefined(
            candidate?.referencia_columna,
            candidate?.referencia
          )
        ) === reference
    );

    if (computedIndex < 0) {
      return {
        ...row,
        structuralSupport3d: structuralSupport,
      };
    }

    consumedComputedRows.add(computedIndex);
    return {
      ...computedRows[computedIndex],
      ...row,
      ancho_m: firstDefined(
        row?.ancho_m,
        computedRows[computedIndex]?.ancho_m
      ),
      largo_m: firstDefined(
        row?.largo_m,
        computedRows[computedIndex]?.largo_m
      ),
      altura_m: firstDefined(
        row?.altura_m,
        computedRows[computedIndex]?.altura_m
      ),
      structuralSupport3d: structuralSupport,
    };
  });

  computedRows.forEach((row, index) => {
    if (!consumedComputedRows.has(index)) {
      mergedRows.push(row);
    }
  });

  const columnsByFoundation = new Map();

  mergedRows.forEach((row, rowIndex) => {
    const foundationId = String(
      row?.fundacion_id || ""
    ).trim();

    if (!foundationId) {
      return;
    }

    const reference = normalizeReference(
      firstDefined(
        row?.referencia_columna,
        row?.referencia
      )
    );
    const structuralSupport =
      row?.structuralSupport3d || null;
    const width = toMeters(
      firstDefined(
        row?.ancho_m,
        row?.dimension_columna_1_m
      ),
      null
    );
    const depth = toMeters(
      firstDefined(
        row?.largo_m,
        row?.dimension_columna_2_m
      ),
      null
    );
    const realHeight = toMeters(
      firstDefined(
        row?.altura_real_m,
        row?.altura_m
      ),
      null
    );
    const currentColumns =
      columnsByFoundation.get(foundationId) || [];

    currentColumns.push({
      id: String(
        firstDefined(
          row?.columna_id,
          [
            foundationId,
            reference || "columna",
            row?.indice_columna_en_fundacion ??
              rowIndex + 1,
          ].join("-")
        )
      ),
      reference: reference || "—",
      width,
      depth,
      realHeight,
      displayHeight:
        realHeight ?? COLUMN_VISUAL_HEIGHT_M,
      hasRealSection:
        width !== null &&
        width > 0 &&
        depth !== null &&
        depth > 0,
      hasRealHeight:
        realHeight !== null && realHeight > 0,
      sourceX: parseNumber(
        firstDefined(
          structuralSupport?.sourceX,
          row?.posicion_rotulo_columna_pdf?.x,
          row?.posicion_pdf?.x
        )
      ),
      sourceZ: parseNumber(
        firstDefined(
          structuralSupport?.sourceZ,
          row?.posicion_rotulo_columna_pdf?.y,
          row?.posicion_pdf?.y
        )
      ),
      index:
        parseNumber(
          row?.indice_columna_en_fundacion
        ) ?? currentColumns.length + 1,
      count:
        parseNumber(
          row?.cantidad_columnas_en_fundacion
        ) ?? 1,
      associationType: row?.tipo_asociacion,
      requiresReview:
        row?.requiere_revision_asociacion === true,
      technicalStatus: inferTechnicalStatus(
        row,
        width !== null &&
          width > 0 &&
          depth !== null &&
          depth > 0 &&
          realHeight !== null &&
          realHeight > 0
      ),
      evidence: {
        ...extractEvidence(row),
        role: "planta",
      },
      source: firstDefined(
        row?.origen_seccion,
        row?.origen
      ),
      state: row?.estado,
      method: row?.metodo_asociacion,
      supportId: structuralSupport?.supportId,
      positionMethod:
        structuralSupport?.method ||
        "centro_del_rotulo_de_columna",
      distancePdf: parseNumber(
        row?.distancia_entre_rotulos_pdf
      ),
      distanceToPrimaryPdf: parseNumber(
        row?.distancia_a_columna_principal_pdf
      ),
    });

    currentColumns.sort(
      (first, second) => first.index - second.index
    );
    columnsByFoundation.set(
      foundationId,
      currentColumns
    );
  });

  return columnsByFoundation;
}

function buildPedestalsByColumnReference(results) {
  return readResultArray(
    results,
    "pedestales_computo_detalle"
  ).reduce((groups, row, index) => {
    const reference = normalizeReference(
      firstDefined(
        row?.referencia_columna,
        row?.referencia
      )
    );

    if (!reference) {
      return groups;
    }

    const width = toMeters(
      row?.dimension_pedestal_1_m,
      null
    );
    const depth = toMeters(
      row?.dimension_pedestal_2_m,
      null
    );
    const realHeight = toMeters(
      row?.altura_real_m,
      null
    );
    const preliminaryHeight = toMeters(
      firstDefined(
        row?.altura_m,
        row?.altura_minima_m
      ),
      null
    );
    const displayHeight =
      realHeight ??
      preliminaryHeight ??
      PEDESTAL_VISUAL_HEIGHT_M;

    groups.set(reference, {
      ...row,
      id: `pedestal-${reference}-${index + 1}`,
      reference,
      width,
      depth,
      realHeight,
      preliminaryHeight,
      displayHeight,
      hasRealHeight:
        realHeight !== null && realHeight > 0,
      hasRealSection:
        width !== null &&
        width > 0 &&
        depth !== null &&
        depth > 0,
      technicalStatus: realHeight
        ? inferTechnicalStatus(row, true)
        : "review",
      evidence: {
        ...extractEvidence(row),
        role: "detalles",
      },
    });

    return groups;
  }, new Map());
}

function buildColumnReinforcementByReference(results) {
  const globallyConfirmed = [
    results?.validacion_columnas,
    results?.resultado?.validacion_columnas,
    results?.data?.validacion_columnas,
    results?.data?.resultado?.validacion_columnas,
  ].some(
    (validation) =>
      validation?.armaduras_columnas_confirmadas === true
  );

  return readResultArray(
    results,
    "armaduras_columnas"
  ).reduce((groups, row, index) => {
    const reference = normalizeReference(
      firstDefined(
        row?.referencia,
        row?.referencia_columna,
        row?.referencia_original
      )
    );

    if (!reference) {
      return groups;
    }

    const longitudinalGroups = Array.isArray(
      row?.grupos_longitudinales
    )
      ? row.grupos_longitudinales.filter(
          (group) =>
            parseNumber(group?.cantidad) > 0 &&
            diameterInchesToMillimeters(
              group?.diametro_pulgadas
            )
        )
      : [];
    const state = normalizeReference(row?.estado);
    const professionallyConfirmed =
      globallyConfirmed ||
      row?.confirmada_profesional === true ||
      row?.validado_profesional === true ||
      row?.confirmado_por_ingeniero === true ||
      state.includes("CONFIRMAD") ||
      state.includes("VALIDAD");
    const hasConflict =
      row?.conflicto_entre_fuentes === true ||
      state.includes("REVISAR") ||
      state.includes("CONFLICT");
    const hasLongitudinalBars = longitudinalGroups.length > 0;
    const usableForPedestalFallback =
      hasLongitudinalBars &&
      (!hasConflict || professionallyConfirmed) &&
      (state === "CORRECTO" || professionallyConfirmed);
    const technicalStatus =
      hasConflict && !professionallyConfirmed
        ? "conflict"
        : professionallyConfirmed
          ? "validated"
          : hasLongitudinalBars
            ? "review"
            : "incomplete";
    const candidate = {
      ...row,
      id: `armadura-columna-${reference}-${index + 1}`,
      reference,
      grupos_longitudinales: longitudinalGroups,
      hasLongitudinalBars,
      professionallyConfirmed,
      hasConflict,
      usableForPedestalFallback,
      technicalStatus,
      evidence: {
        ...extractEvidence(row),
        role: "detalles",
      },
    };
    const current = groups.get(reference);
    const candidatePriority =
      (professionallyConfirmed ? 4 : 0) +
      (state === "CORRECTO" ? 2 : 0) +
      (hasLongitudinalBars ? 1 : 0);
    const currentPriority = current
      ? (current.professionallyConfirmed ? 4 : 0) +
        (normalizeReference(current?.estado) === "CORRECTO"
          ? 2
          : 0) +
        (current.hasLongitudinalBars ? 1 : 0)
      : -1;

    if (!current || candidatePriority > currentPriority) {
      groups.set(reference, candidate);
    }

    return groups;
  }, new Map());
}

function buildReinforcementByType(results) {
  const rows = Array.isArray(results?.armaduras)
    ? results.armaduras
    : [];

  return rows.reduce((groups, row, index) => {
    const reference = String(
      firstDefined(
        row?.referencia,
        row?.tipo_fundacion,
        row?.fundacion
      ) || ""
    ).trim();

    if (!reference) {
      return groups;
    }

    const current = groups.get(reference) || [];
    current.push({
      ...row,
      nivel: normalizeReinforcementLevel(row?.nivel),
      direccion: normalizeReference(row?.direccion),
      id: `${reference}-${normalizeReinforcementLevel(row?.nivel)}-${normalizeReference(row?.direccion) || "D"}-${index}`,
      technicalStatus: inferTechnicalStatus(
        row,
        parseNumber(row?.cantidad_barras) > 0 &&
          parseNumber(row?.longitud_barra_m) > 0 &&
          parseNumber(row?.diametro_mm) > 0
      ),
      evidence: {
        ...extractEvidence(row),
        role: "detalles",
      },
    });
    groups.set(reference, current);
    return groups;
  }, new Map());
}

function RebarSegment({
  position,
  rotation = [0, 0, 0],
  length,
  radius,
  color,
  selected,
}) {
  return (
    <mesh
      position={position}
      rotation={rotation}
      renderOrder={20}
    >
      <cylinderGeometry
        args={[radius, radius, length, 10]}
      />
      <meshStandardMaterial
        color={selected ? "#f8fafc" : color}
        roughness={0.32}
        metalness={0.72}
        depthWrite={false}
        emissive={selected ? color : "#000000"}
        emissiveIntensity={selected ? 0.45 : 0.08}
      />
    </mesh>
  );
}

function InstancedRebarSegments({
  segments,
  color,
  selected,
}) {
  if (!segments.length) {
    return null;
  }

  return (
    <Instances
      limit={segments.length}
      range={segments.length}
      renderOrder={20}
    >
      <cylinderGeometry args={[1, 1, 1, 10]} />
      <meshStandardMaterial
        color={selected ? "#f8fafc" : color}
        roughness={0.32}
        metalness={0.72}
        depthWrite={false}
        emissive={selected ? color : "#000000"}
        emissiveIntensity={selected ? 0.45 : 0.08}
      />
      {segments.map((segment) => (
        <Instance
          key={segment.id}
          position={segment.position}
          rotation={segment.rotation || [0, 0, 0]}
          scale={[
            segment.radius,
            segment.length,
            segment.radius,
          ]}
        />
      ))}
    </Instances>
  );
}

function rectangularBarPositions(
  count,
  halfWidth,
  halfDepth
) {
  if (count <= 1) {
    return [[0, 0]];
  }

  const corners = [
    [-halfWidth, -halfDepth],
    [halfWidth, -halfDepth],
    [halfWidth, halfDepth],
    [-halfWidth, halfDepth],
  ];

  if (count === 2) {
    return [corners[0], corners[2]];
  }

  if (count <= 4) {
    return corners.slice(0, count);
  }

  const width = halfWidth * 2;
  const depth = halfDepth * 2;
  const perimeter = 2 * (width + depth);
  const remaining = count - 4;
  const edgeLengths = [width, depth, width, depth];
  const exactAllocations = edgeLengths.map(
    (length) => (remaining * length) / perimeter
  );
  const allocations = exactAllocations.map(Math.floor);

  while (
    allocations.reduce((total, value) => total + value, 0) <
    remaining
  ) {
    const nextEdge = exactAllocations
      .map((value, index) => ({
        index,
        remainder: value - allocations[index],
      }))
      .sort(
        (first, second) =>
          second.remainder - first.remainder ||
          first.index - second.index
      )[0].index;
    allocations[nextEdge] += 1;
  }

  const positions = [...corners];
  allocations.forEach((quantity, edgeIndex) => {
    const start = corners[edgeIndex];
    const end = corners[(edgeIndex + 1) % corners.length];

    for (let index = 1; index <= quantity; index += 1) {
      const ratio = index / (quantity + 1);
      positions.push([
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio,
      ]);
    }
  });

  return positions;
}

function VerticalReinforcementCage({
  reinforcement,
  sectionWidth,
  sectionDepth,
  height,
  position,
  selected,
  onSelect,
  available = true,
  coverMaximum = 0.04,
  longitudinalColor = "#a78bfa",
  stirrupColor = "#c4b5fd",
  explicitStirrupCount = null,
}) {
  const groups = Array.isArray(
    reinforcement?.grupos_longitudinales
  )
    ? reinforcement.grupos_longitudinales
    : [];
  const bars = groups.flatMap((group, groupIndex) => {
    const quantity = Math.max(
      0,
      Math.round(parseNumber(group?.cantidad) || 0)
    );
    const diameterMm = diameterInchesToMillimeters(
      group?.diametro_pulgadas
    );

    if (!quantity || !diameterMm) {
      return [];
    }

    return Array.from({ length: quantity }, (_, index) => ({
      id: `${groupIndex}-${group.diametro_pulgadas}-${index}`,
      diameterMm,
    }));
  });
  const stirrup = reinforcement?.estribo;
  const stirrupDiameterMm = diameterInchesToMillimeters(
    stirrup?.diametro_pulgadas
  );
  const cover = Math.min(
    coverMaximum,
    sectionWidth * 0.18,
    sectionDepth * 0.18
  );
  const halfWidth = Math.max(
    0.015,
    sectionWidth / 2 - cover
  );
  const halfDepth = Math.max(
    0.015,
    sectionDepth / 2 - cover
  );
  const cageHeight = Math.max(0.05, height - 0.04);
  const spacing = parseNumber(stirrup?.separacion_m);
  const calculatedStirrups = Math.max(
    0,
    Math.round(
      parseNumber(explicitStirrupCount) ||
        (spacing
          ? Math.ceil(height / spacing) + 1
          : 0)
    )
  );
  const stirrupCount = Math.min(calculatedStirrups, 120);
  const barPositions = rectangularBarPositions(
    bars.length,
    halfWidth,
    halfDepth
  );

  if (
    !available ||
    !bars.length ||
    !Number.isFinite(sectionWidth) ||
    sectionWidth <= 0 ||
    !Number.isFinite(sectionDepth) ||
    sectionDepth <= 0 ||
    !Number.isFinite(height) ||
    height <= 0
  ) {
    return null;
  }

  const longitudinalSegments = bars.map((bar, index) => {
    const [x, z] = barPositions[index];
    return {
      id: `longitudinal-${bar.id}-${index}`,
      position: [x, height / 2, z],
      length: cageHeight,
      radius: Math.max(0.004, bar.diameterMm / 2000),
    };
  });
  const stirrupSegments = [];

  if (stirrupDiameterMm && stirrupCount > 0) {
    const radius = Math.max(
      0.0035,
      stirrupDiameterMm / 2000
    );

    for (let index = 0; index < stirrupCount; index += 1) {
      const y =
        stirrupCount === 1
          ? height / 2
          : 0.02 +
            (index * (height - 0.04)) /
              (stirrupCount - 1);

      stirrupSegments.push(
        {
          id: `stirrup-${index}-front`,
          position: [0, y, -halfDepth],
          rotation: [0, 0, Math.PI / 2],
          length: halfWidth * 2,
          radius,
        },
        {
          id: `stirrup-${index}-back`,
          position: [0, y, halfDepth],
          rotation: [0, 0, Math.PI / 2],
          length: halfWidth * 2,
          radius,
        },
        {
          id: `stirrup-${index}-left`,
          position: [-halfWidth, y, 0],
          rotation: [Math.PI / 2, 0, 0],
          length: halfDepth * 2,
          radius,
        },
        {
          id: `stirrup-${index}-right`,
          position: [halfWidth, y, 0],
          rotation: [Math.PI / 2, 0, 0],
          length: halfDepth * 2,
          radius,
        }
      );
    }
  }

  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation();
        onSelect?.();
      }}
    >
      <InstancedRebarSegments
        segments={longitudinalSegments}
        color={longitudinalColor}
        selected={selected}
      />
      <InstancedRebarSegments
        segments={stirrupSegments}
        color={stirrupColor}
        selected={selected}
      />
    </group>
  );
}

function PedestalReinforcementMesh({
  pedestal,
  reinforcement,
  reinforcementOrigin,
  reinforcementAvailable,
  position,
  selected,
  onSelect,
}) {
  const appliedReinforcement =
    reinforcement || pedestal?.armadura_pedestal;
  const inherited =
    reinforcementOrigin === "heredada_de_columna" ||
    pedestal?.origen_armadura_pedestal ===
      "heredada_de_columna";
  const hasConflict =
    appliedReinforcement?.technicalStatus === "conflict" ||
    appliedReinforcement?.hasConflict === true;
  const longitudinalColor = hasConflict
    ? "#ef4444"
    : inherited
      ? "#fb923c"
      : "#22d3ee";
  const stirrupColor = hasConflict
    ? "#fb7185"
    : inherited
      ? "#facc15"
      : "#67e8f9";

  return (
    <VerticalReinforcementCage
      reinforcement={appliedReinforcement}
      sectionWidth={pedestal?.width}
      sectionDepth={pedestal?.depth}
      height={pedestal?.displayHeight}
      position={position}
      selected={selected}
      onSelect={onSelect}
      available={
        reinforcementAvailable ??
        pedestal?.acero_disponible === true
      }
      coverMaximum={0.05}
      longitudinalColor={longitudinalColor}
      stirrupColor={stirrupColor}
      explicitStirrupCount={
        pedestal?.cantidad_estribos_unitario
      }
    />
  );
}

function ColumnReinforcementMesh({
  column,
  reinforcement,
  position,
  selected,
  onSelect,
}) {
  const colors =
    reinforcement?.technicalStatus === "conflict"
      ? {
          longitudinal: "#ef4444",
          stirrup: "#fb7185",
        }
      : reinforcement?.technicalStatus === "validated"
        ? {
            longitudinal: "#8b5cf6",
            stirrup: "#c4b5fd",
          }
        : {
            longitudinal: "#f59e0b",
            stirrup: "#facc15",
          };

  return (
    <VerticalReinforcementCage
      reinforcement={reinforcement}
      sectionWidth={column?.width}
      sectionDepth={column?.depth}
      height={column?.displayHeight}
      position={position}
      selected={selected}
      onSelect={onSelect}
      available={reinforcement?.hasLongitudinalBars === true}
      coverMaximum={0.04}
      longitudinalColor={colors.longitudinal}
      stirrupColor={colors.stirrup}
    />
  );
}

function ReinforcementMesh({
  foundation,
  rows = [],
  selectedElement,
  onSelectElement,
  showLowerReinforcement,
  showUpperReinforcement,
}) {
  if (!rows.length) {
    return null;
  }

  const layers = rows.flatMap((row, rowIndex) => {
    const direction = String(row?.direccion || "").toUpperCase();
    const level = normalizeReinforcementLevel(row?.nivel);
    if (!["X", "Y"].includes(direction)) {
      return [];
    }

    const upper = level === "SUPERIOR";

    if (
      (upper && !showUpperReinforcement) ||
      (!upper && !showLowerReinforcement)
    ) {
      return [];
    }

    const positions = Math.max(
      1,
      Math.round(parseNumber(row?.cantidad_posiciones) || 1)
    );
    const barsPerPosition = Math.max(
      1,
      Math.round(parseNumber(row?.cantidad_indicada) || 1)
    );
    const diameterMm = Math.max(
      6,
      parseNumber(row?.diametro_mm) || 10
    );
    const radius = Math.max(0.004, diameterMm / 2000);
    const distributionDimension =
      direction === "X"
        ? foundation.depth
        : foundation.width;
    const mainDimension =
      direction === "X"
        ? foundation.width
        : foundation.depth;
    const available = Math.min(
      distributionDimension,
      Math.max(
        0,
        parseNumber(row?.longitud_disponible_m) ??
          distributionDimension - 0.15
      )
    );
    const cover = Math.max(
      0.01,
      (distributionDimension - available) / 2
    );
    const mainLength = Math.max(
      0.05,
      mainDimension - 2 * cover
    );
    const totalBarLength =
      parseNumber(row?.longitud_barra_m) ?? mainLength;
    const bendLength = Math.max(
      0,
      (totalBarLength - mainLength) / 2
    );
    const spacing =
      positions > 1
        ? parseNumber(row?.separacion_real_m) ??
          available / (positions - 1)
        : 0;
    const layerOffset = direction === "X" ? radius : -radius;
    const y = upper
      ? foundation.height - cover + layerOffset
      : cover + layerOffset;
    const hookSign = upper ? -1 : 1;
    const color = upper ? "#f472b6" : "#38bdf8";
    const bundleOffset = Math.max(radius * 2.4, 0.012);

    const bars = [];
    for (let positionIndex = 0; positionIndex < positions; positionIndex += 1) {
      const distributionPosition =
        positions === 1
          ? 0
          : -available / 2 + spacing * positionIndex;

      for (let bundleIndex = 0; bundleIndex < barsPerPosition; bundleIndex += 1) {
        const bundleShift =
          (bundleIndex - (barsPerPosition - 1) / 2) *
          bundleOffset;
        bars.push({
          id: `${row.id}-${positionIndex}-${bundleIndex}`,
          direction,
          distributionPosition,
          bundleShift,
          y,
          radius,
          mainLength,
          bendLength,
          hookSign,
          color,
        });
      }
    }

    return [{
      row,
      rowIndex,
      bars,
      color,
    }];
  });

  return (
    <group>
      {layers.map(({ row, bars }) => {
        const selected =
          selectedElement?.kind === "reinforcement" &&
          selectedElement?.id === row.id;

        return (
          <group
            key={row.id}
            onClick={(event) => {
              event.stopPropagation();
              onSelectElement({
                kind: "reinforcement",
                id: row.id,
                foundationId: foundation.id,
              });
            }}
          >
            {bars.map((bar) => {
              const alongX = bar.direction === "X";
              const mainPosition = alongX
                ? [
                    0,
                    bar.y + bar.bundleShift,
                    bar.distributionPosition,
                  ]
                : [
                    bar.distributionPosition,
                    bar.y + bar.bundleShift,
                    0,
                  ];
              const end = bar.mainLength / 2;

              return (
                <group key={bar.id}>
                  <RebarSegment
                    position={mainPosition}
                    rotation={
                      alongX
                        ? [0, 0, Math.PI / 2]
                        : [Math.PI / 2, 0, 0]
                    }
                    length={bar.mainLength}
                    radius={bar.radius}
                    color={bar.color}
                    selected={selected}
                  />

                  {bar.bendLength > 0.005
                    ? [-1, 1].map((side) => (
                        <RebarSegment
                          key={`${bar.id}-hook-${side}`}
                          position={
                            alongX
                              ? [
                                  side * end,
                                  bar.y + bar.bundleShift +
                                    bar.hookSign *
                                      bar.bendLength / 2,
                                  bar.distributionPosition,
                                ]
                              : [
                                  bar.distributionPosition,
                                  bar.y + bar.bundleShift +
                                    bar.hookSign *
                                      bar.bendLength / 2,
                                  side * end,
                                ]
                          }
                          length={bar.bendLength}
                          radius={bar.radius}
                          color={bar.color}
                          selected={selected}
                        />
                      ))
                    : null}
                </group>
              );
            })}
          </group>
        );
      })}
    </group>
  );
}

function readResultArray(results, key) {
  const candidates = [
    results?.[key],
    results?.resultado?.[key],
    results?.data?.[key],
    results?.data?.resultado?.[key],
  ];

  return candidates.find(Array.isArray) || [];
}

function readPdfPoint(value) {
  const x = parseNumber(value?.x);
  const z = parseNumber(
    firstDefined(value?.y, value?.z)
  );

  if (x === null || z === null) {
    return null;
  }

  return { x, z };
}

function pointDistance(first, second) {
  return Math.hypot(
    first.x - second.x,
    first.z - second.z
  );
}

function buildConfirmedBeamLinks(results) {
  const rows = readResultArray(
    results,
    "columnas_vinculadas_por_viga"
  );

  return rows.flatMap((row, index) => {
    if (
      row?.estado !==
      "confirmada_por_eje_vectorial"
    ) {
      return [];
    }

    const foundationId = String(
      row?.fundacion_id || ""
    ).trim();

    const axis = row?.eje_viga_pdf;

    const start = readPdfPoint({
      x: axis?.x_inicial,
      y: axis?.y_inicial,
    });

    const end = readPdfPoint({
      x: axis?.x_final,
      y: axis?.y_final,
    });

    if (!foundationId || !start || !end) {
      return [];
    }

    const directLabel = readPdfPoint(
      row?.posicion_rotulo_columna_directa_pdf
    );

    const linkedLabel = readPdfPoint(
      row?.posicion_rotulo_columna_vinculada_pdf ??
        row?.posicion_rotulo_columna_pdf
    );

    let directPoint = start;
    let linkedPoint = end;

    if (directLabel && linkedLabel) {
      const forwardScore =
        pointDistance(start, directLabel) +
        pointDistance(end, linkedLabel);

      const reverseScore =
        pointDistance(end, directLabel) +
        pointDistance(start, linkedLabel);

      if (reverseScore < forwardScore) {
        directPoint = end;
        linkedPoint = start;
      }
    }

    const columnWidth = toMeters(
      row?.ancho_m,
      null
    );

    const columnDepth = toMeters(
      row?.largo_m,
      null
    );

    const realColumnHeight = toMeters(
      row?.altura_m,
      null
    );

    const beamWidth = toMeters(
      row?.seccion_viga_m?.ancho,
      null
    );

    const beamHeight = toMeters(
      row?.seccion_viga_m?.alto,
      null
    );

    if (
      columnWidth === null ||
      columnWidth <= 0 ||
      columnDepth === null ||
      columnDepth <= 0 ||
      beamWidth === null ||
      beamWidth <= 0 ||
      beamHeight === null ||
      beamHeight <= 0
    ) {
      return [];
    }

    return [
      {
        id: [
          foundationId,
          row?.referencia_viga || "viga",
          row?.referencia_columna_vinculada ||
            row?.referencia_columna ||
            "columna",
          row?.id_eje_viga ?? index + 1,
        ].join("-"),
        foundationId,
        directReference:
          row?.referencia_columna_directa || "—",
        linkedReference:
          row?.referencia_columna_vinculada ??
          row?.referencia_columna ??
          "—",
        beamReference:
          row?.referencia_viga || "—",
        columnWidth,
        columnDepth,
        realColumnHeight,
        displayColumnHeight:
          realColumnHeight ??
          COLUMN_VISUAL_HEIGHT_M,
        beamWidth,
        beamHeight,
        directPoint,
        linkedPoint,
        beamText: row?.texto_viga,
        state: row?.estado,
        source: row?.origen_seccion,
        vectorAxisId: row?.id_eje_viga,
        requiresReview:
          row?.requiere_revision_geometrica === true,
        technicalStatus: inferTechnicalStatus(
          row,
          realColumnHeight !== null &&
            realColumnHeight > 0
        ),
        evidence: {
          ...extractEvidence(row),
          role: "planta",
        },
      },
    ];
  });
}

function medianValue(values) {
  const ordered = values
    .filter(Number.isFinite)
    .sort((first, second) => first - second);

  if (!ordered.length) {
    return null;
  }

  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2;
}

function buildPlanTransform(foundations) {
  const positioned = foundations.filter(
    (foundation) =>
      Number.isFinite(foundation.sourceX) &&
      Number.isFinite(foundation.sourceZ) &&
      Number.isFinite(foundation.planScale)
  );

  if (!positioned.length) {
    return null;
  }

  const scale = medianValue(
    positioned.map((foundation) => foundation.planScale)
  );

  if (!Number.isFinite(scale) || scale <= 0) {
    return null;
  }

  const offsetX =
    positioned.reduce(
      (total, foundation) =>
        total + foundation.x - foundation.sourceX * scale,
      0
    ) / positioned.length;
  const offsetZ =
    positioned.reduce(
      (total, foundation) =>
        total + foundation.z - foundation.sourceZ * scale,
      0
    ) / positioned.length;

  return {
    scale,
    point(source) {
      return {
        x: source.x * scale + offsetX,
        z: source.z * scale + offsetZ,
      };
    },
  };
}

function nearestFoundation(foundations, point) {
  return foundations.reduce((nearest, foundation) => {
    const distance = Math.hypot(
      foundation.x - point.x,
      foundation.z - point.z
    );

    if (!nearest || distance < nearest.distance) {
      return { foundation, distance };
    }

    return nearest;
  }, null)?.foundation;
}

function buildComputedBeamSegments(results, foundations) {
  const transform = buildPlanTransform(foundations);
  const reinforcementByReference = new Map(
    readResultArray(results, "armaduras_vigas_riostra")
      .map((row) => [
        normalizeReference(row?.referencia),
        row,
      ])
      .filter(([reference]) => Boolean(reference))
  );

  if (!transform) {
    return [];
  }

  return readResultArray(
    results,
    "vigas_riostra_computo_detalle"
  ).flatMap((row, index) => {
    const axis = firstDefined(
      row?.eje_pdf,
      row?.eje_viga_pdf
    );
    const startPdf = readPdfPoint({
      x: firstDefined(
        axis?.x_inicial,
        row?.punto_inicial_pdf?.x
      ),
      y: firstDefined(
        axis?.y_inicial,
        row?.punto_inicial_pdf?.y
      ),
    });
    const endPdf = readPdfPoint({
      x: firstDefined(
        axis?.x_final,
        row?.punto_final_pdf?.x
      ),
      y: firstDefined(
        axis?.y_final,
        row?.punto_final_pdf?.y
      ),
    });
    const beamWidth = toMeters(row?.ancho_m, null);
    const beamHeight = toMeters(row?.alto_m, null);

    if (
      !startPdf ||
      !endPdf ||
      beamWidth === null ||
      beamWidth <= 0 ||
      beamHeight === null ||
      beamHeight <= 0
    ) {
      return [];
    }

    const start = transform.point(startPdf);
    const end = transform.point(endPdf);
    const sceneLength = Math.hypot(
      end.x - start.x,
      end.z - start.z
    );

    if (!Number.isFinite(sceneLength) || sceneLength <= 0) {
      return [];
    }

    const center = {
      x: (start.x + end.x) / 2,
      z: (start.z + end.z) / 2,
    };
    const startFoundation = nearestFoundation(
      foundations,
      start
    );
    const endFoundation = nearestFoundation(
      foundations,
      end
    );
    const supportingFoundation =
      startFoundation ||
      endFoundation ||
      nearestFoundation(
      foundations,
      center
    );
    const foundationHeight = Math.max(
      startFoundation?.height || 0,
      endFoundation?.height || 0,
      supportingFoundation?.height || 0
    );
    const state = normalizeReference(row?.estado);
    const complete =
      state === "COMPUTADO" ||
      parseNumber(row?.longitud_m) !== null;
    const beamReference = normalizeReference(
      row?.referencia
    );
    const beamReinforcement =
      row?.armadura_viga ||
      reinforcementByReference.get(beamReference) ||
      null;
    const longitudinalBars = Array.isArray(
      beamReinforcement?.armadura_longitudinal
    )
      ? beamReinforcement.armadura_longitudinal.filter(
          (bar) =>
            parseNumber(bar?.cantidad) > 0 &&
            (parseNumber(bar?.diametro_mm) ||
              diameterInchesToMillimeters(
                bar?.diametro_pulgadas
              ))
        )
      : [];
    const reinforcementAvailable =
      longitudinalBars.length > 0 &&
      Boolean(beamReinforcement?.estribo);
    const steelComputed =
      normalizeReference(row?.estado_acero) ===
      "COMPUTADO";

    return [{
      id: String(
        firstDefined(
          row?.tramo_id,
          row?.identificador,
          `viga-${index + 1}`
        )
      ),
      foundationId: supportingFoundation?.id,
      foundationHeight,
      startFoundationId: startFoundation?.id,
      endFoundationId: endFoundation?.id,
      elevationMethod:
        "cara_superior_mas_alta_de_los_apoyos",
      beamReference:
        row?.referencia || "Viga",
      directReference:
        row?.referencia_apoyo_inicial || "—",
      linkedReference:
        row?.referencia_apoyo_final || "—",
      beamWidth,
      beamHeight,
      centerX: center.x,
      centerZ: center.z,
      sceneLength,
      realLength: parseNumber(
        firstDefined(
          row?.longitud_m,
          row?.longitud_entre_ejes_m
        )
      ),
      geometricLength: sceneLength,
      startSupportId: firstDefined(
        row?.apoyo_inicial_id,
        row?.referencia_apoyo_inicial_id
      ),
      endSupportId: firstDefined(
        row?.apoyo_final_id,
        row?.referencia_apoyo_final_id
      ),
      startX: start.x,
      startZ: start.z,
      endX: end.x,
      endZ: end.z,
      rotationY: -Math.atan2(
        end.z - start.z,
        end.x - start.x
      ),
      state: row?.estado,
      source: firstDefined(
        row?.origen,
        results?.archivo_planta
      ),
      requiresReview:
        row?.requiere_revision_geometrica === true ||
        !complete,
      beamReinforcement,
      reinforcementAvailable,
      reinforcementTechnicalStatus: steelComputed
        ? "validated"
        : reinforcementAvailable
          ? "review"
          : "incomplete",
      steelComputed,
      steelState: row?.estado_acero,
      stirrupCount: parseNumber(
        row?.cantidad_estribos
      ),
      steelWeightKg: parseNumber(
        row?.peso_acero_total_kg
      ),
      steelCriterion: row?.criterio_acero,
      technicalStatus: inferTechnicalStatus(
        row,
        complete
      ),
      evidence: {
        ...extractEvidence(row),
        documentName: firstDefined(
          extractEvidence(row).documentName,
          results?.archivo_planta
        ),
        role: "planta",
      },
    }];
  });
}

function beamSupportPairKey(beam) {
  const supportIds = [
    beam?.startSupportId,
    beam?.endSupportId,
  ]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .sort();

  return supportIds.length === 2
    ? supportIds.join("::")
    : null;
}

function beamSceneEndpoints(beam) {
  const direct = [
    parseNumber(beam?.startX),
    parseNumber(beam?.startZ),
    parseNumber(beam?.endX),
    parseNumber(beam?.endZ),
  ];

  if (direct.every(Number.isFinite)) {
    return {
      start: { x: direct[0], z: direct[1] },
      end: { x: direct[2], z: direct[3] },
    };
  }

  const linked = [
    parseNumber(beam?.directX),
    parseNumber(beam?.directZ),
    parseNumber(beam?.linkedX),
    parseNumber(beam?.linkedZ),
  ];

  if (linked.every(Number.isFinite)) {
    return {
      start: { x: linked[0], z: linked[1] },
      end: { x: linked[2], z: linked[3] },
    };
  }

  return null;
}

function beamsShareSceneGeometry(first, second) {
  const firstPair = beamSupportPairKey(first);
  const secondPair = beamSupportPairKey(second);

  if (firstPair && firstPair === secondPair) {
    return true;
  }

  const firstEnds = beamSceneEndpoints(first);
  const secondEnds = beamSceneEndpoints(second);

  if (!firstEnds || !secondEnds) {
    return false;
  }

  const comparedLength = Math.min(
    Number(first?.sceneLength) || Infinity,
    Number(second?.sceneLength) || Infinity
  );
  const tolerance = Math.min(
    0.18,
    Math.max(
      0.06,
      Number.isFinite(comparedLength)
        ? comparedLength * 0.02
        : 0.08
    )
  );
  const forward = Math.max(
    pointDistance(firstEnds.start, secondEnds.start),
    pointDistance(firstEnds.end, secondEnds.end)
  );
  const reverse = Math.max(
    pointDistance(firstEnds.start, secondEnds.end),
    pointDistance(firstEnds.end, secondEnds.start)
  );

  if (Math.min(forward, reverse) <= tolerance) {
    return true;
  }

  const firstVector = {
    x: firstEnds.end.x - firstEnds.start.x,
    z: firstEnds.end.z - firstEnds.start.z,
  };
  const secondVector = {
    x: secondEnds.end.x - secondEnds.start.x,
    z: secondEnds.end.z - secondEnds.start.z,
  };
  const firstLength = Math.hypot(
    firstVector.x,
    firstVector.z
  );
  const secondLength = Math.hypot(
    secondVector.x,
    secondVector.z
  );

  if (firstLength <= 0 || secondLength <= 0) {
    return false;
  }

  const direction = {
    x: firstVector.x / firstLength,
    z: firstVector.z / firstLength,
  };
  const parallelism = Math.abs(
    (firstVector.x * secondVector.x +
      firstVector.z * secondVector.z) /
      (firstLength * secondLength)
  );

  if (parallelism < Math.cos((5 * Math.PI) / 180)) {
    return false;
  }

  const relativeStart = {
    x: secondEnds.start.x - firstEnds.start.x,
    z: secondEnds.start.z - firstEnds.start.z,
  };
  const relativeEnd = {
    x: secondEnds.end.x - firstEnds.start.x,
    z: secondEnds.end.z - firstEnds.start.z,
  };
  const perpendicularStart = Math.abs(
    relativeStart.x * direction.z -
      relativeStart.z * direction.x
  );
  const perpendicularEnd = Math.abs(
    relativeEnd.x * direction.z -
      relativeEnd.z * direction.x
  );

  if (
    Math.max(perpendicularStart, perpendicularEnd) >
    Math.max(tolerance, 0.12)
  ) {
    return false;
  }

  const secondProjectionStart =
    relativeStart.x * direction.x +
    relativeStart.z * direction.z;
  const secondProjectionEnd =
    relativeEnd.x * direction.x +
    relativeEnd.z * direction.z;
  const secondMinimum = Math.min(
    secondProjectionStart,
    secondProjectionEnd
  );
  const secondMaximum = Math.max(
    secondProjectionStart,
    secondProjectionEnd
  );
  const overlap = Math.max(
    0,
    Math.min(firstLength, secondMaximum) -
      Math.max(0, secondMinimum)
  );

  return overlap / Math.min(firstLength, secondLength) >= 0.8;
}

function mergeBeamSegments(...groups) {
  const merged = [];

  groups.flat().forEach((beam) => {
    if (
      !beam ||
      merged.some((current) =>
        beamsShareSceneGeometry(current, beam)
      )
    ) {
      return;
    }

    merged.push(beam);
  });

  return merged;
}

function undirectedAngleDifference(first, second) {
  let difference = Math.abs(first - second) % Math.PI;

  if (difference > Math.PI / 2) {
    difference = Math.PI - difference;
  }

  return Math.abs(difference);
}

function buildUnreferencedBeamSegments(
  results,
  foundations,
  computed
) {
  const transform = buildPlanTransform(foundations);
  const candidates = readResultArray(
    results,
    "candidatos_vectoriales_sin_rotulo"
  );
  const supports = readResultArray(
    results,
    "apoyos_columnas_vigas"
  );

  if (!transform || !candidates.length || !supports.length) {
    return [];
  }

  const supportsByPageAndId = new Map();
  const supportsById = new Map();

  supports.forEach((support) => {
    const supportId = String(
      firstDefined(
        support?.apoyo_id,
        support?.identificador,
        support?.id
      ) || ""
    ).trim();
    const page = parseNumber(support?.pagina);

    if (!supportId) {
      return;
    }

    supportsById.set(supportId, support);
    supportsByPageAndId.set(
      `${page ?? "?"}:${supportId}`,
      support
    );
  });

  const sectionSources = [
    ...computed,
    ...readResultArray(results, "armaduras_vigas_riostra"),
    ...readResultArray(results, "rotulos_vigas_riostra_planta"),
  ];
  const fallbackWidth = medianValue(
    sectionSources.map((row) =>
      toMeters(
        firstDefined(
          row?.beamWidth,
          row?.ancho_m,
          row?.seccion_viga_m?.ancho
        ),
        null
      )
    )
  );
  const fallbackHeight = medianValue(
    sectionSources.map((row) =>
      toMeters(
        firstDefined(
          row?.beamHeight,
          row?.alto_m,
          row?.seccion_viga_m?.alto
        ),
        null
      )
    )
  );

  return candidates.flatMap((candidate, index) => {
    const vectorEvidence =
      candidate?.evidencia_vectorial || {};
    const evidenceType = String(
      vectorEvidence?.tipo || ""
    ).trim().toLowerCase();
    const evidenceConfidence = String(
      vectorEvidence?.confianza || ""
    ).trim().toLowerCase();
    const candidateState = String(
      candidate?.estado || ""
    ).trim().toLowerCase();
    const professionallyConfirmed =
      candidate?.validado_profesional === true ||
      candidate?.confirmado_por_ingeniero === true ||
      candidateState.includes("confirmado_profesional") ||
      candidateState.includes("validado_profesional");
    const hasReliableVectorGeometry =
      evidenceType === "doble_borde" &&
      evidenceConfidence === "alta";

    if (
      !professionallyConfirmed &&
      !hasReliableVectorGeometry
    ) {
      return [];
    }

    const page = parseNumber(candidate?.pagina);
    const startSupportId = String(
      candidate?.apoyo_inicial_id || ""
    ).trim();
    const endSupportId = String(
      candidate?.apoyo_final_id || ""
    ).trim();
    const startSupport =
      supportsByPageAndId.get(
        `${page ?? "?"}:${startSupportId}`
      ) || supportsById.get(startSupportId);
    const endSupport =
      supportsByPageAndId.get(
        `${page ?? "?"}:${endSupportId}`
      ) || supportsById.get(endSupportId);
    const startPdf = readPdfPoint({
      x: firstDefined(
        startSupport?.centro_x,
        startSupport?.posicion?.x
      ),
      y: firstDefined(
        startSupport?.centro_y,
        startSupport?.posicion?.y
      ),
    });
    const endPdf = readPdfPoint({
      x: firstDefined(
        endSupport?.centro_x,
        endSupport?.posicion?.x
      ),
      y: firstDefined(
        endSupport?.centro_y,
        endSupport?.posicion?.y
      ),
    });

    if (!startPdf || !endPdf) {
      return [];
    }

    const start = transform.point(startPdf);
    const end = transform.point(endPdf);
    const sceneLength = pointDistance(start, end);

    if (!Number.isFinite(sceneLength) || sceneLength <= 0) {
      return [];
    }

    const rotationY = -Math.atan2(
      end.z - start.z,
      end.x - start.x
    );
    const candidateSupportIds = new Set([
      startSupportId,
      endSupportId,
    ]);
    const collinearNeighbours = computed.filter((beam) => {
      const sharesSupport = [
        beam?.startSupportId,
        beam?.endSupportId,
      ].some((supportId) =>
        candidateSupportIds.has(String(supportId || ""))
      );

      return (
        sharesSupport &&
        undirectedAngleDifference(
          rotationY,
          beam.rotationY
        ) <=
          (12 * Math.PI) / 180
      );
    });
    const neighbourReferences = [
      ...new Set(
        collinearNeighbours
          .map((beam) => beam?.beamReference)
          .filter(Boolean)
      ),
    ];
    const suggestedReference =
      neighbourReferences.length === 1
        ? neighbourReferences[0]
        : null;
    const beamWidth =
      medianValue(
        collinearNeighbours.map((beam) => beam.beamWidth)
      ) ??
      fallbackWidth ??
      BEAM_VISUAL_WIDTH_M;
    const beamHeight =
      medianValue(
        collinearNeighbours.map((beam) => beam.beamHeight)
      ) ??
      fallbackHeight ??
      BEAM_VISUAL_HEIGHT_M;
    const center = {
      x: (start.x + end.x) / 2,
      z: (start.z + end.z) / 2,
    };
    const startFoundation = nearestFoundation(
      foundations,
      start
    );
    const endFoundation = nearestFoundation(
      foundations,
      end
    );
    const supportingFoundation =
      startFoundation ||
      endFoundation ||
      nearestFoundation(foundations, center);
    const foundationHeight = Math.max(
      startFoundation?.height || 0,
      endFoundation?.height || 0,
      supportingFoundation?.height || 0
    );
    return [{
      id: [
        "viga-sin-rotulo",
        page ?? 1,
        startSupportId || index + 1,
        endSupportId || index + 1,
      ].join("-"),
      foundationId: supportingFoundation?.id,
      foundationHeight,
      startFoundationId: startFoundation?.id,
      endFoundationId: endFoundation?.id,
      elevationMethod:
        "cara_superior_mas_alta_de_los_apoyos",
      beamReference: "SIN RÓTULO",
      suggestedReference,
      directReference:
        startSupport?.referencia || startSupportId || "—",
      linkedReference:
        endSupport?.referencia || endSupportId || "—",
      beamWidth,
      beamHeight,
      centerX: center.x,
      centerZ: center.z,
      sceneLength,
      realLength: null,
      geometricLength: sceneLength,
      rotationY,
      startSupportId,
      endSupportId,
      startX: start.x,
      startZ: start.z,
      endX: end.x,
      endZ: end.z,
      state: "sin_referencia_de_viga",
      source: results?.archivo_planta,
      requiresReview: true,
      technicalStatus: "review",
      calculationExcluded: true,
      unlabeledCandidate: true,
      visualSectionInferred: true,
      candidateConfidence:
        vectorEvidence?.confianza || "pendiente",
      candidateEvidenceType:
        vectorEvidence?.tipo || "evidencia_vectorial",
      evidence: {
        page,
        documentName: results?.archivo_planta,
        role: "planta",
      },
    }];
  });
}

function buildStructuralBeamSegments(results, foundations) {
  const computed = buildComputedBeamSegments(
    results,
    foundations
  );
  const confirmed = positionConfirmedBeamLinks(
    foundations,
    buildConfirmedBeamLinks(results)
  );
  const unreferenced = buildUnreferencedBeamSegments(
    results,
    foundations,
    computed
  );

  return mergeBeamSegments(
    computed,
    confirmed,
    unreferenced
  );
}

function positionConfirmedBeamLinks(
  foundations,
  links
) {
  const foundationsById = new Map(
    foundations.map((foundation) => [
      foundation.id,
      foundation,
    ])
  );

  return links.flatMap((link) => {
    const foundation = foundationsById.get(
      link.foundationId
    );

    if (!foundation) {
      return [];
    }

    const scale = foundation.planScale;

    if (!Number.isFinite(scale) || scale <= 0) {
      return [];
    }

    const deltaX =
      (link.linkedPoint.x -
        link.directPoint.x) *
      scale;

    const deltaZ =
      (link.linkedPoint.z -
        link.directPoint.z) *
      scale;

    const sceneLength = Math.hypot(
      deltaX,
      deltaZ
    );

    if (!Number.isFinite(sceneLength) || sceneLength <= 0) {
      return [];
    }

    const directX = foundation.x;
    const directZ = foundation.z;
    const linkedX = directX + deltaX;
    const linkedZ = directZ + deltaZ;

    return [
      {
        ...link,
        foundationHeight: foundation.height,
        directX,
        directZ,
        linkedX,
        linkedZ,
        startX: directX,
        startZ: directZ,
        endX: linkedX,
        endZ: linkedZ,
        centerX: (directX + linkedX) / 2,
        centerZ: (directZ + linkedZ) / 2,
        sceneLength,
        rotationY: -Math.atan2(
          deltaZ,
          deltaX
        ),
      },
    ];
  });
}

function normalizeRows(rows) {
  const expanded = [];
  const identifiers = new Set();

  rows.forEach((value, index) => {
    if (!value || typeof value !== "object") return;
    const type = String(firstDefined(value.tipo, value.referencia, value.codigo, "")).trim();
    if (!type) return;

    const position = firstDefined(value.posicion, value.centro, value.coordenadas);
    const hasPosition = position !== null;
    const sourceX = Array.isArray(position)
      ? parseNumber(position[0])
      : parseNumber(firstDefined(position?.x, position?.X, value.posicion_x, value.centro_x, value.coordenada_x, value.x_pdf));
    const sourceZ = Array.isArray(position)
      ? parseNumber(position[1])
      : parseNumber(firstDefined(position?.y, position?.Y, position?.z, position?.Z, value.posicion_y, value.centro_y, value.coordenada_y, value.y_pdf));
    const width = readDimension(value,
      ["ancho", "width", "lado_x", "base_x", ...(hasPosition ? [] : ["x", "X"])],
      ["x", "ancho", "width"], 0, null);
    const depth = readDimension(value,
      ["profundidad", "depth", "largo", "lado_y", ...(hasPosition ? [] : ["y", "Y"])],
      ["y", "profundidad", "depth", "largo"], 1, null);
    const height = readDimension(value,
      ["altura", "alto", "height", "h"],
      ["h", "altura", "alto", "height"], 2, null);

    // No ubicar ni dimensionar fundaciones a partir de números inventados.
    if (sourceX === null || sourceZ === null ||
        ![width, depth, height].every((size) => Number.isFinite(size) && size > 0)) return;

    const requestedId = String(firstDefined(value.identificador, value.foundation_id, value.id, `${type}-${index + 1}`));
    let id = requestedId;
    let suffix = 2;
    while (identifiers.has(id)) id = `${requestedId}-${suffix++}`;
    identifiers.add(id);
    expanded.push({
      id, label: id, type, width, depth, height,
      sourceX, sourceZ,
      color: colorForType(type, index),
      technicalStatus: inferTechnicalStatus(value, true),
      positionMethod: value.metodo_posicion_3d || "rotulo_de_planta",
      supportIds: value.apoyos_vectoriales_3d || [],
      evidence: { ...extractEvidence(value), role: "planta" },
    });
  });

  if (!expanded.length) return [];

  const centerX = expanded.reduce((sum, item) => sum + item.sourceX, 0) / expanded.length;
  const centerZ = expanded.reduce((sum, item) => sum + item.sourceZ, 0) / expanded.length;
  const spanX = Math.max(...expanded.map((item) => item.sourceX)) -
    Math.min(...expanded.map((item) => item.sourceX));
  const spanZ = Math.max(...expanded.map((item) => item.sourceZ)) -
    Math.min(...expanded.map((item) => item.sourceZ));
  const nearestDistances = expanded.flatMap((item, index) => {
    const distances = expanded
      .filter((_, other) => other !== index)
      .map((other) => Math.hypot(item.sourceX - other.sourceX, item.sourceZ - other.sourceZ))
      .filter((distance) => distance > 0);
    return distances.length ? [Math.min(...distances)] : [];
  }).sort((a, b) => a - b);
  const midpoint = Math.floor(nearestDistances.length / 2);
  const medianDistance = nearestDistances.length
    ? nearestDistances.length % 2
      ? nearestDistances[midpoint]
      : (nearestDistances[midpoint - 1] + nearestDistances[midpoint]) / 2
    : 0;
  const foundationSizes = expanded.map((item) => Math.max(item.width, item.depth)).sort((a, b) => a - b);
  const medianSize = foundationSizes[Math.floor(foundationSizes.length / 2)];
  const planSpan = Math.max(spanX, spanZ);
  const fitScale = planSpan > 24 ? 16 / planSpan : 1;
  const clearanceScale = medianDistance > 0 ? medianSize * 1.8 / medianDistance : 1;
  const sourceScale = Math.max(fitScale, clearanceScale);

  return expanded.map((item) => ({
    ...item,
    x: (item.sourceX - centerX) * sourceScale,
    z: (item.sourceZ - centerZ) * sourceScale,
    planScale: sourceScale,
  }));
}

function clamp(value, minimum, maximum) {
  return Math.min(
    maximum,
    Math.max(minimum, value)
  );
}

function structureHeightForFoundation(
  foundation,
  columnsByFoundation,
  pedestalsByReference
) {
  const columns =
    columnsByFoundation.get(foundation.id) || [];
  const maximumAboveFoundation = columns.reduce(
    (maximum, column) => {
      const pedestal = pedestalsByReference.get(
        normalizeReference(column.reference)
      );

      return Math.max(
        maximum,
        column.displayHeight +
          (pedestal?.displayHeight || 0)
      );
    },
    0
  );

  return foundation.height + maximumAboveFoundation;
}

function positionColumnsOnFoundation(
  foundation,
  columns
) {
  const renderableColumns = columns.filter(
    (column) => column.hasRealSection
  );

  if (renderableColumns.length <= 1) {
    return renderableColumns.map(
      (column) => ({
        ...column,
        localX: 0,
        localZ: 0,
      })
    );
  }

  const allHavePosition =
    renderableColumns.every(
      (column) =>
        column.sourceX !== null &&
        column.sourceZ !== null
    );

  if (!allHavePosition) {
    return renderableColumns.map(
      (column, index) => {
        const ratio =
          renderableColumns.length === 1
            ? 0
            : (
                index /
                (renderableColumns.length - 1)
              ) *
                2 -
              1;

        const limitX = Math.max(
          0,
          foundation.width / 2 -
            column.width / 2 -
            0.05
        );

        return {
          ...column,
          localX: ratio * limitX,
          localZ: 0,
        };
      }
    );
  }

  const centerX =
    renderableColumns.reduce(
      (total, column) =>
        total + column.sourceX,
      0
    ) / renderableColumns.length;

  const centerZ =
    renderableColumns.reduce(
      (total, column) =>
        total + column.sourceZ,
      0
    ) / renderableColumns.length;

  const scale =
    foundation.planScale || 0.05;

  return renderableColumns.map(
    (column) => {
      const limitX = Math.max(
        0,
        foundation.width / 2 -
          column.width / 2 -
          0.05
      );

      const limitZ = Math.max(
        0,
        foundation.depth / 2 -
          column.depth / 2 -
          0.05
      );

      return {
        ...column,

        localX: clamp(
          (column.sourceX - centerX) * scale,
          -limitX,
          limitX
        ),

        localZ: clamp(
          (column.sourceZ - centerZ) * scale,
          -limitZ,
          limitZ
        ),
      };
    }
  );
}

function FoundationMesh({
  foundation,
  columns = [],
  pedestalsByReference,
  columnReinforcementByReference,
  reinforcementRows = [],
  active,
  selected,
  onSelect,
  onFocus,
  selectedElement,
  onSelectElement,
  showConcrete,
  showReinforcement,
  showLabels,
  showColumns,
  showPedestals,
  showPedestalReinforcement,
  showColumnReinforcement,
  showLowerReinforcement,
  showUpperReinforcement,
}) {
  const [hovered, setHovered] = useState(false);
  const foundationColor =
    STATUS_PRESENTATION[
      foundation.technicalStatus || "validated"
    ].color;
  const positionedColumns =
    showColumns || showPedestals
    ? positionColumnsOnFoundation(
        foundation,
        columns
      )
    : [];
  const columnsWithPedestals = positionedColumns.map(
    (column) => ({
      ...column,
      pedestal:
        pedestalsByReference.get(
          normalizeReference(column.reference)
        ) || null,
      columnReinforcement:
        columnReinforcementByReference.get(
          normalizeReference(column.reference)
        ) || null,
    })
  );

  const maximumColumnHeight =
    columnsWithPedestals.length
      ? Math.max(
          ...columnsWithPedestals.map(
            (column) =>
              column.displayHeight +
              (column.pedestal?.displayHeight || 0)
          )
        )
      : 0;

  return (
    <group
      position={[
        foundation.x,
        0,
        foundation.z,
      ]}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(foundation.id);
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        onFocus(foundation.id);
      }}
      onPointerOver={(event) => {
        event.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={() => setHovered(false)}
    >
      <mesh
        position={[
          0,
          foundation.height / 2,
          0,
        ]}
        castShadow
        receiveShadow
      >
        <boxGeometry
          args={[
            foundation.width,
            foundation.height,
            foundation.depth,
          ]}
        />

        <meshStandardMaterial
          color={
            selected
              ? "#f8fafc"
              : hovered
                ? "#bae6fd"
              : foundationColor
          }
          roughness={0.6}
          metalness={0.12}
          emissive={
            selected
              ? "#38bdf8"
              : hovered
                ? "#0ea5e9"
              : "#000000"
          }
          emissiveIntensity={
            selected ? 0.3 : hovered ? 0.18 : 0
          }
          transparent={!showConcrete || showReinforcement}
          opacity={showConcrete ? (showReinforcement ? 0.32 : 1) : 0.1}
          depthWrite={!showReinforcement}
        />
      </mesh>

      {active && showReinforcement ? (
        <ReinforcementMesh
          foundation={foundation}
          rows={reinforcementRows}
          selectedElement={selectedElement}
          onSelectElement={onSelectElement}
          showLowerReinforcement={showLowerReinforcement}
          showUpperReinforcement={showUpperReinforcement}
        />
      ) : null}

      {showPedestals ? columnsWithPedestals.map((column) => {
        const pedestal = column.pedestal;

        if (!pedestal?.hasRealSection) {
          return null;
        }

        const pedestalId = [
          foundation.id,
          pedestal.id,
          column.id,
        ].join("-");
        const pedestalSelected =
          selectedElement?.kind === "pedestal" &&
          selectedElement?.id === pedestalId;
        const pedestalColor =
          STATUS_PRESENTATION[
            pedestal.technicalStatus || "review"
          ].color;
        const columnReinforcement =
          column.columnReinforcement;
        const fallbackReinforcement =
          !pedestal?.armadura_pedestal &&
          columnReinforcement?.hasLongitudinalBars
            ? columnReinforcement
            : null;
        const appliedReinforcement =
          pedestal?.armadura_pedestal ||
          fallbackReinforcement;
        const reinforcementAvailable =
          pedestal?.acero_disponible === true ||
          Boolean(fallbackReinforcement);
        const pedestalSteelVisible =
          showReinforcement &&
          showPedestalReinforcement &&
          reinforcementAvailable;

        return (
          <group key={pedestalId}>
            <mesh
              position={[
                column.localX,
                foundation.height +
                  pedestal.displayHeight / 2,
                column.localZ,
              ]}
              castShadow
              receiveShadow
              onClick={(event) => {
                event.stopPropagation();
                onSelectElement({
                  kind: "pedestal",
                  id: pedestalId,
                  foundationId: foundation.id,
                  reference: pedestal.reference,
                });
              }}
              onDoubleClick={(event) => {
                event.stopPropagation();
                onSelectElement({
                  kind: "pedestal",
                  id: pedestalId,
                  foundationId: foundation.id,
                  reference: pedestal.reference,
                });
                onFocus(foundation.id, true);
              }}
            >
              <boxGeometry
                args={[
                  pedestal.width,
                  pedestal.displayHeight,
                  pedestal.depth,
                ]}
              />
              <meshStandardMaterial
                color={
                  pedestalSelected
                    ? "#fde68a"
                    : pedestalColor
                }
                emissive={
                  pedestalSelected
                    ? "#d97706"
                    : "#000000"
                }
                emissiveIntensity={
                  pedestalSelected ? 0.3 : 0
                }
                roughness={0.62}
                metalness={0.05}
                transparent={pedestalSteelVisible}
                opacity={
                  pedestalSteelVisible ? 0.2 : 1
                }
                depthWrite={!pedestalSteelVisible}
              />
            </mesh>

            {pedestalSteelVisible ? (
              <PedestalReinforcementMesh
                pedestal={pedestal}
                reinforcement={appliedReinforcement}
                reinforcementOrigin={
                  fallbackReinforcement
                    ? "heredada_de_columna"
                    : pedestal?.origen_armadura_pedestal
                }
                reinforcementAvailable={
                  reinforcementAvailable
                }
                position={[
                  column.localX,
                  foundation.height,
                  column.localZ,
                ]}
                selected={pedestalSelected}
                onSelect={() =>
                  onSelectElement({
                    kind: "pedestal",
                    id: pedestalId,
                    foundationId: foundation.id,
                    reference: pedestal.reference,
                  })
                }
              />
            ) : null}
          </group>
        );
      }) : null}

      {showColumns ? columnsWithPedestals.map((column) => {
        const columnSelected =
          selectedElement?.kind === "column" &&
          selectedElement?.id === column.id;
        const columnReinforcement =
          column.columnReinforcement;
        const columnSteelVisible =
          showReinforcement &&
          showColumnReinforcement &&
          columnReinforcement?.hasLongitudinalBars === true;
        const columnBaseY =
          foundation.height +
          (column.pedestal?.displayHeight || 0);
        const columnColor =
          STATUS_PRESENTATION[
            column.technicalStatus || "incomplete"
          ].color;

        return (
          <group key={column.id}>
            <mesh
              position={[
                column.localX,
                columnBaseY + column.displayHeight / 2,
                column.localZ,
              ]}
              castShadow
              receiveShadow
              onClick={(event) => {
                event.stopPropagation();
                onSelectElement({
                  kind: "column",
                  id: column.id,
                  foundationId: foundation.id,
                });
              }}
              onDoubleClick={(event) => {
                event.stopPropagation();
                onSelectElement({
                  kind: "column",
                  id: column.id,
                  foundationId: foundation.id,
                });
                onFocus(foundation.id, true);
              }}
            >
              <boxGeometry
                args={[
                  column.width,
                  column.displayHeight,
                  column.depth,
                ]}
              />

              <meshStandardMaterial
                color={
                  columnSelected
                    ? "#67e8f9"
                    : columnColor
                }
                emissive={
                  columnSelected
                    ? "#0891b2"
                    : "#000000"
                }
                emissiveIntensity={
                  columnSelected ? 0.35 : 0
                }
                roughness={0.55}
                metalness={0.08}
                transparent={columnSteelVisible}
                opacity={columnSteelVisible ? 0.16 : 1}
                depthWrite={!columnSteelVisible}
              />
            </mesh>

            {columnSteelVisible ? (
              <ColumnReinforcementMesh
                column={column}
                reinforcement={columnReinforcement}
                position={[
                  column.localX,
                  columnBaseY,
                  column.localZ,
                ]}
                selected={columnSelected}
                onSelect={() =>
                  onSelectElement({
                    kind: "column",
                    id: column.id,
                    foundationId: foundation.id,
                  })
                }
              />
            ) : null}
          </group>
        );
      }) : null}

      {showLabels ? (
        <Html
          position={[
            0,
            foundation.height +
              maximumColumnHeight +
              0.16,
            0,
          ]}
          center
          distanceFactor={8}
          style={{ pointerEvents: "none" }}
        >
          <div
            className={`whitespace-nowrap rounded-md border px-2 py-1 text-[10px] font-bold shadow-lg ${
              active
                ? "border-cyan-300 bg-cyan-400 text-slate-950"
                : "border-white/20 bg-slate-950/85 text-white"
            }`}
          >
            {foundation.label}

            {columnsWithPedestals.length
              ? ` · ${columnsWithPedestals
                  .map(
                    (column) =>
                      column.reference
                  )
                  .join(" + ")}`
              : ""}
          </div>
        </Html>
      ) : null}
    </group>
  );
}

function BeamReinforcementMesh({
  link,
  selected,
}) {
  const reinforcement = link?.beamReinforcement;
  const groups = Array.isArray(
    reinforcement?.armadura_longitudinal
  )
    ? reinforcement.armadura_longitudinal
    : [];
  const bars = groups.flatMap((group, groupIndex) => {
    const quantity = Math.max(
      0,
      Math.round(parseNumber(group?.cantidad) || 0)
    );
    const diameterMm =
      parseNumber(group?.diametro_mm) ||
      diameterInchesToMillimeters(
        group?.diametro_pulgadas
      );

    if (!quantity || !diameterMm) {
      return [];
    }

    return Array.from({ length: quantity }, (_, index) => ({
      id: `${groupIndex}-${group.diametro_pulgadas}-${index}`,
      diameterMm,
    }));
  });
  const stirrup = reinforcement?.estribo;
  const stirrupDiameterMm =
    parseNumber(stirrup?.diametro_mm) ||
    diameterInchesToMillimeters(
      stirrup?.diametro_pulgadas
    );

  if (
    !link?.reinforcementAvailable ||
    !bars.length ||
    !Number.isFinite(link.sceneLength) ||
    link.sceneLength <= 0
  ) {
    return null;
  }

  const cover = Math.min(
    0.04,
    link.beamHeight * 0.18,
    link.beamWidth * 0.18
  );
  const halfHeight = Math.max(
    0.015,
    link.beamHeight / 2 - cover
  );
  const halfDepth = Math.max(
    0.015,
    link.beamWidth / 2 - cover
  );
  const cageLength = Math.max(
    0.05,
    link.sceneLength - 2 * Math.min(cover, 0.04)
  );
  const positions = rectangularBarPositions(
    bars.length,
    halfHeight,
    halfDepth
  );
  const longitudinalSegments = bars.map((bar, index) => ({
    id: `beam-longitudinal-${bar.id}`,
    position: [0, positions[index][0], positions[index][1]],
    rotation: [0, 0, Math.PI / 2],
    length: cageLength,
    radius: Math.max(0.004, bar.diameterMm / 2000),
  }));
  const spacing = parseNumber(stirrup?.separacion_m);
  const calculatedStirrupCount = Math.max(
    0,
    Math.round(
      parseNumber(link?.stirrupCount) ||
        (spacing
          ? Math.ceil(cageLength / spacing) + 1
          : 0)
    )
  );
  const stirrupCount = Math.min(
    calculatedStirrupCount,
    180
  );
  const stirrupSegments = [];

  if (stirrupDiameterMm && stirrupCount > 0) {
    const radius = Math.max(
      0.0035,
      stirrupDiameterMm / 2000
    );

    for (let index = 0; index < stirrupCount; index += 1) {
      const x =
        stirrupCount === 1
          ? 0
          : -cageLength / 2 +
            (index * cageLength) /
              (stirrupCount - 1);

      stirrupSegments.push(
        {
          id: `beam-stirrup-${index}-front`,
          position: [x, 0, -halfDepth],
          length: halfHeight * 2,
          radius,
        },
        {
          id: `beam-stirrup-${index}-back`,
          position: [x, 0, halfDepth],
          length: halfHeight * 2,
          radius,
        },
        {
          id: `beam-stirrup-${index}-lower`,
          position: [x, -halfHeight, 0],
          rotation: [Math.PI / 2, 0, 0],
          length: halfDepth * 2,
          radius,
        },
        {
          id: `beam-stirrup-${index}-upper`,
          position: [x, halfHeight, 0],
          rotation: [Math.PI / 2, 0, 0],
          length: halfDepth * 2,
          radius,
        }
      );
    }
  }

  const validated =
    link.reinforcementTechnicalStatus === "validated";

  return (
    <group
      position={[
        link.centerX,
        link.foundationHeight + link.beamHeight / 2,
        link.centerZ,
      ]}
      rotation={[0, link.rotationY, 0]}
    >
      <InstancedRebarSegments
        segments={longitudinalSegments}
        color={validated ? "#22d3ee" : "#f59e0b"}
        selected={selected}
      />
      <InstancedRebarSegments
        segments={stirrupSegments}
        color={validated ? "#67e8f9" : "#facc15"}
        selected={selected}
      />
    </group>
  );
}

function ConfirmedBeamLink({
  link,
  selected,
  onSelectElement,
  onFocus,
  showLabels,
  showColumns,
  showReinforcement,
  showBeamReinforcement,
}) {
  if (!showColumns) {
    return null;
  }

  const beamY =
    link.foundationHeight +
    link.beamHeight / 2;

  const hasLinkedColumn =
    Number.isFinite(link.linkedX) &&
    Number.isFinite(link.linkedZ) &&
    Number.isFinite(link.columnWidth) &&
    Number.isFinite(link.columnDepth) &&
    Number.isFinite(link.displayColumnHeight);
  const linkedColumnY = hasLinkedColumn
    ? link.foundationHeight +
      link.displayColumnHeight / 2
    : 0;
  const statusColor =
    STATUS_PRESENTATION[
      link.technicalStatus || "validated"
    ].color;
  const beamSteelVisible =
    showReinforcement &&
    showBeamReinforcement &&
    link.reinforcementAvailable;

  return (
    <group
      onClick={(event) => {
        event.stopPropagation();
        onSelectElement({
          kind: "beam",
          id: link.id,
          foundationId: link.foundationId,
        });
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        onSelectElement({
          kind: "beam",
          id: link.id,
          foundationId: link.foundationId,
        });
        if (link.foundationId) {
          onFocus(link.foundationId, true);
        }
      }}
    >
      <mesh
        position={[
          link.centerX,
          beamY,
          link.centerZ,
        ]}
        rotation={[0, link.rotationY, 0]}
        castShadow
        receiveShadow
      >
        <boxGeometry
          args={[
            link.sceneLength,
            link.beamHeight,
            link.beamWidth,
          ]}
        />

        <meshStandardMaterial
          color={
            selected
              ? "#67e8f9"
              : statusColor
          }
          emissive={selected ? "#0891b2" : "#000000"}
          emissiveIntensity={selected ? 0.35 : 0}
          roughness={0.58}
          metalness={0.06}
          transparent={beamSteelVisible}
          opacity={beamSteelVisible ? 0.18 : 1}
          depthWrite={!beamSteelVisible}
        />
        <Edges
          threshold={15}
          color={
            selected
              ? "#cffafe"
              : link.technicalStatus === "review"
                ? "#92400e"
                : link.technicalStatus === "conflict"
                  ? "#991b1b"
                  : "#166534"
          }
        />
      </mesh>

      {beamSteelVisible ? (
        <BeamReinforcementMesh
          link={link}
          selected={selected}
        />
      ) : null}

      {hasLinkedColumn ? (
        <mesh
          position={[
            link.linkedX,
            linkedColumnY,
            link.linkedZ,
          ]}
          castShadow
          receiveShadow
        >
          <boxGeometry
            args={[
              link.columnWidth,
              link.displayColumnHeight,
              link.columnDepth,
            ]}
          />

          <meshStandardMaterial
            color={
              selected
                ? "#67e8f9"
                : statusColor
            }
            roughness={0.55}
            metalness={0.08}
          />
        </mesh>
      ) : null}

      {showLabels ? (
        <Html
          position={[
            link.centerX,
            beamY + link.beamHeight / 2 + 0.16,
            link.centerZ,
          ]}
          center
          distanceFactor={8}
          style={{ pointerEvents: "none" }}
        >
          <div className="whitespace-nowrap rounded-md border border-amber-300/40 bg-slate-950/90 px-2 py-1 text-[10px] font-bold text-white shadow-lg">
            {link.beamReference}
            {link.directReference !== "—" ||
            link.linkedReference !== "—"
              ? ` · ${link.directReference}–${link.linkedReference}`
              : ""}
          </div>
        </Html>
      ) : null}
    </group>
  );
}

function CameraController({
  foundations,
  columnsByFoundation,
  pedestalsByReference,
  selectedId,
  viewCommand,
}) {
  const { camera } = useThree();
  const controlsRef = useRef(null);

  const modelFrame = useMemo(() => {
    if (!foundations.length) {
      return {
        center: new Vector3(0, 0, 0),
        span: 12,
      };
    }

    const minX = Math.min(
      ...foundations.map(
        (item) => item.x - item.width / 2
      )
    );
    const maxX = Math.max(
      ...foundations.map(
        (item) => item.x + item.width / 2
      )
    );
    const minZ = Math.min(
      ...foundations.map(
        (item) => item.z - item.depth / 2
      )
    );
    const maxZ = Math.max(
      ...foundations.map(
        (item) => item.z + item.depth / 2
      )
    );
    const maximumHeight = Math.max(
      ...foundations.map((foundation) =>
        structureHeightForFoundation(
          foundation,
          columnsByFoundation,
          pedestalsByReference
        )
      ),
      1
    );

    return {
      center: new Vector3(
        (minX + maxX) / 2,
        maximumHeight / 2,
        (minZ + maxZ) / 2
      ),
      span: Math.max(
        maxX - minX,
        maxZ - minZ,
        maximumHeight,
        4
      ),
    };
  }, [
    columnsByFoundation,
    foundations,
    pedestalsByReference,
  ]);

  useEffect(() => {
    const controls = controlsRef.current;

    if (!controls || !viewCommand) {
      return;
    }

    const selected = foundations.find(
      (item) => item.id === selectedId
    );
    const focusSelected =
      viewCommand.type === "focus" && selected;
    const selectedStructureHeight = selected
      ? structureHeightForFoundation(
          selected,
          columnsByFoundation,
          pedestalsByReference
        )
      : 0;
    const target = focusSelected
      ? new Vector3(
          selected.x,
          selectedStructureHeight / 2,
          selected.z
        )
      : modelFrame.center.clone();
    const span = focusSelected
      ? Math.max(
          selected.width,
          selected.depth,
          selectedStructureHeight,
          1
        ) * 2.25
      : modelFrame.span * 1.25;

    if (
      viewCommand.type === "zoomIn" ||
      viewCommand.type === "zoomOut"
    ) {
      const factor =
        viewCommand.type === "zoomIn" ? 0.72 : 1.38;
      const offset = camera.position
        .clone()
        .sub(controls.target)
        .multiplyScalar(factor);
      camera.position.copy(
        controls.target.clone().add(offset)
      );
      camera.updateProjectionMatrix();
      controls.update();
      return;
    }

    controls.target.copy(target);

    if (viewCommand.type === "top") {
      camera.position.set(
        target.x,
        target.y + span,
        target.z + 0.001
      );
      camera.up.set(0, 0, -1);
    } else if (viewCommand.type === "front") {
      camera.position.set(
        target.x,
        target.y + span * 0.25,
        target.z + span
      );
      camera.up.set(0, 1, 0);
    } else {
      camera.position.set(
        target.x + span * 0.78,
        target.y + span * 0.62,
        target.z + span * 0.78
      );
      camera.up.set(0, 1, 0);
    }

    camera.lookAt(target);
    camera.updateProjectionMatrix();
    controls.update();
  }, [
    camera,
    columnsByFoundation,
    foundations,
    modelFrame,
    pedestalsByReference,
    selectedId,
    viewCommand,
  ]);

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      enableDamping
      enablePan
      enableRotate
      enableZoom
      screenSpacePanning
      zoomToCursor
      dampingFactor={0.08}
      rotateSpeed={0.62}
      panSpeed={0.85}
      zoomSpeed={1.05}
      minDistance={0.45}
      maxDistance={120}
      minPolarAngle={0.01}
      maxPolarAngle={Math.PI / 2 - 0.01}
      mouseButtons={{
        LEFT: MOUSE.ROTATE,
        MIDDLE: MOUSE.DOLLY,
        RIGHT: MOUSE.PAN,
      }}
      touches={{
        ONE: TOUCH.ROTATE,
        TWO: TOUCH.DOLLY_PAN,
      }}
    />
  );
}

function ModelScene({
  foundations,
  columnsByFoundation,
  pedestalsByReference,
  columnReinforcementByReference,
  reinforcementByType,
  beamLinks,
  selectedId,
  selectedElement,
  onSelect,
  onSelectElement,
  onFocus,
  viewCommand,
  showConcrete,
  showReinforcement,
  showGrid,
  showLabels,
  showColumns,
  showPedestals,
  showPedestalReinforcement,
  showColumnReinforcement,
  showBeamReinforcement,
  showBeams,
  showLowerReinforcement,
  showUpperReinforcement,
}) {
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{
        position: [10, 8, 12],
        fov: 45,
        near: 0.05,
        far: 500,
      }}
    >
      <color
        attach="background"
        args={["#0f172a"]}
      />

      <hemisphereLight
        args={["#e2e8f0", "#0f172a", 1.5]}
      />

      <directionalLight
        position={[8, 12, 6]}
        intensity={2}
        castShadow
      />

      {showGrid ? (
        <Grid
          position={[0, -0.02, 0]}
          args={[40, 40]}
          cellSize={1}
          cellThickness={0.6}
          sectionSize={5}
          sectionThickness={1.2}
          cellColor="#1e293b"
          sectionColor="#475569"
          fadeDistance={30}
          fadeStrength={1}
          infiniteGrid
        />
      ) : null}

      <group>
          {foundations.map((foundation) => (
            <FoundationMesh
  key={foundation.id}
  foundation={foundation}
  columns={
  columnsByFoundation.get(
    foundation.id
  ) || []
}
  pedestalsByReference={pedestalsByReference}
  columnReinforcementByReference={
    columnReinforcementByReference
  }
  reinforcementRows={
    reinforcementByType.get(
      foundation.type
    ) || []
  }
  selected={
    selectedElement?.kind === "foundation" &&
    foundation.id === selectedElement?.id
  }
  active={foundation.id === selectedId}
  onSelect={onSelect}
  onFocus={onFocus}
  selectedElement={selectedElement}
  onSelectElement={onSelectElement}
  showConcrete={showConcrete}
  showReinforcement={showReinforcement}
  showLabels={showLabels}
  showColumns={showColumns}
  showPedestals={showPedestals}
  showPedestalReinforcement={
    showPedestalReinforcement
  }
  showColumnReinforcement={
    showColumnReinforcement
  }
  showLowerReinforcement={showLowerReinforcement}
  showUpperReinforcement={showUpperReinforcement}
/>
          ))}

          {showBeams ? beamLinks.map((link) => (
            <ConfirmedBeamLink
              key={link.id}
              link={link}
              selected={
                selectedElement?.kind === "beam" &&
                selectedElement?.id === link.id
              }
              onSelectElement={onSelectElement}
              onFocus={onFocus}
              showLabels={showLabels}
              showColumns={showBeams}
              showReinforcement={showReinforcement}
              showBeamReinforcement={
                showBeamReinforcement
              }
            />
          )) : null}
      </group>

      <CameraController
        foundations={foundations}
        columnsByFoundation={columnsByFoundation}
        pedestalsByReference={pedestalsByReference}
        selectedId={selectedId}
        viewCommand={viewCommand}
      />

      <GizmoHelper
        alignment="bottom-right"
        margin={[72, 72]}
      >
        <GizmoViewport
          axisColors={[
            "#fb7185",
            "#4ade80",
            "#38bdf8",
          ]}
          labelColor="#0f172a"
        />
      </GizmoHelper>
    </Canvas>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>

      <p className="mt-1 text-lg font-black text-slate-900">
        {value}
      </p>
    </div>
  );
}

function StructuralMotor3D({
  project,
  results,
  onBack,
}) {
  const sourceRows = useMemo(
    () => extractRows(results),
    [results]
  );

  const foundations = useMemo(
    () => normalizeRows(sourceRows),
    [sourceRows]
  );

  const columnsByFoundation = useMemo(
    () => buildColumnsByFoundation(results),
    [results]
  );

  const columnReinforcementByReference = useMemo(
    () => buildColumnReinforcementByReference(results),
    [results]
  );

  const reinforcementByType = useMemo(
    () => buildReinforcementByType(results),
    [results]
  );

  const pedestalsByReference = useMemo(
    () => buildPedestalsByColumnReference(results),
    [results]
  );

  const beamLinks = useMemo(
    () => buildStructuralBeamSegments(results, foundations),
    [foundations, results]
  );

  const [selectedId, setSelectedId] = useState(
    foundations[0]?.id ?? null
  );
  const [selectedElement, setSelectedElement] = useState(
    foundations[0]
      ? {
          kind: "foundation",
          id: foundations[0].id,
          foundationId: foundations[0].id,
        }
      : null
  );
  const [viewCommand, setViewCommand] = useState({
    type: "fit",
    sequence: 0,
  });

  const requestView = (type) => {
    setViewCommand((current) => ({
      type,
      sequence: current.sequence + 1,
    }));
  };

  const selectFoundation = (foundationId) => {
    setSelectedId(foundationId);
    setSelectedElement({
      kind: "foundation",
      id: foundationId,
      foundationId,
    });
  };

  const focusFoundation = (
    foundationId,
    preserveSelection = false
  ) => {
    setSelectedId(foundationId);
    if (!preserveSelection) {
      setSelectedElement({
        kind: "foundation",
        id: foundationId,
        foundationId,
      });
    }
    requestView("focus");
  };

  const selectElement = (element) => {
    if (element.foundationId) {
      setSelectedId(element.foundationId);
    }

    if (
      ["reinforcement", "pedestal", "column", "beam"].includes(
        element.kind
      )
    ) {
      setShowReinforcement(true);
    }

    if (element.kind === "pedestal") {
      setShowPedestals(true);
      setShowPedestalReinforcement(true);
    }

    if (element.kind === "column") {
      setShowColumns(true);
      setShowColumnReinforcement(true);
    }

    if (element.kind === "beam") {
      setShowBeams(true);
      setShowBeamReinforcement(true);
    }

    setSelectedElement(element);
  };

  const [showConcrete, setShowConcrete] = useState(true);
  const [showReinforcement, setShowReinforcement] = useState(true);
  const [showPedestalReinforcement, setShowPedestalReinforcement] =
    useState(true);
  const [showColumnReinforcement, setShowColumnReinforcement] =
    useState(true);
  const [showBeamReinforcement, setShowBeamReinforcement] =
    useState(true);
  const [showLowerReinforcement, setShowLowerReinforcement] =
    useState(true);
  const [showUpperReinforcement, setShowUpperReinforcement] =
    useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showColumns, setShowColumns] =
  useState(true);
  const [showPedestals, setShowPedestals] = useState(true);
  const [showBeams, setShowBeams] = useState(true);
  const [sourceError, setSourceError] = useState("");

  const selectedFoundation =
    foundations.find(
      (item) => item.id === selectedId
    ) ?? foundations[0];

    const selectedUnitVolume = selectedFoundation
  ? selectedFoundation.width *
    selectedFoundation.depth *
    selectedFoundation.height
  : 0;

const selectedColumns = selectedFoundation
  ? (
      columnsByFoundation.get(
        selectedFoundation.id
      ) || []
    )
  : [];

const selectedColumn =
  selectedElement?.kind === "column"
    ? selectedColumns.find(
        (column) => column.id === selectedElement.id
      ) || null
    : selectedColumns[0] || null;

const selectedColumnReinforcement = selectedColumn
  ? columnReinforcementByReference.get(
      normalizeReference(selectedColumn.reference)
    ) || null
  : null;

const selectedColumnReinforcementDescription = (
  selectedColumnReinforcement?.grupos_longitudinales || []
)
  .map(
    (group) =>
      `${group.cantidad} Ø ${group.diametro_pulgadas}`
  )
  .join(" + ");

const selectedColumnStirrupSpacingM = parseNumber(
  selectedColumnReinforcement?.estribo?.separacion_m
);

const selectedPedestal =
  selectedElement?.kind === "pedestal"
    ? pedestalsByReference.get(
        normalizeReference(selectedElement.reference)
      ) || null
    : null;

const selectedPedestalColumnReinforcement = selectedPedestal
  ? columnReinforcementByReference.get(
      normalizeReference(selectedPedestal.reference)
    ) || null
  : null;

const selectedPedestalUsesVisualFallback = Boolean(
  selectedPedestal &&
  !selectedPedestal?.armadura_pedestal &&
  selectedPedestalColumnReinforcement?.hasLongitudinalBars
);

const selectedPedestalFallbackHasConflict = Boolean(
  selectedPedestalUsesVisualFallback &&
  selectedPedestalColumnReinforcement?.hasConflict
);

const selectedPedestalAppliedReinforcement =
  selectedPedestal?.armadura_pedestal ||
  (selectedPedestalUsesVisualFallback
    ? selectedPedestalColumnReinforcement
    : null);

const selectedPedestalReinforcement = (
  selectedPedestalAppliedReinforcement?.grupos_longitudinales || []
)
  .map(
    (group) =>
      `${group.cantidad} Ø ${group.diametro_pulgadas}"`
  )
  .join(" + ");

const selectedPedestalUnitSteelKg = parseNumber(
  selectedPedestal?.peso_acero_unitario_kg,
  null
);

const selectedPedestalTotalSteelKg = parseNumber(
  firstDefined(
    selectedPedestal?.peso_acero_total_kg,
    selectedPedestal?.acero_kg
  ),
  null
);

const selectedBeamLinks = selectedFoundation
  ? beamLinks.filter(
      (link) =>
        link.foundationId ===
        selectedFoundation.id
    )
  : [];

const selectedBeam =
  selectedElement?.kind === "beam"
    ? selectedBeamLinks.find(
        (beam) => beam.id === selectedElement.id
      ) || null
    : null;

const selectedBeamLongitudinalReinforcement = (
  selectedBeam?.beamReinforcement
    ?.armadura_longitudinal || []
)
  .map(
    (bar) =>
      `${bar.cantidad} Ø ${bar.diametro_pulgadas}"`
  )
  .join(" + ");

const selectedBeamStirrup =
  selectedBeam?.beamReinforcement?.estribo || null;

const selectedReinforcements = selectedFoundation
  ? reinforcementByType.get(selectedFoundation.type) || []
  : [];

const selectedLowerReinforcements =
  selectedReinforcements.filter(
    (row) =>
      normalizeReinforcementLevel(row?.nivel) ===
      "INFERIOR"
  );

const selectedUpperReinforcements =
  selectedReinforcements.filter(
    (row) =>
      normalizeReinforcementLevel(row?.nivel) ===
      "SUPERIOR"
  );

const firstFoundationWithUpper = foundations.find(
  (foundation) =>
    (reinforcementByType.get(foundation.type) || []).some(
      (row) =>
        normalizeReinforcementLevel(row?.nivel) ===
        "SUPERIOR"
    )
);

const selectedReinforcement =
  selectedElement?.kind === "reinforcement"
    ? selectedReinforcements.find(
        (row) => row.id === selectedElement.id
      ) || null
    : null;

const selectedEntity =
  selectedElement?.kind === "column" && selectedColumn
    ? {
        kind: "Columna",
        title: selectedColumn.reference,
        status:
          selectedColumnReinforcement?.technicalStatus ===
          "conflict"
            ? "conflict"
            : selectedColumn.technicalStatus,
        evidence:
          selectedColumnReinforcement?.evidence ||
          selectedColumn.evidence,
        details: [
          ["Sección", selectedColumn.hasRealSection
            ? `${selectedColumn.width.toFixed(2)} × ${selectedColumn.depth.toFixed(2)} m`
            : "Sin sección validada"],
          ["Altura", selectedColumn.hasRealHeight
            ? `${selectedColumn.realHeight.toFixed(2)} m`
            : `${selectedColumn.displayHeight.toFixed(2)} m (visual; altura pendiente)`],
          [
            "Armadura longitudinal",
            selectedColumnReinforcementDescription ||
              "No detectada",
          ],
          [
            "Estribos",
            selectedColumnReinforcement?.estribo
              ? `Ø ${
                  selectedColumnReinforcement.estribo
                    .diametro_pulgadas || "—"
                }${
                  Number.isFinite(
                    selectedColumnStirrupSpacingM
                  )
                    ? ` c/${Math.round(
                        selectedColumnStirrupSpacingM * 100
                      )} cm`
                    : ""
                }`
              : "No detectados",
          ],
          [
            "Estado del acero",
            selectedColumnReinforcement?.hasConflict
              ? "Conflicto entre fuentes; jaula mostrada para revisión"
              : selectedColumnReinforcement
                  ?.professionallyConfirmed
                ? "Validado profesionalmente"
                : selectedColumnReinforcement
                    ?.hasLongitudinalBars
                  ? "Candidato detectado; requiere validación"
                  : "Sin armadura disponible",
          ],
          [
            "Origen del acero",
            selectedColumnReinforcement?.origen ||
              selectedColumnReinforcement?.fuentes_detectadas
                ?.join(", ") ||
              "—",
          ],
          ["Asociación", selectedColumn.associationType || selectedColumn.method || "—"],
          [
            "Posición 3D",
            selectedColumn.supportId
              ? `Centro vectorial ${selectedColumn.supportId}`
              : "Centro del rótulo (sin apoyo confirmado)",
          ],
        ],
      }
    : selectedElement?.kind === "pedestal" && selectedPedestal
      ? {
          kind: "Pedestal",
          title: selectedPedestal.reference,
          status: selectedPedestalFallbackHasConflict
            ? "conflict"
            : selectedPedestal.technicalStatus,
          evidence: selectedPedestal.evidence,
          details: [
            [
              "Sección",
              selectedPedestal.hasRealSection
                ? `${selectedPedestal.width.toFixed(2)} × ${selectedPedestal.depth.toFixed(2)} m`
                : "Sin sección validada",
            ],
            [
              "Altura",
              selectedPedestal.hasRealHeight
                ? `${selectedPedestal.realHeight.toFixed(2)} m`
                : `${selectedPedestal.displayHeight.toFixed(2)} m (preliminar)`,
            ],
            [
              "Resultado",
              selectedPedestal.hasRealHeight
                ? "Altura validada"
                : "Requiere validación profesional",
            ],
            [
              "Armadura",
              selectedPedestalReinforcement || "Pendiente",
            ],
            [
              "Procedencia del acero",
              selectedPedestalFallbackHasConflict
                ? "Candidata heredada de la columna con conflicto; resolver antes de computar"
                : selectedPedestalUsesVisualFallback
                  ? "Vista preliminar heredada de la columna; reprocesar para incorporarla al cómputo"
                : selectedPedestal.origen_armadura_pedestal ===
              "heredada_de_columna"
                ? "Heredada de la columna asociada"
                : selectedPedestal.origen_armadura_pedestal ===
                    "especifica_pedestal"
                  ? "Específica del pedestal"
                  : "Sin fuente válida",
            ],
            [
              "Acero unitario",
              Number.isFinite(selectedPedestalUnitSteelKg)
                ? `${selectedPedestalUnitSteelKg.toFixed(2)} kg${
                    selectedPedestal.usa_altura_minima_para_acero
                      ? " (preliminar)"
                      : ""
                  }`
                : "Pendiente",
            ],
            [
              `Subtotal del tipo (${parseNumber(
                selectedPedestal.cantidad
              ) || 0})`,
              Number.isFinite(selectedPedestalTotalSteelKg)
                ? `${selectedPedestalTotalSteelKg.toFixed(2)} kg`
                : "Pendiente",
            ],
          ],
        }
    : selectedElement?.kind === "beam" && selectedBeam
      ? {
          kind: "Viga",
          title: selectedBeam.beamReference,
          status: selectedBeam.technicalStatus,
          evidence: selectedBeam.evidence,
          details: [
            [
              selectedBeam.visualSectionInferred
                ? "Sección visual provisional"
                : "Sección",
              `${selectedBeam.beamWidth.toFixed(2)} × ${selectedBeam.beamHeight.toFixed(2)} m`,
            ],
            [
              selectedBeam.calculationExcluded
                ? "Longitud geométrica"
                : "Longitud computada",
              Number.isFinite(
                selectedBeam.calculationExcluded
                  ? selectedBeam.geometricLength
                  : selectedBeam.realLength
              )
                ? `${(
                    selectedBeam.calculationExcluded
                      ? selectedBeam.geometricLength
                      : selectedBeam.realLength
                  ).toFixed(2)} m`
                : "Pendiente",
            ],
            [
              "Apoyos",
              `${selectedBeam.directReference} – ${selectedBeam.linkedReference}`,
            ],
            [
              "Cota en el visor",
              selectedBeam.elevationMethod
                ? "Sobre el apoyo de mayor altura"
                : "Según asociación disponible",
            ],
            [
              "Armadura longitudinal",
              selectedBeamLongitudinalReinforcement ||
                "No detectada",
            ],
            [
              "Estribos",
              selectedBeamStirrup
                ? `Ø ${
                    selectedBeamStirrup
                      .diametro_pulgadas || "—"
                  }${
                    parseNumber(
                      selectedBeamStirrup.separacion_m
                    ) !== null
                      ? ` c/${Math.round(
                          parseNumber(
                            selectedBeamStirrup.separacion_m
                          ) * 100
                        )} cm`
                      : ""
                  }`
                : "No detectados",
            ],
            [
              "Estado del acero",
              selectedBeam.steelComputed
                ? "Computado y vinculado a este tramo"
                : selectedBeam.reinforcementAvailable
                  ? `Detalle detectado; ${String(
                      selectedBeam.steelState ||
                        "pendiente de cómputo"
                    )
                      .replaceAll("_", " ")
                      .toLowerCase()}`
                  : "Sin armadura disponible",
            ],
            [
              "Peso de acero del tramo",
              Number.isFinite(selectedBeam.steelWeightKg)
                ? `${selectedBeam.steelWeightKg.toFixed(2)} kg`
                : "Pendiente",
            ],
            ...(selectedBeam.calculationExcluded
              ? [[
                  "Uso en cómputo",
                  "Excluida hasta confirmar referencia y sección",
                ]]
              : []),
            ...(selectedBeam.suggestedReference
              ? [[
                  "Referencia sugerida",
                  `${selectedBeam.suggestedReference} por continuidad`,
                ]]
              : []),
          ],
        }
      : selectedElement?.kind === "reinforcement" &&
          selectedReinforcement
        ? {
            kind: "Armadura",
            title: `${selectedReinforcement.nivel || "—"} · ${selectedReinforcement.direccion || "—"}`,
            status: selectedReinforcement.technicalStatus,
            evidence: selectedReinforcement.evidence,
            details: [
              [
                "Diámetro",
                selectedReinforcement.diametro_pulgadas
                  ? `Ø ${selectedReinforcement.diametro_pulgadas}" (${parseNumber(selectedReinforcement.diametro_mm)?.toFixed(1) || "—"} mm)`
                  : "—",
              ],
              [
                "Barras",
                `${parseNumber(selectedReinforcement.cantidad_barras) || 0}`,
              ],
              [
                "Separación real",
                parseNumber(selectedReinforcement.separacion_real_m) !== null
                  ? `${(parseNumber(selectedReinforcement.separacion_real_m) * 100).toFixed(1)} cm`
                  : "—",
              ],
              [
                "Longitud por barra",
                parseNumber(selectedReinforcement.longitud_barra_m) !== null
                  ? `${parseNumber(selectedReinforcement.longitud_barra_m).toFixed(2)} m`
                  : "—",
              ],
              ["Forma representada", "Tramo recto con dos dobleces"],
              ["Radio de doblado", "No informado en los datos"],
            ],
          }
      : selectedFoundation
        ? {
            kind: "Fundación",
            title: selectedFoundation.label,
            status: selectedFoundation.technicalStatus,
            evidence: selectedFoundation.evidence,
            details: [
              ["Tipo", selectedFoundation.type],
              ["Dimensiones", `${selectedFoundation.width.toFixed(2)} × ${selectedFoundation.depth.toFixed(2)} × ${selectedFoundation.height.toFixed(2)} m`],
              ["Volumen", `${selectedUnitVolume.toFixed(3)} m³`],
              [
                "Posición 3D",
                selectedFoundation.supportIds?.length
                  ? `Apoyo ${selectedFoundation.supportIds.join(", ")}`
                  : "Centro del rótulo",
              ],
            ],
          }
        : null;

const selectedEvidenceLocation = selectedEntity
  ? resolveEvidenceLocation(
      results,
      selectedEntity.evidence
    )
  : null;

const selectedSteelPerFoundation = selectedReinforcements.reduce(
  (total, row) => total + (parseNumber(row?.peso_por_fundacion_kg) || 0),
  0
);

const selectedSteelTotal = selectedReinforcements.reduce(
  (total, row) => total + (parseNumber(row?.peso_total_kg) || 0),
  0
);

const allColumns = [
  ...columnsByFoundation.values(),
].flat();

const readyColumns = allColumns.filter(
  (column) => column.hasRealSection
).length;

const readyPedestals = allColumns.filter((column) => {
  const pedestal = pedestalsByReference.get(
    normalizeReference(column.reference)
  );
  return pedestal?.hasRealSection;
}).length;

const readyColumnReinforcements = allColumns.filter(
  (column) =>
    column.hasRealSection &&
    columnReinforcementByReference.get(
      normalizeReference(column.reference)
    )?.hasLongitudinalBars === true
).length;

const readyPedestalReinforcements = allColumns.filter(
  (column) => {
    const reference = normalizeReference(
      column.reference
    );
    const pedestal = pedestalsByReference.get(reference);
    const columnReinforcement =
      columnReinforcementByReference.get(reference);

    return Boolean(
      pedestal?.hasRealSection &&
      (
        pedestal?.acero_disponible === true ||
        (
          !pedestal?.armadura_pedestal &&
          columnReinforcement?.hasLongitudinalBars
        )
      )
    );
  }
).length;

const readyBeamReinforcements = beamLinks.filter(
  (beam) => beam.reinforcementAvailable
).length;

const computedBeamReinforcements = beamLinks.filter(
  (beam) => beam.steelComputed
).length;

const selectedTypeCount = selectedFoundation
  ? foundations.filter(
      (item) =>
        item.type === selectedFoundation.type
    ).length
  : 0;

const selectedTypeVolume =
  selectedUnitVolume * selectedTypeCount;

  const calculatedVolume = foundations.reduce(
    (total, foundation) =>
      total +
      foundation.width *
        foundation.depth *
        foundation.height,
    0
  );

  const resultVolume = parseNumber(
    firstDefined(
      results?.volumen_cimientos_corridos_m3,
      results?.volumen_hormigon_m3,
      results?.volumen_total_m3
    )
  );

  const references = foundations.length;
  const types = new Set(foundations.map((item) => item.type)).size;
  const reportedCount = parseNumber(results?.cantidad_fundaciones);
  const missingGeometry = Math.max(0, sourceRows.length - foundations.length);
  const emptySceneMessage = !results
    ? "Abrí un análisis de este proyecto para construir su modelo."
    : results?.tipologia_fundacion === "cimientos_corridos"
      ? "Hay cimientos corridos calculados, pero el resultado no contiene sus recorridos ubicados en planta. No es posible reconstruirlos en 3D desde la longitud total."
      : sourceRows.length
        ? "La planta contiene referencias, pero faltan coordenadas o dimensiones X, Y y H verificadas para dibujarlas en 3D."
        : "Este análisis no contiene ubicaciones de fundaciones extraídas de la planta. Revisá la clasificación y la extracción de ese proyecto.";

  async function openEvidence(evidence) {
    setSourceError("");
    const popup = window.open("about:blank", "_blank");

    try {
      const routing = results?.enrutamiento_documentos || {};
      const location = resolveEvidenceLocation(
        results,
        evidence
      );
      const pageNumber = location.page;

      if (!Number.isFinite(pageNumber) || pageNumber < 1) {
        throw new Error(
          "Este elemento no tiene una página de origen registrada."
        );
      }

      const documents = routing?.documentos || [];
      const normalizedName = String(
        evidence?.documentName || ""
      ).toLowerCase();
      const document = documents.find((item) => {
        if (
          location.documentId &&
          item?.documento_id === location.documentId
        ) {
          return true;
        }

        if (
          location.documentSha &&
          item?.sha256 === location.documentSha
        ) {
          return true;
        }

        if (
          evidence?.documentSha &&
          item?.sha256 === evidence.documentSha
        ) {
          return true;
        }

        if (
          normalizedName &&
          String(item?.nombre || "")
            .toLowerCase()
            .includes(normalizedName)
        ) {
          return true;
        }

        return (item?.paginas || []).some(
          (page) =>
            Number(page?.pagina) === pageNumber
        );
      });

      if (!document?.sha256) {
        throw new Error(
          `No se encontró el documento asociado a la página ${pageNumber}.`
        );
      }

      const storedPdf = await getPdf(document.sha256);
      if (!storedPdf) {
        throw new Error(
          "El PDF original no está disponible en este navegador. Volvé a cargarlo para abrir la evidencia."
        );
      }

      const url = URL.createObjectURL(storedPdf);
      if (!popup) {
        URL.revokeObjectURL(url);
        throw new Error(
          "El navegador bloqueó la nueva pestaña. Habilitá las ventanas emergentes."
        );
      }

      popup.location.href = `${url}#page=${pageNumber}`;
      setTimeout(() => URL.revokeObjectURL(url), 300000);
    } catch (openError) {
      popup?.close();
      setSourceError(
        openError.message ||
          "No se pudo abrir la evidencia del plano."
      );
    }
  }

  return (
    <main className="min-h-screen bg-mist p-4 sm:p-6">
      <div className="mx-auto max-w-[1600px]">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <button
              type="button"
              onClick={onBack}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-950 hover:text-white"
            >
              <Icon
                name="arrowRight"
                size={17}
                className="rotate-180"
              />
            </button>

            <div>
              <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-cyan-600">
                Visualización estructural
              </p>

              <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-950">
                Modelo 3D
              </h1>

              <p className="mt-1 text-sm text-slate-500">
                {project?.name || "Proyecto"}
              </p>
            </div>
          </div>

          <span className="rounded-full border border-cyan-200 bg-cyan-50 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-cyan-700">
            {foundations.length ? "Planta del análisis" : "Sin geometría de planta"}
          </span>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-950 shadow-sm">
            <div className="flex items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
              <div>
                <p className="text-sm font-bold text-white">
                  Modelo estructural 3D trazable
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  Arrastrar: rotar · Derecho: desplazar ·
                  Rueda: zoom · Doble clic: enfocar
                </p>
              </div>

              <span className="rounded-lg bg-white/10 px-2.5 py-1.5 text-[10px] font-bold text-slate-300">
                {foundations.length} fund. · {readyPedestals} ped. · {readyColumns} col. · {beamLinks.length} vigas
              </span>
            </div>

            <div
              className="relative h-[540px] min-h-[420px] cursor-grab touch-none active:cursor-grabbing"
              onContextMenu={(event) =>
                event.preventDefault()
              }
            >
              {foundations.length ? <div className="absolute left-3 top-3 z-10 flex max-w-[calc(100%-1.5rem)] flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-slate-950/85 p-2 shadow-xl backdrop-blur">
                <select
                  aria-label="Seleccionar fundación"
                  value={selectedFoundation?.id || ""}
                  onChange={(event) =>
                    focusFoundation(event.target.value)
                  }
                  className="h-9 max-w-44 rounded-lg border border-white/15 bg-slate-900 px-2 text-[11px] font-bold text-white outline-none focus:border-cyan-400"
                >
                  {foundations.map((foundation) => (
                    <option
                      key={foundation.id}
                      value={foundation.id}
                    >
                      {foundation.label}
                    </option>
                  ))}
                </select>

                {[
                  ["fit", "Encuadrar"],
                  ["focus", "Enfocar"],
                  ["isometric", "Isométrica"],
                  ["top", "Superior"],
                  ["front", "Frontal"],
                  ["zoomIn", "+"],
                  ["zoomOut", "−"],
                ].map(([type, label]) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => requestView(type)}
                    className="h-9 rounded-lg border border-white/10 bg-white/10 px-3 text-[10px] font-extrabold text-slate-100 transition hover:border-cyan-400/60 hover:bg-cyan-400/15 hover:text-cyan-200 focus:outline-none focus:ring-2 focus:ring-cyan-400"
                  >
                    {label}
                  </button>
                ))}
              </div> : null}

{foundations.length ? <ModelScene
  foundations={foundations}
  columnsByFoundation={
    columnsByFoundation
  }
  pedestalsByReference={pedestalsByReference}
  columnReinforcementByReference={
    columnReinforcementByReference
  }
  reinforcementByType={reinforcementByType}
  beamLinks={beamLinks}
  selectedId={selectedId}
  selectedElement={selectedElement}
  onSelect={selectFoundation}
  onSelectElement={selectElement}
  onFocus={focusFoundation}
  viewCommand={viewCommand}
  showConcrete={showConcrete}
  showReinforcement={showReinforcement}
  showGrid={showGrid}
  showLabels={showLabels}
  showColumns={showColumns}
  showPedestals={showPedestals}
  showPedestalReinforcement={
    showPedestalReinforcement
  }
  showColumnReinforcement={
    showColumnReinforcement
  }
  showBeamReinforcement={
    showBeamReinforcement
  }
  showBeams={showBeams}
  showLowerReinforcement={showLowerReinforcement}
  showUpperReinforcement={showUpperReinforcement}
/> : <div className="flex h-full items-center justify-center p-8 text-center text-sm leading-6 text-amber-100" role="status">
  <p className="max-w-xl">{emptySceneMessage}</p>
</div>}
            </div>

            {(missingGeometry > 0 || (reportedCount !== null && reportedCount > foundations.length)) ? (
              <p className="border-t border-amber-500/30 bg-amber-950 px-5 py-3 text-xs text-amber-100" role="status">
                Se muestran {foundations.length} fundaciones ubicadas y dimensionadas.
                {missingGeometry > 0 ? ` ${missingGeometry} ocurrencias de la planta no tienen posición o X, Y y H suficientes.` : ""}
                {reportedCount !== null && reportedCount > sourceRows.length
                  ? ` El cálculo informa ${reportedCount} fundaciones; comprobá la cobertura de la planta.` : ""}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center gap-4 border-t border-white/10 px-5 py-4">
              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showConcrete}
                  onChange={(event) => setShowConcrete(event.target.checked)}
                  className="accent-cyan-400"
                />
                Hormigón
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showReinforcement}
                  onChange={(event) => setShowReinforcement(event.target.checked)}
                  className="accent-cyan-400"
                />
                Mostrar aceros
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-sky-300">
                <input
                  type="checkbox"
                  checked={showLowerReinforcement}
                  disabled={!showReinforcement}
                  onChange={(event) =>
                    setShowLowerReinforcement(event.target.checked)
                  }
                  className="accent-sky-400 disabled:opacity-40"
                />
                Fundación inferior activa ({selectedLowerReinforcements.length})
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-pink-300">
                <input
                  type="checkbox"
                  checked={showUpperReinforcement}
                  disabled={!showReinforcement}
                  onChange={(event) =>
                    setShowUpperReinforcement(event.target.checked)
                  }
                  className="accent-pink-400 disabled:opacity-40"
                />
                Fundación superior activa ({selectedUpperReinforcements.length})
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-amber-300">
                <input
                  type="checkbox"
                  checked={showPedestalReinforcement}
                  disabled={!showReinforcement}
                  onChange={(event) =>
                    setShowPedestalReinforcement(
                      event.target.checked
                    )
                  }
                  className="accent-amber-400 disabled:opacity-40"
                />
                Acero de pedestales ({readyPedestalReinforcements})
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-violet-300">
                <input
                  type="checkbox"
                  checked={showColumnReinforcement}
                  disabled={!showReinforcement}
                  onChange={(event) =>
                    setShowColumnReinforcement(
                      event.target.checked
                    )
                  }
                  className="accent-violet-400 disabled:opacity-40"
                />
                Acero de columnas ({readyColumnReinforcements})
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-cyan-300">
                <input
                  type="checkbox"
                  checked={showBeamReinforcement}
                  disabled={!showReinforcement || !showBeams}
                  onChange={(event) =>
                    setShowBeamReinforcement(
                      event.target.checked
                    )
                  }
                  className="accent-cyan-400 disabled:opacity-40"
                />
                Acero de vigas ({readyBeamReinforcements})
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showGrid}
                  onChange={(event) =>
                    setShowGrid(event.target.checked)
                  }
                  className="accent-cyan-400"
                />
                Cuadrícula
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showLabels}
                  onChange={(event) =>
                    setShowLabels(event.target.checked)
                  }
                  className="accent-cyan-400"
                />
                Etiquetas
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showColumns}
                  onChange={(event) =>
                    setShowColumns(event.target.checked)
                  }
                  className="accent-cyan-400"
                />
               Columnas ({readyColumns})
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showPedestals}
                  onChange={(event) =>
                    setShowPedestals(event.target.checked)
                  }
                  className="accent-amber-400"
                />
                Pedestales ({readyPedestals})
              </label>

              <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showBeams}
                  onChange={(event) => setShowBeams(event.target.checked)}
                  className="accent-cyan-400"
                />
                Vigas trazadas ({beamLinks.length})
              </label>

              <div className="flex flex-wrap items-center gap-3 border-l border-white/10 pl-4 text-[10px] font-bold text-slate-400">
                {Object.entries(STATUS_PRESENTATION).map(
                  ([status, presentation]) => (
                    <span
                      key={status}
                      className="inline-flex items-center gap-1.5"
                    >
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{
                          backgroundColor: presentation.color,
                        }}
                      />
                      {presentation.label}
                    </span>
                  )
                )}
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-sky-400" />
                  Acero inferior
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-pink-400" />
                  Acero superior
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-violet-500" />
                  Acero de columna
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-orange-400" />
                  Acero heredado de pedestal
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-cyan-400" />
                  Acero de viga computado
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-0.5 w-4 bg-amber-400" />
                  Acero candidato
                </span>
              </div>
            </div>
            <div className="border-t border-white/10 bg-slate-900/70 px-5 py-3 text-[11px] leading-relaxed text-slate-400">
              Jaulas disponibles: {readyPedestalReinforcements} pedestales · {readyColumnReinforcements} columnas · {readyBeamReinforcements} vigas ({computedBeamReinforcements} computadas). Las mallas de fundación se muestran solo en la fundación activa para conservar el rendimiento del visor.
            </div>
          </section>

          <aside className="space-y-4">
            {selectedEntity ? (
              <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[9px] font-extrabold uppercase tracking-[0.16em] text-slate-400">
                      Elemento seleccionado · {selectedEntity.kind}
                    </p>
                    <h2 className="mt-1 text-lg font-black text-slate-950">
                      {selectedEntity.title}
                    </h2>
                  </div>

                  <span
                    className="rounded-full px-2.5 py-1 text-[9px] font-extrabold text-white"
                    style={{
                      backgroundColor:
                        STATUS_PRESENTATION[
                          selectedEntity.status || "incomplete"
                        ].color,
                    }}
                  >
                    {
                      STATUS_PRESENTATION[
                        selectedEntity.status || "incomplete"
                      ].label
                    }
                  </span>
                </div>

                <dl className="mt-4 grid gap-2">
                  {selectedEntity.details.map(([label, value]) => (
                    <div
                      key={label}
                      className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-[10px]"
                    >
                      <dt className="font-bold text-slate-400">
                        {label}
                      </dt>
                      <dd className="text-right font-extrabold text-slate-700">
                        {value}
                      </dd>
                    </div>
                  ))}
                </dl>

                <div className="mt-4 rounded-xl border border-slate-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                        Evidencia del plano
                      </p>
                      <p className="mt-1 text-[10px] text-slate-600">
                        {Number.isFinite(
                          selectedEvidenceLocation?.page
                        )
                          ? `Página ${selectedEvidenceLocation.page}`
                          : "Página de origen no registrada"}
                      </p>
                    </div>

                    <button
                      type="button"
                      disabled={
                        !Number.isFinite(
                          selectedEvidenceLocation?.page
                        )
                      }
                      onClick={() =>
                        openEvidence(selectedEntity.evidence)
                      }
                      className="rounded-lg bg-slate-950 px-3 py-2 text-[10px] font-extrabold text-white transition hover:bg-cyan-600 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
                    >
                      Ver plano
                    </button>
                  </div>

                  {selectedEvidenceLocation?.documentName ? (
                    <p className="mt-2 truncate text-[9px] text-slate-400">
                      {selectedEvidenceLocation.documentName}
                    </p>
                  ) : null}
                </div>

                {sourceError ? (
                  <p className="mt-3 rounded-lg bg-red-50 p-2 text-[10px] font-semibold text-red-700">
                    {sourceError}
                  </p>
                ) : null}
              </section>
            ) : null}

            <div className="grid grid-cols-2 gap-3">
              <Metric
                label="Fundaciones 3D"
                value={references}
              />

              <Metric
                label="Tipos 3D"
                value={types}
              />

              <Metric
  label="Volumen representado"
  value={foundations.length ? `${calculatedVolume.toFixed(3)} m³` : "—"}
/>

<Metric
  label="Volumen del análisis"
  value={resultVolume === null ? "—" : `${resultVolume.toFixed(3)} m³`}
/>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-slate-400">
                Elemento seleccionado
              </p>

              {selectedFoundation ? (
  <>
    <h2 className="mt-2 text-2xl font-black text-slate-950">
      {selectedFoundation.label}
    </h2>

    <div className="mt-4 space-y-2 text-sm text-slate-600">
      <div className="flex justify-between gap-3">
        <span>Tipo</span>
        <strong>
          {selectedFoundation.type}
        </strong>
      </div>

      <div className="flex justify-between gap-3">
        <span>Ancho</span>
        <strong>
          {selectedFoundation.width.toFixed(2)} m
        </strong>
      </div>

      <div className="flex justify-between gap-3">
        <span>Profundidad</span>
        <strong>
          {selectedFoundation.depth.toFixed(2)} m
        </strong>
      </div>

      <div className="flex justify-between gap-3">
        <span>Altura</span>
        <strong>
          {selectedFoundation.height.toFixed(2)} m
        </strong>
      </div>

      <div className="flex justify-between gap-3">
        <span>Volumen unitario</span>
        <strong>
          {selectedUnitVolume.toFixed(3)} m³
        </strong>
      </div>

      <div className="flex justify-between gap-3">
        <span>
          Volumen del tipo ({selectedTypeCount})
        </span>
        <strong>
          {selectedTypeVolume.toFixed(3)} m³
        </strong>
      </div>
    </div>

    <div className="mt-5 border-t border-slate-100 pt-4">
      <p className="text-[10px] font-extrabold uppercase tracking-[0.15em] text-slate-400">
        Columna asociada
      </p>

      {selectedColumn?.hasRealSection ? (
        <div className="mt-3 space-y-2 text-sm text-slate-600">
          <div className="flex justify-between gap-3">
            <span>Referencia</span>
            <strong>
              {selectedColumn.reference}
            </strong>
          </div>

          <div className="flex justify-between gap-3">
            <span>Sección real</span>
            <strong>
              {selectedColumn.width.toFixed(2)}
              {" × "}
              {selectedColumn.depth.toFixed(2)} m
            </strong>
          </div>

          <div className="flex justify-between gap-3">
            <span>Plano de origen</span>
            <strong className="text-right">
              {selectedColumn.source || "—"}
            </strong>
          </div>

          <div className="flex justify-between gap-3">
            <span>Altura real</span>
            <strong className="text-right text-amber-600">
              {selectedColumn.hasRealHeight
                ? `${selectedColumn.realHeight.toFixed(2)} m`
                : "No disponible"}
            </strong>
          </div>

          {!selectedColumn.hasRealHeight ? (
            <p className="rounded-lg bg-amber-50 p-2.5 text-[10px] leading-4 text-amber-700">
              La altura de 1,20 m utilizada en el modelo es
              solamente visual y no forma parte del cómputo.
            </p>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-xs text-amber-600">
          No existe una sección validada para esta columna.
        </p>
      )}
    </div>

    <div className="mt-5 border-t border-slate-100 pt-4">
      <p className="text-[10px] font-extrabold uppercase tracking-[0.15em] text-slate-400">
        Armadura de la fundación
      </p>

      {selectedReinforcements.length ? (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <Metric
              label="Por fundación"
              value={`${selectedSteelPerFoundation.toFixed(2)} kg`}
            />
            <Metric
              label="Total del tipo"
              value={`${selectedSteelTotal.toFixed(2)} kg`}
            />
          </div>

          <div className="flex flex-wrap gap-2 text-[10px] font-extrabold">
            <span className="rounded-full bg-sky-100 px-2.5 py-1 text-sky-700">
              Inferior: {selectedLowerReinforcements.length} direcciones
            </span>
            <span className="rounded-full bg-pink-100 px-2.5 py-1 text-pink-700">
              Superior: {selectedUpperReinforcements.length} direcciones
            </span>
          </div>

          {!selectedUpperReinforcements.length ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-[10px] leading-4 text-amber-700">
              <p>
                El resultado de {selectedFoundation.type} no contiene una
                armadura superior confirmada. El visor no la agrega porque
                hacerlo inventaría acero que no fue leído del plano.
              </p>
              {firstFoundationWithUpper ? (
                <button
                  type="button"
                  onClick={() =>
                    focusFoundation(firstFoundationWithUpper.id)
                  }
                  className="mt-2 rounded-md bg-pink-600 px-2.5 py-1.5 font-extrabold text-white transition hover:bg-pink-700"
                >
                  Ver superior en {firstFoundationWithUpper.label}
                </button>
              ) : null}
            </div>
          ) : null}

          <div className="max-h-44 space-y-2 overflow-y-auto pr-1">
            {selectedReinforcements.map((row) => {
              const upper =
                normalizeReinforcementLevel(row?.nivel) ===
                "SUPERIOR";

              return (
                <div
                  key={row.id}
                  className={`rounded-lg border p-2.5 text-[11px] ${
                    upper
                      ? "border-pink-200 bg-pink-50/80 text-pink-950"
                      : "border-sky-200 bg-sky-50/80 text-sky-950"
                  }`}
                >
                <div className="flex justify-between gap-3 font-bold">
                  <span>{row.nivel || "—"} · {row.direccion || "—"}</span>
                  <span>Ø {row.diametro_pulgadas || row.diametro_mm || "—"}</span>
                </div>
                <div className="mt-1 flex justify-between gap-3 opacity-80">
                  <span>Separación</span>
                  <strong>{row.separacion_cm ?? "—"} cm</strong>
                </div>
                <div className="mt-1 flex justify-between gap-3 opacity-80">
                  <span>Barras calculadas</span>
                  <strong>{row.cantidad_barras ?? "—"}</strong>
                </div>
              </div>
              );
            })}
          </div>

          <p className="text-[10px] leading-4 text-slate-500">
            Las barras dibujadas corresponden a las posiciones, cantidades,
            diámetros, separaciones y niveles calculados para esta fundación.
          </p>
        </div>
      ) : (
        <p className="mt-2 text-xs text-amber-600">
          No existe armadura validada para este tipo de fundación.
        </p>
      )}
    </div>

    {selectedBeamLinks.length ? (
      <div className="mt-5 border-t border-slate-100 pt-4">
        <p className="text-[10px] font-extrabold uppercase tracking-[0.15em] text-slate-400">
          Vigas asociadas a esta zona
        </p>

        <div className="mt-3 space-y-3">
          {selectedBeamLinks.map((link) => (
            <div
              key={link.id}
              className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-slate-700"
            >
              <p className="font-black text-slate-950">
                {link.directReference}
                {" — "}
                {link.beamReference}
                {" — "}
                {link.linkedReference}
              </p>

              <div className="mt-2 flex justify-between gap-3">
                <span>Sección de viga</span>
                <strong>
                  {link.beamWidth.toFixed(2)}
                  {" × "}
                  {link.beamHeight.toFixed(2)} m
                </strong>
              </div>

              {Number.isFinite(
                link.calculationExcluded
                  ? link.geometricLength
                  : link.realLength
              ) ? (
                <div className="mt-1 flex justify-between gap-3">
                  <span>
                    {link.calculationExcluded
                      ? "Longitud geométrica"
                      : "Longitud computada"}
                  </span>
                  <strong>
                    {(link.calculationExcluded
                      ? link.geometricLength
                      : link.realLength
                    ).toFixed(2)} m
                  </strong>
                </div>
              ) : null}

              {link.suggestedReference ? (
                <div className="mt-1 flex justify-between gap-3">
                  <span>Referencia sugerida</span>
                  <strong>{link.suggestedReference}</strong>
                </div>
              ) : null}

              {Number.isFinite(link.columnWidth) &&
              Number.isFinite(link.columnDepth) ? (
                <div className="mt-1 flex justify-between gap-3">
                  <span>Columna vinculada</span>
                  <strong>
                    {link.columnWidth.toFixed(2)}
                    {" × "}
                    {link.columnDepth.toFixed(2)} m
                  </strong>
                </div>
              ) : null}

              <p
                className={`mt-2 text-[10px] font-bold uppercase tracking-wide ${
                  link.calculationExcluded
                    ? "text-amber-700"
                    : "text-emerald-700"
                }`}
              >
                {link.calculationExcluded
                  ? "Candidata vectorial sin rótulo · excluida del cómputo"
                  : link.state === "computado"
                    ? "Computada por eje vectorial"
                    : "Geometría trazable del plano"}
              </p>
            </div>
          ))}
        </div>
      </div>
    ) : null}
  </>
) : (
  <p className="mt-3 text-sm text-slate-500">
    Seleccioná una fundación en el visor.
  </p>
)}
            </div>

            {foundations.length ? <div className="rounded-2xl border border-cyan-200 bg-cyan-50 p-5">
              <p className="text-sm font-bold text-cyan-950">
                Modelo estructural trazable
              </p>

              <p className="mt-2 text-xs leading-5 text-cyan-800">
                Las fundaciones, armaduras, columnas y vigas provienen
                del resultado trazable del backend. Las alturas reales
                validadas desde pórticos se representan cuando están
                disponibles. Las vigas verdes tienen referencia y sección;
                las vigas ámbar conservan evidencia vectorial del plano,
                pero siguen excluidas del cómputo hasta que el ingeniero
                confirme su referencia y sección. Al seleccionar una columna
                o un pedestal, el visor activa automáticamente su acero y
                vuelve translúcido el hormigón. Una jaula dibujada con altura
                visual sigue siendo preliminar y no habilita por sí sola el
                cómputo.
              </p>
            </div> : null}
          </aside>
        </div>
      </div>
    </main>
  );
}

export default function Motor3D(props) {
  if (props.results?.tipologia_fundacion === "cimientos_corridos") {
    return <ContinuousFoundation3D {...props} />;
  }
  return <StructuralMotor3D {...props} />;
}
