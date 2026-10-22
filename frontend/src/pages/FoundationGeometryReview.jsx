import { useEffect, useMemo, useState } from "react";

import {
  getGeometryDecision,
  saveGeometryDecision,
} from "../services/documentReviewStorage";

function initialRows(review, saved) {
  const savedById = new Map(
    (saved?.elementos || []).map((item) => [item.id, item])
  );
  const detected = (review.elementos || []).map((item) => {
    const previous = savedById.get(item.id);
    return {
      id: item.id,
      incluir: previous?.incluir ?? true,
      referencia:
        previous?.referencia ?? item.referencia_propuesta ?? "",
      x_m:
        previous?.x_m ?? item.x_m_propuesto ?? "",
      y_m:
        previous?.y_m ?? item.y_m_propuesto ?? "",
      h_m:
        previous?.h_m ?? item.h_m_propuesto ?? "",
      pagina_motor: item.pagina_motor,
      centro_visual: previous?.centro_visual ?? item.centro_visual,
      motivo_exclusion: previous?.motivo_exclusion ?? "",
    };
  });
  const manuallyPlaced = (saved?.elementos || [])
    .filter((item) => /^manual-[0-9a-f-]{36}$/.test(item.id || ""))
    .map((item) => ({ ...item, x_m: item.x_m ?? "", y_m: item.y_m ?? "", h_m: item.h_m ?? "" }));
  return [...detected, ...manuallyPlaced];
}

function validPositive(value) {
  const parsed = Number(String(value).replace(",", "."));
  return Number.isFinite(parsed) && parsed > 0 && parsed <= 100;
}

