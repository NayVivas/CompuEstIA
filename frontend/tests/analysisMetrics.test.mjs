import { test } from "node:test";
import { strict as assert } from "node:assert";

import { latestCompletedByProject, confirmedConcreteVolume } from "../src/utils/analysisMetrics.js";
import { withoutDemoSeeds } from "../src/services/workspaceStorage.js";

test("los proyectos se suman una vez con su último análisis y el material sin clasificar no figura como hormigón", () => {
  const analyses = [
    { projectId: 1, date: "2026-10-16T12:00:00Z", status: "Completado", resultado: { volumen_hormigon_m3: 12 } },
    { projectId: 2, date: "2026-10-17T12:00:00Z", status: "Completado", resultado: { volumen_cimientos_corridos_m3: 37.6874, volumen_hormigon_m3: 0 } },
    { projectId: 1, date: "2026-10-18T12:00:00Z", status: "Completado", resultado: { volumen_hormigon_m3: 15 } },
    { projectId: 3, date: "2026-10-18T12:00:00Z", status: "Procesando" },
  ];
  assert.equal(latestCompletedByProject(analyses).length, 2);
  assert.equal(confirmedConcreteVolume(analyses), 15);
});

test("se oculta el ejemplo antiguo sin borrar proyectos que el usuario sí analizó", () => {
  const data = {
    projects: [
      { id: 1, name: "Edificio Norte", client: "Constructora Norte", status: "En análisis", documents: 8, analyses: 3, volumeValue: 124.6, updated: "Hoy", documentsData: [] },
      { id: 2, name: "Viviendas Sur", client: "Grupo Viviendas Sur", status: "Completado", documents: 12, analyses: 5, volumeValue: 86.2, updated: "Ayer", documentsData: [{ name: "real.pdf" }] },
      { id: 7, name: "Proyecto personal" },
    ],
    analyses: [
      { id: 1, projectId: 1, status: "Completado" },
      { id: 3, projectId: 2, status: "Completado", resultado: { volumen_hormigon_m3: 2 } },
    ],
  };
  const cleaned = withoutDemoSeeds(data);
  assert.deepEqual(cleaned.projects.map((project) => project.id), [2, 7]);
  assert.deepEqual(cleaned.analyses.map((analysis) => analysis.id), [3]);
});
