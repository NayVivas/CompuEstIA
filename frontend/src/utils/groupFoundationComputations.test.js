import { test } from "node:test";
import assert from "node:assert/strict";

import { groupFoundationComputations, groupFormworkComputations } from "./groupFoundationComputations.js";

test("resume ubicaciones iguales y mantiene las variantes del mismo tipo", () => {
  const foundations = [
    { identificador: "F2-001-p001", referencia: "F2", cantidad: 1,
      x: 1.5, y: 1.5, h: 0.3, volumen_unitario: 0.675, volumen_total: 0.675 },
    { identificador: "F2-002-p001", referencia: "F2", cantidad: 1,
      x: 1.5, y: 1.5, h: 0.3, volumen_unitario: 0.675, volumen_total: 0.675 },
    { identificador: "F2-003-p001", referencia: "F2", cantidad: 1,
      x: 1.5, y: 2, h: 0.3, volumen_unitario: 0.9, volumen_total: 0.9 },
  ];
  const formwork = [
    { identificador: "F2-001-p001", referencia: "F2", cantidad: 1,
      encofrado_unitario_m2: 1.8, encofrado_total_m2: 1.8 },
    { identificador: "F2-002-p001", referencia: "F2", cantidad: 1,
      encofrado_unitario_m2: 1.8, encofrado_total_m2: 1.8 },
    { identificador: "F2-003-p001", referencia: "F2", cantidad: 1,
      encofrado_unitario_m2: 2.1, encofrado_total_m2: 2.1 },
  ];
  const concreteGroups = groupFoundationComputations(foundations);
  const formworkGroups = groupFormworkComputations(formwork, foundations);

  assert.equal(concreteGroups.length, 2);
  assert.deepEqual(concreteGroups.map((item) => item.cantidad), [2, 1]);
  assert.equal(concreteGroups[0].volumen_total, 1.35);
  assert.deepEqual(concreteGroups[0].elementos.map((item) => item.identificador),
    ["F2-001-p001", "F2-002-p001"]);
  assert.equal(concreteGroups.reduce((sum, item) => sum + item.volumen_total, 0), 2.25);

  assert.equal(formworkGroups.length, 2);
  assert.deepEqual(formworkGroups.map((item) => item.cantidad), [2, 1]);
  assert.equal(formworkGroups[0].area_total_m2, 3.6);
  assert.ok(Math.abs(formworkGroups[0].formula.resultado_m2 - 1.8) < 0.00001);
  assert.equal(formworkGroups[0].caras.length, 4);
  assert.equal(formworkGroups[0].comprobaciones.estado, "verificado");
  assert.ok(Math.abs(formworkGroups.reduce((sum, item) => sum + item.area_total_m2, 0) - 5.7) < 0.00001);
  assert.equal(foundations[0].cantidad, 1); // la salida original conserva la trazabilidad
});

test("deja intactos los resultados ya agregados del motor tabular", () => {
  const foundation = { referencia: "Z4", cantidad: 7, x: 0.8, y: 0.8, h: 0.4,
    volumen_unitario: 0.256, volumen_total: 1.792 };
  const formwork = { referencia: "Z4", cantidad: 7,
    dimensiones_m: { x: 0.8, y: 0.8, h: 0.4 }, area_unitaria_m2: 1.28,
    area_total_m2: 8.96, comprobaciones: { estado: "verificado" } };
  assert.deepEqual(groupFoundationComputations([foundation]), [foundation]);
  assert.deepEqual(groupFormworkComputations([formwork], [foundation]), [formwork]);
});
