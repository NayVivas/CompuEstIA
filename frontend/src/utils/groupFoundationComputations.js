// La revisión geométrica devuelve una fila por ubicación. Los resultados del
// motor tabular ya llegan por tipo; ambos formatos se presentan de la misma
// manera sin alterar los datos originales ni perder identificadores.

const numeric = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
};

const referenceOf = (item) => String(item.referencia || "").trim().toUpperCase();
const occurrence = (item) => Boolean(item?.identificador) && numeric(item.cantidad) === 1;
const dimensionsOf = (item) => [numeric(item.x), numeric(item.y), numeric(item.h)];

function sortByReference(items) {
  return items.sort((left, right) =>
    referenceOf(left).localeCompare(referenceOf(right), "es", { numeric: true })
  );
}

export function groupFoundationComputations(items = []) {
  const groups = new Map();
  const display = [];

  for (const item of items) {
    const dimensions = dimensionsOf(item);
    const unit = numeric(item.volumen_unitario);
    const total = numeric(item.volumen_total);
    if (!occurrence(item) || !referenceOf(item) || dimensions.some((value) => value === null) ||
        unit === null || total === null) {
      display.push(item);
      continue;
    }

    // Dos elementos del mismo tipo con medidas diferentes nunca se fusionan.
    const key = JSON.stringify([referenceOf(item), ...dimensions, unit]);
    if (!groups.has(key)) {
      const group = { ...item, cantidad: 0, volumen_total: 0, elementos: [] };
      groups.set(key, group);
      display.push(group);
    }
    const group = groups.get(key);
    group.cantidad += 1;
    group.volumen_total += total;
    group.elementos.push({ identificador: item.identificador, volumen_m3: total });
  }

  return sortByReference(display);
}

export function groupFormworkComputations(items = [], foundations = []) {
  const foundationById = new Map(
    foundations.filter((item) => item.identificador).map((item) => [item.identificador, item])
  );
  const groups = new Map();
  const display = [];

  for (const item of items) {
    const foundation = foundationById.get(item.identificador);
    const dimensions = foundation ? dimensionsOf(foundation) : [];
    const unit = numeric(item.encofrado_unitario_m2 ?? item.area_unitaria_m2);
    const total = numeric(item.encofrado_total_m2 ?? item.area_total_m2);
    if (!occurrence(item) || !referenceOf(item) || dimensions.length !== 3 ||
        dimensions.some((value) => value === null) || unit === null || total === null ||
        referenceOf(foundation) !== referenceOf(item)) {
      display.push(item);
      continue;
    }

    const [x, y, h] = dimensions;
    const key = JSON.stringify([referenceOf(item), x, y, h, unit]);
    if (!groups.has(key)) {
      const caras = [
        ["X1", x], ["X2", x], ["Y1", y], ["Y2", y],
      ].map(([cara, largo_m]) => ({
        cara, largo_m, alto_m: h, sustitucion: `${largo_m} × ${h}`,
        area_m2: largo_m * h, incluida_en_computo: true,
      }));
      const group = {
        referencia: item.referencia,
        cantidad: 0,
        dimensiones_m: { x, y, h },
        criterio: { descripcion: "Cuatro caras laterales de la zapata." },
        formula: {
          expresion: "2 × (X + Y) × h",
          sustitucion: `2 × (${x} + ${y}) × ${h}`,
          resultado_m2: 2 * (x + y) * h,
        },
        caras,
        area_unitaria_m2: unit,
        area_total_m2: 0,
        elementos: [],
      };
      groups.set(key, group);
      display.push(group);
    }
    const group = groups.get(key);
    group.cantidad += 1;
    group.area_total_m2 += total;
    group.elementos.push({
      identificador: item.identificador,
      area_encofrado_esperada_m2: total,
      ubicacion_confirmada: true,
    });
  }

  for (const group of groups.values()) {
    const formulaMatches = Math.abs(group.formula.resultado_m2 - group.area_unitaria_m2) < 0.00001;
    const totalMatches = Math.abs(group.area_total_m2 - group.cantidad * group.area_unitaria_m2) <
      Math.max(0.00001, group.cantidad * 0.000001);
    group.comprobaciones = {
      formula_coincide_con_caras: formulaMatches,
      elementos_coinciden_con_total: totalMatches,
      estado: formulaMatches && totalMatches ? "verificado" : "inconsistente",
    };
  }

  return sortByReference(display);
}
