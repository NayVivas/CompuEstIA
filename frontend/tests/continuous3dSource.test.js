import test from "node:test";
import assert from "node:assert/strict";
import { selectReviewedContinuousSegments } from "../src/utils/continuous3dSource.js";

const segment = {
  id: "tramo-p1-1", referencia: "C-2", fuente: { sha256: "abc", pagina: 1 },
  inicio: { x: 100, y: 100 }, fin: { x: 200, y: 100 },
  longitud_m: 10, puntos_por_metro: 10,
  ancho_base_m: 0.7, ancho_superior_m: 0.3, altura_m: 0.4,
};

test("sólo usa extremos y sección congruentes con la longitud calculada", () => {
  assert.deepEqual(selectReviewedContinuousSegments({
    cimientos_corridos_detalle: [{ referencia: "C-2", longitud_m: 10 }],
  }), []);
  assert.deepEqual(selectReviewedContinuousSegments({
    cimientos_corridos_tramos: [segment, { ...segment, id: "falso", longitud_m: 20 }],
  }).map((item) => item.id), [segment.id]);
});