export default function FoundationGeometryReview({
  review,
  projectId,
  error,
  onConfirm,
  onBack,
}) {
  const [rows, setRows] = useState(() => initialRows(review));
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [commonHeight, setCommonHeight] = useState("");
  const [selectedId, setSelectedId] = useState(
    review.elementos?.[0]?.id || null
  );
  const [viewPageNumber, setViewPageNumber] = useState(review.elementos?.[0]?.pagina_motor || review.paginas?.[0]?.pagina_motor || 1);
  const [placementMode, setPlacementMode] = useState(null);
  const [localError, setLocalError] = useState("");
  const [saving, setSaving] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    getGeometryDecision(projectId, review.identidad_fuentes)
      .then((saved) => {
        if (!active) return;
        const restored = initialRows(review, saved);
        setRows(restored);
        if (restored.length) setSelectedId((current) => current || restored[0].id);
        setReviewer(saved?.revisor || "");
        setReason(saved?.motivo || "");
        setReady(true);
      })
      .catch((storageError) => {
        if (!active) return;
        setLocalError(storageError.message);
        setReady(true);
      });
    return () => {
      active = false;
    };
  }, [projectId, review]);

  const proposalById = useMemo(
    () => new Map((review.elementos || []).map((item) => [item.id, item])),
    [review]
  );
  const selectedRow = rows.find((item) => item.id === selectedId);
  const selected = proposalById.get(selectedId);
  const selectedPage = (review.paginas || []).find(
    (page) => page.pagina_motor === viewPageNumber
  );
  const missing = rows.filter(
    (row) =>
      row.incluir &&
      (!row.referencia.trim() ||
        !validPositive(row.x_m) ||
        !validPositive(row.y_m) ||
        !validPositive(row.h_m))
  ).length;
  const excludedWithoutReason = rows.filter(
    (row) => !row.incluir && row.motivo_exclusion.trim().length < 10
  ).length;

  function updateRow(id, changes) {
    setRows((current) =>
      current.map((row) => (row.id === id ? { ...row, ...changes } : row))
    );
    setSelectedId(id);
    setLocalError("");
  }

  function chooseRow(row) {
    setSelectedId(row.id);
    setViewPageNumber(row.pagina_motor);
    setPlacementMode(null);
  }

  function placeOnPlan(event) {
    if (!placementMode || !selectedPage) return;
    const rectangle = event.currentTarget.getBoundingClientRect();
    const centro_visual = {
      x: Math.round((event.clientX - rectangle.left) / rectangle.width * selectedPage.ancho_visual_pt * 1000) / 1000,
      y: Math.round((event.clientY - rectangle.top) / rectangle.height * selectedPage.alto_visual_pt * 1000) / 1000,
    };
    if (placementMode === "move" && selectedRow && selectedRow.pagina_motor === viewPageNumber) {
      updateRow(selectedRow.id, { centro_visual });
    } else if (placementMode === "add") {
      const id = `manual-${crypto.randomUUID()}`;
      setRows((current) => [...current, {
        id, incluir: true, referencia: "", x_m: "", y_m: "", h_m: "",
        pagina_motor: viewPageNumber, centro_visual, motivo_exclusion: "",
      }]);
      setSelectedId(id);
    }
    setPlacementMode(null);
  }

  function applyHeight() {
    if (!validPositive(commonHeight)) {
      setLocalError("Ingresá una altura común mayor que 0 y menor o igual que 100 m.");
      return;
    }
    setRows((current) =>
      current.map((row) =>
        row.incluir ? { ...row, h_m: commonHeight } : row
      )
    );
    setLocalError("");
  }

  async function submit() {
    if (missing) {
      setLocalError(
        `Completá referencia, X, Y y H en ${missing} elemento${missing === 1 ? "" : "s"} incluido${missing === 1 ? "" : "s"}.`
      );
      return;
    }
    if (excludedWithoutReason) {
      setLocalError(
        `Explicá la exclusión de ${excludedWithoutReason} elemento${excludedWithoutReason === 1 ? "" : "s"} con al menos 10 caracteres.`
      );
      return;
    }
    if (reviewer.trim().length < 2 || reason.trim().length < 10) {
      setLocalError(
        "Indicá el profesional responsable y un motivo general de al menos 10 caracteres."
      );
      return;
    }

    const decision = {
      version: review.version,
      identidad_fuentes: review.identidad_fuentes,
      revisor: reviewer.trim(),
      motivo: reason.trim(),
      elementos: rows.map((row) => ({
        id: row.id,
        incluir: row.incluir,
        referencia: row.referencia.trim().toUpperCase(),
        x_m: row.incluir ? Number(String(row.x_m).replace(",", ".")) : null,
        y_m: row.incluir ? Number(String(row.y_m).replace(",", ".")) : null,
        h_m: row.incluir ? Number(String(row.h_m).replace(",", ".")) : null,
        pagina_motor: row.pagina_motor,
        centro_visual: row.incluir ? row.centro_visual : null,
        motivo_exclusion: row.incluir ? null : row.motivo_exclusion.trim(),
      })),
    };
    setSaving(true);
    setLocalError("");
    try {
      await saveGeometryDecision(projectId, decision);
      await onConfirm(decision);
    } catch (saveError) {
      setLocalError(saveError.message || "No se pudo guardar la revisión.");
    } finally {
      setSaving(false);
    }
  }

  const marker = selectedRow?.centro_visual;
  const markerStyle = marker && selectedPage && selectedRow.pagina_motor === viewPageNumber
    ? {
        left: `${(marker.x / selectedPage.ancho_visual_pt) * 100}%`,
        top: `${(marker.y / selectedPage.alto_visual_pt) * 100}%`,
      }
    : null;

  return (
    <main className="mx-auto max-w-7xl space-y-6 p-6 sm:p-8">
      <header className="space-y-3">
        <h1 className="text-3xl font-bold">Revisión de geometría de fundaciones</h1>
        <p>
          El plano contiene cotas distribuidas en lugar de un cuadro único. El
          sistema propone dimensiones por ocurrencia; un profesional debe
          confirmarlas, corregirlas o excluir el elemento antes de calcular.
        </p>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          Esta revisión habilita solamente hormigón y encofrado de las zapatas
          confirmadas. El acero, los pedestales, las vigas de riostra y las
          columnas permanecen pendientes hasta contar con fuentes verificables.
        </div>
        {!!review.referencias_no_interpretadas?.length && (
          <p role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm">
            Hay rótulos no incorporados por este lector: {review.referencias_no_interpretadas.map((item) => `${item.texto} (pág. ${item.pagina_motor})`).join(", ")}.
            Revisá si representan fundaciones adicionales. Las cantidades siguientes serán parciales y no incluirán esos elementos.
          </p>
        )}
        {!review.elementos?.length && <p className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm">No se reconocieron rótulos de zapatas. Podés ubicar manualmente las ocurrencias sobre la planta; cada una necesitará referencia y cotas verificadas.</p>}
        <div className="flex flex-wrap gap-3">
          <button className="rounded border px-4 py-2" onClick={onBack} type="button">
            Volver a los documentos
          </button>
          <span className="rounded bg-slate-100 px-4 py-2 text-sm font-semibold">
            {rows.length} ocurrencias · {missing} incompletas · {rows.filter((row) => !row.incluir).length} excluidas
          </span>
        </div>
      </header>

      {(error || localError) && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-red-800">
          {localError || error}
        </p>
      )}

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(360px,.85fr)]">
        <div className="space-y-3 rounded-2xl border bg-white p-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm font-semibold">
              Altura común H (m)
              <input
                className="mt-1 block w-40 rounded border px-3 py-2"
                value={commonHeight}
                onChange={(event) => setCommonHeight(event.target.value)}
                inputMode="decimal"
                placeholder="Ej. 0,40"
              />
            </label>
            <button className="rounded bg-blue-800 px-4 py-2 text-white" onClick={applyHeight} type="button">
              Aplicar a incluidas
            </button>
          </div>

          <div className="max-h-[720px] overflow-auto rounded-xl border">
            <table className="min-w-[860px] w-full border-collapse text-left text-sm">
              <thead className="sticky top-0 z-10 bg-slate-100">
                <tr>
                  <th className="px-3 py-2">Usar</th>
                  <th className="px-3 py-2">Fuente</th>
                  <th className="px-3 py-2">Referencia</th>
                  <th className="px-3 py-2">X (m)</th>
                  <th className="px-3 py-2">Y (m)</th>
                  <th className="px-3 py-2">H (m)</th>
                  <th className="px-3 py-2">Exclusión</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((row) => {
                  const proposal = proposalById.get(row.id);
                  const incomplete = row.incluir &&
                    (!row.referencia.trim() || !validPositive(row.x_m) || !validPositive(row.y_m) || !validPositive(row.h_m));
                  return (
                    <tr
                      key={row.id}
                      className={`${selectedId === row.id ? "bg-blue-50" : ""} ${incomplete ? "text-amber-900" : ""}`}
                      onClick={() => chooseRow(row)}
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={row.incluir}
                          onChange={(event) => updateRow(row.id, { incluir: event.target.checked })}
                          aria-label={`Incluir ${row.id}`}
                        />
                      </td>
                      <td className="px-3 py-2 text-xs">
                        <button className="text-left font-semibold text-blue-800 underline" type="button" onClick={() => chooseRow(row)}>
                          {proposal?.fuente?.archivo || (review.paginas || []).find((page) => page.pagina_motor === row.pagina_motor)?.fuente?.archivo || "Planta"} · pág. {proposal?.fuente?.pagina || row.pagina_motor}
                        </button>
                        {!proposal && <button type="button" className="block text-xs text-red-700 underline" onClick={() => { setRows((current) => current.filter((item) => item.id !== row.id)); setSelectedId(null); }}>Quitar ubicación añadida</button>}
                      </td>
                      <td className="px-3 py-2">
                        <input className="w-24 rounded border px-2 py-1" value={row.referencia} onChange={(event) => updateRow(row.id, { referencia: event.target.value })} />
                      </td>
                      {[
                        ["x_m", "X"],
                        ["y_m", "Y"],
                        ["h_m", "H"],
                      ].map(([field, label]) => (
                        <td className="px-3 py-2" key={field}>
                          <input
                            className="w-20 rounded border px-2 py-1"
                            value={row[field]}
                            disabled={!row.incluir}
                            onChange={(event) => updateRow(row.id, { [field]: event.target.value })}
                            inputMode="decimal"
                            aria-label={`${label} de ${row.id}`}
                          />
                        </td>
                      ))}
                      <td className="px-3 py-2">
                        {!row.incluir && (
                          <input
                            className="w-64 rounded border px-2 py-1"
                            value={row.motivo_exclusion}
                            onChange={(event) => updateRow(row.id, { motivo_exclusion: event.target.value })}
                            placeholder="Motivo de exclusión"
                          />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="space-y-3 rounded-2xl border bg-white p-4 lg:sticky lg:top-4 lg:self-start">
          <div>
            <h2 className="font-bold">Ubicación en el plano</h2>
            <p className="text-sm text-slate-500">
              {selectedPage?.fuente?.archivo || selected?.fuente?.archivo || "Plano"} · página {selectedPage?.fuente?.pagina || viewPageNumber} · {selectedRow?.id || "sin selección"}
            </p>
          </div>
          <label className="block text-sm font-semibold">Página de la planta
            <select value={viewPageNumber} onChange={(event) => { setViewPageNumber(Number(event.target.value)); setPlacementMode(null); }} className="mt-1 block w-full rounded border px-3 py-2">
              {(review.paginas || []).map((page) => <option key={page.pagina_motor} value={page.pagina_motor}>{page.fuente?.archivo || "Plano"} · página {page.fuente?.pagina || page.pagina_motor}</option>)}
            </select>
          </label>
          <div className="flex flex-wrap gap-2 text-sm">
            <button type="button" className="rounded bg-blue-800 px-3 py-2 text-white" onClick={() => setPlacementMode("add")}>Añadir fundación en esta página</button>
            <button type="button" disabled={!selectedRow || selectedRow.pagina_motor !== viewPageNumber} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => setPlacementMode("move")}>Mover seleccionada</button>
            {placementMode && <button type="button" className="rounded border px-3 py-2" onClick={() => setPlacementMode(null)}>Cancelar</button>}
          </div>
          {placementMode && <p className="text-sm text-blue-900">Hacé clic en la planta para {placementMode === "add" ? "ubicar la nueva fundación" : "corregir la posición seleccionada"}. Luego completá y verificá sus medidas.</p>}
          {selectedPage?.imagen ? (
            <div className="relative overflow-auto rounded border bg-slate-100">
              <div className="relative min-w-full">
                <img className={`block h-auto w-full ${placementMode ? "cursor-crosshair" : ""}`} onClick={placeOnPlan} src={selectedPage.imagen} alt={`Página ${selectedPage.pagina_motor} con las referencias seleccionadas`} />
                {markerStyle && (
                  <div
                    className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-red-600 shadow"
                    style={markerStyle}
                  />
                )}
                {rows.filter((row) => row.id !== selectedId && row.pagina_motor === viewPageNumber && row.centro_visual).map((row) => <button key={row.id} type="button" aria-label={`Seleccionar ${row.referencia || row.id} en la planta`} title={row.referencia || row.id} className="absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white bg-blue-700" style={{ left: `${row.centro_visual.x / selectedPage.ancho_visual_pt * 100}%`, top: `${row.centro_visual.y / selectedPage.alto_visual_pt * 100}%` }} onClick={() => chooseRow(row)} />)}
              </div>
            </div>
          ) : (
            <p>No se pudo generar la vista previa de esta página.</p>
          )}
          <p className="text-sm text-slate-600">
            {selected?.origen_dimensiones === "cuadro_local_tipado"
              ? "X, Y y H propuestas desde la fila del cuadro de fundaciones."
              : selected?.origen_dimensiones === "contorno_y_dos_cotas_coherentes"
                ? "X e Y propuestas desde dos cotas exteriores con escala coherente con el contorno."
                : "No se pudo asociar X e Y con evidencia suficiente. Las cotas cercanas son alternativas, no medidas confirmadas."}
            {selected?.evidencia_altura && ` H propuesta desde el detalle típico: «${selected.evidencia_altura.texto}». Confirmá que corresponde a esta ocurrencia.`}
          </p>
          {!!selected?.alternativas_dimensiones?.length && (
            <details className="text-sm">
              <summary>Cotas cercanas consideradas</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {selected.alternativas_dimensiones.map((item, index) => (
                  <li key={`${item.texto}-${index}`}>
                    «{item.texto}» → {item.valor_m} m · {item.eje_relativo}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </aside>
      </section>

      <section className="space-y-4 rounded-2xl border bg-white p-5">
        <h2 className="text-xl font-bold">Responsabilidad de la revisión</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-semibold">
            Profesional responsable
            <input className="mt-1 block w-full rounded border px-3 py-2" value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
          </label>
          <label className="text-sm font-semibold">
            Motivo o criterio aplicado
            <input className="mt-1 block w-full rounded border px-3 py-2" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Ej. Dimensiones comprobadas contra las cotas del plano" />
          </label>
        </div>
        <button
          className="rounded bg-slate-900 px-5 py-3 font-semibold text-white disabled:cursor-wait disabled:opacity-60"
          type="button"
          disabled={saving || !ready}
          onClick={submit}
        >
          {saving ? "Guardando y calculando…" : "Guardar revisión y calcular cantidades verificadas"}
        </button>
      </section>
    </main>
  );
}

