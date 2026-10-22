import test from "node:test";
import assert from "node:assert/strict";
import { selectFoundationPlanRows } from "../src/utils/model3dSource.js";

const planta = (id, x) => ({
  identificador: id, referencia: "F1", posicion: { x, y: 12 },
  dimensiones_m: { x: 1.5, y: 1.5, h: 0.4 },
});

test("sin resultado ni planta no usa las 13 filas de un cuadro como 3D", () => {
  const detalle = Array.from({ length: 13 }, (_, i) => ({ referencia: `F${i + 1}`, cantidad: 1 }));
  assert.deepEqual(selectFoundationPlanRows(null), []);
  assert.deepEqual(selectFoundationPlanRows({ fundaciones_planta: [], fundaciones: detalle }), []);
  assert.deepEqual(selectFoundationPlanRows({ encofrado_zapatas_detalle: detalle }), []);
  assert.deepEqual(selectFoundationPlanRows({ tipologia_fundacion: "cimientos_corridos", cimientos_corridos_detalle: detalle }), []);
});

test("usa únicamente las ocurrencias de la planta del proyecto vigente", () => {
  const detalle = Array.from({ length: 13 }, (_, i) => ({ referencia: `F${i + 1}` }));
  const uno = { fundaciones_planta: [planta("F1-01", 40), planta("F1-02", 90)], fundaciones: detalle };
  const otro = { fundaciones_planta: [planta("Z3-01", 25)], fundaciones: detalle };
  assert.deepEqual(selectFoundationPlanRows(uno).map((f) => f.identificador), ["F1-01", "F1-02"]);
  assert.deepEqual(selectFoundationPlanRows(otro).map((f) => f.identificador), ["Z3-01"]);
});

test("acepta ubicaciones verificadas sin convertir un detalle por tipo en ocurrencias", () => {
  assert.equal(selectFoundationPlanRows({ fundaciones_planta: [], ubicaciones_fundaciones: [planta("C1", 8)] }).length, 1);
  assert.deepEqual(selectFoundationPlanRows({ fundaciones: [planta("F1-01", 8), { referencia: "F2", cantidad: 9 }] }).map((r) => r.identificador), ["F1-01"]);
});
