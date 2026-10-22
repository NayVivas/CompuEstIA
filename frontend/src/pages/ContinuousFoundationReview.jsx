import { useEffect, useMemo, useState } from "react";

import {
  getGeometryDecision,
  saveGeometryDecision,
} from "../services/documentReviewStorage";

function decimal(value) {
  return value === null || value === undefined ? "" : String(value);
}

function positive(value, maximum) {
  const parsed = Number(String(value).replace(",", "."));
  return Number.isFinite(parsed) && parsed > 0 && parsed <= maximum;
}

function initialRows(review, saved) {
  const compatible = saved?.version === review.version ? saved : null;
  const savedById = new Map(
    (compatible?.elementos || []).map((item) => [item.id, item]),
  );

  return (review.elementos || []).map((item) => {
    const previous = savedById.get(item.id);
    return {
      id: item.id,
      incluir: previous?.incluir ?? item.origen_referencia !== "solo_detalle",
      referencia: previous?.referencia ?? item.referencia_propuesta ?? "",
      ancho_superior_m: decimal(
        previous?.ancho_superior_m ?? item.ancho_superior_m_propuesto,
      ),
      ancho_base_m: decimal(
        previous?.ancho_base_m ?? item.ancho_base_m_propuesto,
      ),
      altura_m: decimal(previous?.altura_m ?? item.altura_m_propuesta),
      longitud_m: decimal(previous?.longitud_m ?? item.longitud_m_propuesta),
      material: previous?.material ?? item.material_propuesto ?? "",
      motivo_exclusion: previous?.motivo_exclusion ?? item.motivo_exclusion_propuesto ?? "",
      motivo_inclusion: previous?.motivo_inclusion ?? "",
      tramos: previous?.tramos ?? (item.tramos_propuestos || []).map((tramo) => ({ id: tramo.id })),
    };
  });
}

function measurementSummary(review) {
  const pages = review.diagnostico_medicion?.paginas || [];
  const calibrated = pages.find(
    (item) => item.calibracion?.estado === "calibrado",
  )?.calibracion;
  if (!calibrated) return null;
  return `${calibrated.cota_horizontal_m} × ${calibrated.cota_vertical_m} m · confianza ${Math.round((calibrated.confianza || 0) * 100)} %`;
}

export default function ContinuousFoundationReview({
  review,
  projectId,
  error,
  onConfirm,
  onBack,
}) {
  const [rows, setRows] = useState(() => initialRows(review));
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [selectedId, setSelectedId] = useState(
    review.elementos?.find((item) => item.apariciones_rotulo > 0)?.id || review.elementos?.[0]?.id || null,
  );
  const [localError, setLocalError] = useState("");
  const [saving, setSaving] = useState(false);
  const [ready, setReady] = useState(false);
  const [sourceView, setSourceView] = useState("planta");
  const [viewPageNumber, setViewPageNumber] = useState(review.elementos?.[0]?.pagina_motor || review.paginas?.[0]?.pagina_motor || 1);
  const [drawingStart, setDrawingStart] = useState(null);

  useEffect(() => {
    let active = true;
    getGeometryDecision(projectId, review.identidad_fuentes)
      .then((saved) => {
        if (!active) return;
        const compatible = saved?.version === review.version ? saved : null;
        setRows(initialRows(review, compatible));
        setReviewer(compatible?.revisor || "");
        setReason(compatible?.motivo || "");
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
    [review],
  );
  const selected = proposalById.get(selectedId) || review.elementos?.[0];
  const selectedRow = rows.find((row) => row.id === selected?.id);
  const selectedPage = (review.paginas || []).find(
    (page) => page.pagina_motor === viewPageNumber,
  );
  const calibration = (review.diagnostico_medicion?.paginas || []).find(
    (page) => page.pagina_motor === viewPageNumber,
  )?.calibracion;
  const availableSegments = selected?.tramos_propuestos || [];
  const selectedSegments = (selectedRow?.tramos || []).map(
    (segment) => availableSegments.find((candidate) => candidate.id === segment.id) || segment,
  ).filter((segment) => segment.pagina_motor === viewPageNumber);
  const ficha = selected?.ficha_lector_15 || (review.fichas_lector_15?.fichas || []).find(
    (item) => item.origen_pdf_coincide
      && ["cimiento_corrido", "cimentacion_sin_subtipo"].includes(item.familia)
      && item.referencia?.replace(/[_.]/g, "-").replace(/^C(\d)/i, "C-$1")
        .toUpperCase() === selected?.referencia_propuesta,
  );
  const detailPage = (review.paginas_detalle_lector_15 || []).find(
    (page) => page.sha256_pdf === (ficha?.sha256_pdf || selected?.fuente?.sha256)
      && page.pagina === (ficha?.pagina || selected?.fuente?.pagina),
  );
  const showDetail = (sourceView === "detalle" || !selectedPage) && !!detailPage;
  const materials = review.materiales_permitidos || [];
  const missing = rows.filter(
    (row) =>
      row.incluir &&
      (!row.referencia.trim() ||
        !positive(row.ancho_superior_m, 10) ||
        !positive(row.ancho_base_m, 10) ||
        !positive(row.altura_m, 10) ||
        !positive(row.longitud_m, 10000)),
  ).length;
  const invalidSection = rows.filter(
    (row) =>
      row.incluir &&
      positive(row.ancho_superior_m, 10) &&
      positive(row.ancho_base_m, 10) &&
      Number(String(row.ancho_base_m).replace(",", ".")) <
        Number(String(row.ancho_superior_m).replace(",", ".")),
  ).length;
  const excludedWithoutReason = rows.filter(
    (row) => !row.incluir && row.motivo_exclusion.trim().length < 10,
  ).length;
  const includedWithoutEvidence = rows.filter((row) =>
    row.incluir && proposalById.get(row.id)?.origen_referencia === "solo_detalle"
    && row.motivo_inclusion.trim().length < 10,
  ).length;

  function updateRow(id, changes) {
    setRows((current) =>
      current.map((row) => (row.id === id ? { ...row, ...changes } : row)),
    );
    setSelectedId(id);
    setLocalError("");
  }

  function chooseRow(row) {
    setSelectedId(row.id);
    setViewPageNumber(proposalById.get(row.id)?.pagina_motor || viewPageNumber);
    setDrawingStart(null);
  }

  function setSegments(row, segments) {
    const candidates = proposalById.get(row.id)?.tramos_propuestos || [];
    const length = segments.reduce((sum, segment) =>
      sum + (candidates.find((item) => item.id === segment.id) || segment).longitud_m, 0);
    updateRow(row.id, {
      tramos: segments,
      longitud_m: segments.length ? length.toFixed(2) : "",
    });
  }

  function drawSegment(event) {
    if (!selectedPage || !selectedRow || !calibration?.puntos_por_metro) return;
    const box = event.currentTarget.getBoundingClientRect();
    const point = {
      x: Math.round((event.clientX - box.left) / box.width * selectedPage.ancho_visual_pt * 1000) / 1000,
      y: Math.round((event.clientY - box.top) / box.height * selectedPage.alto_visual_pt * 1000) / 1000,
    };
    if (!drawingStart || drawingStart.pending) {
      setDrawingStart(point);
      return;
    }
    const length = Math.hypot(point.x - drawingStart.x, point.y - drawingStart.y) / calibration.puntos_por_metro;
    if (length < 0.05) {
      setLocalError("Marcá dos puntos distintos separados por al menos 5 cm.");
      return;
    }
    const segment = {
      id: `manual-${crypto.randomUUID()}`,
      pagina_motor: viewPageNumber,
      inicio: drawingStart,
      fin: point,
      longitud_m: Math.round(length * 100000) / 100000,
    };
    setSegments(selectedRow, [...selectedRow.tramos, segment]);
    setDrawingStart(null);
  }

  async function submit() {
    if (missing) {
      setLocalError(
        `Revisá referencia, sección y longitud en ${missing} tipo${missing === 1 ? "" : "s"} incluido${missing === 1 ? "" : "s"}.`,
      );
      return;
    }
    if (invalidSection) {
      setLocalError("El ancho de base no puede ser menor que el ancho superior.");
      return;
    }
    if (excludedWithoutReason) {
      setLocalError(
        `Explicá la exclusión de ${excludedWithoutReason} tipo${excludedWithoutReason === 1 ? "" : "s"} con al menos 10 caracteres.`,
      );
      return;
    }
    if (includedWithoutEvidence) {
      setLocalError("Para incluir un tipo que solo figura en el detalle, indicá el plano y el criterio usados para verificar su recorrido.");
      return;
    }
    if (reviewer.trim().length < 2 || reason.trim().length < 10) {
      setLocalError(
        "Indicá el profesional responsable y un criterio de revisión de al menos 10 caracteres.",
      );
      return;
    }

    const number = (value) => Number(String(value).replace(",", "."));
    const decision = {
      version: review.version,
      identidad_fuentes: review.identidad_fuentes,
      revisor: reviewer.trim(),
      motivo: reason.trim(),
      elementos: rows.map((row) => ({
        id: row.id,
        incluir: row.incluir,
        referencia: row.referencia.trim().toUpperCase(),
        ancho_superior_m: row.incluir ? number(row.ancho_superior_m) : null,
        ancho_base_m: row.incluir ? number(row.ancho_base_m) : null,
        altura_m: row.incluir ? number(row.altura_m) : null,
        longitud_m: row.incluir ? number(row.longitud_m) : null,
        material: row.incluir ? row.material || null : null,
        motivo_exclusion: row.incluir ? null : row.motivo_exclusion.trim(),
        motivo_inclusion: row.incluir && proposalById.get(row.id)?.origen_referencia === "solo_detalle"
          ? row.motivo_inclusion.trim() : null,
        tramos: row.incluir ? row.tramos : [],
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

  const marker = showDetail ? ficha?.caja_visual_px :
    selected?.origen_referencia !== "solo_detalle" && selected?.pagina_motor === viewPageNumber ? selected?.caja_visual : null;
  const markerStyle =
    marker && (showDetail || selectedPage)
      ? {
          left: `${((showDetail ? marker[0] : marker.x0) / (showDetail ? ficha.ancho_px : selectedPage.ancho_visual_pt)) * 100}%`,
          top: `${((showDetail ? marker[1] : marker.y0) / (showDetail ? ficha.alto_px : selectedPage.alto_visual_pt)) * 100}%`,
          width: `${Math.max(((showDetail ? marker[2] - marker[0] : marker.x1 - marker.x0) / (showDetail ? ficha.ancho_px : selectedPage.ancho_visual_pt)) * 100, 1)}%`,
          height: `${Math.max(((showDetail ? marker[3] - marker[1] : marker.y1 - marker.y0) / (showDetail ? ficha.alto_px : selectedPage.alto_visual_pt)) * 100, 1)}%`,
        }
      : null;
  const calibrated = measurementSummary(review);

  return (
    <main className="mx-auto max-w-[1500px] space-y-6 p-6 sm:p-8">
      <header className="space-y-3">
        <p className="text-xs font-bold uppercase tracking-[.18em] text-blue-700">
          Propuesta automática trazable
        </p>
        <h1 className="text-3xl font-bold">Revisión de cimientos corridos</h1>
        <p className="max-w-4xl text-slate-600">
          Se localizaron referencias candidatas de cimientos corridos. El detalle aporta ancho y altura de la sección; la longitud corresponde al recorrido del tipo en la planta. Un campo vacío indica que no se pudo respaldar esa medida, no un error del plano.
        </p>
        <p className="max-w-4xl text-sm text-slate-600">Los ejes detectados son propuestas: verificá cada tramo sobre su página, descartá los erróneos o trazá extremos adicionales sobre una planta calibrada. Solo los recorridos confirmados se mostrarán en 3D.</p>
        {!!review.tipos_solo_detalle?.length && <p className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <strong>{review.tipos_solo_detalle.map((item) => item.referencia).join(", ")} figuran solo en los detalles.</strong>
          {" "}Sus cotas describen la sección transversal, no la longitud construida. No se encontraron rótulos ni recorridos para esos tipos en las plantas estructurales seleccionadas. Quedan excluidos inicialmente; si comprobás que sí se construyen en otra lámina, marcá «Usar», indicá su recorrido y verificá la longitud antes de calcular.
        </p>}
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border bg-white p-4">
            <span className="text-xs font-bold uppercase text-slate-500">Tipos detectados</span>
            <p className="mt-1 text-2xl font-bold">{rows.length}</p>
          </div>
          <div className="rounded-xl border bg-white p-4">
            <span className="text-xs font-bold uppercase text-slate-500">Calibración</span>
            <p className="mt-1 font-semibold">{calibrated || "Pendiente de verificación"}</p>
          </div>
          <div className="rounded-xl border bg-white p-4">
            <span className="text-xs font-bold uppercase text-slate-500">OCR local</span>
            <p className="mt-1 font-semibold">
              {review.diagnostico_ocr?.listo ? "Disponible" : "No disponible"}
            </p>
          </div>
        </div>
        {!review.diagnostico_ocr?.listo && (
          <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
            {review.diagnostico_ocr?.mensaje ||
              "El OCR local no está disponible; las cotas que falten deberán revisarse manualmente."}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <button className="rounded border px-4 py-2" onClick={onBack} type="button">
            Volver a los documentos
          </button>
          <span className="rounded bg-slate-100 px-4 py-2 text-sm font-semibold">
            {missing} incompletos · {rows.filter((row) => !row.incluir).length} excluidos
          </span>
        </div>
      </header>

      {(error || localError) && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-red-800">
          {localError || error}
        </p>
      )}

      <section className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-slate-800">
        <strong>Lectura de fichas integrada:</strong> {review.fichas_lector_15?.fichas?.length || 0} tipos documentales encontrados.
        Las medidas del lector aparecen como propuestas cuando coinciden con la planta; verificá sus cotas y recorridos antes de aprobar.
        {review.fichas_lector_15?.avisos?.map((aviso, index) => <p key={index} className="mt-2">{aviso}</p>)}
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,.55fr)]">
        <div className="overflow-auto rounded-2xl border bg-white">
          <table className="min-w-[1220px] w-full border-collapse text-left text-sm">
            <thead className="sticky top-0 z-10 bg-slate-100">
              <tr>
                <th className="px-3 py-3">Usar</th>
                <th className="px-3 py-3">Tipo</th>
                <th className="px-3 py-3">Ancho superior (m)</th>
                <th className="px-3 py-3">Ancho base (m)</th>
                <th className="px-3 py-3">Altura de sección (m)</th>
                <th className="px-3 py-3">Longitud del recorrido (m)</th>
                <th className="px-3 py-3">Material</th>
                <th className="px-3 py-3">Evidencia</th>
                <th className="px-3 py-3">Justificación</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row) => {
                const proposal = proposalById.get(row.id);
                return (
                  <tr
                    key={row.id}
                    className={selectedId === row.id ? "bg-blue-50" : ""}
                    onClick={() => chooseRow(row)}
                  >
                    <td className="px-3 py-3">
                      <input
                        type="checkbox"
                        checked={row.incluir}
                        onChange={(event) => updateRow(row.id, { incluir: event.target.checked })}
                        aria-label={`Incluir ${row.id}`}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <input
                        className="w-24 rounded border px-2 py-1 font-semibold"
                        value={row.referencia}
                        disabled={!row.incluir}
                        onChange={(event) => updateRow(row.id, { referencia: event.target.value })}
                      />
                      <p className="mt-1 text-xs text-slate-500">
                        {proposal?.origen_referencia === "solo_detalle" ? "Solo en detalle · sin recorrido" : `${proposal?.apariciones_rotulo || 0} rótulos en planta`}
                      </p>
                    </td>
                    {[
                      ["ancho_superior_m", 10],
                      ["ancho_base_m", 10],
                      ["altura_m", 10],
                      ["longitud_m", 10000],
                    ].map(([field, maximum]) => (
                      <td className="px-3 py-3" key={field}>
                        <input
                          className={`w-24 rounded border px-2 py-1 ${row.incluir && !positive(row[field], maximum) ? "border-amber-500 bg-amber-50" : ""}`}
                          value={row[field]}
                          disabled={!row.incluir}
                          inputMode="decimal"
                          onChange={(event) => updateRow(row.id, { [field]: event.target.value })}
                        />
                      </td>
                    ))}
                    <td className="px-3 py-3">
                      <select
                        className="w-48 rounded border px-2 py-1"
                        value={row.material}
                        disabled={!row.incluir}
                        onChange={(event) => updateRow(row.id, { material: event.target.value })}
                      >
                        <option value="">Sin confirmar</option>
                        {materials.map((item) => (
                          <option key={item.id} value={item.id}>{item.nombre}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-3 text-xs">
                      <span className="block font-semibold text-emerald-700">
                        Sección {proposal?.evidencia_seccion?.completa ? "leída" : "pendiente"}
                      </span>
                      {proposal?.ficha_lector_15 && <span className="block text-blue-700">Ficha visual asociada</span>}
                      {proposal?.conflicto_fichas_lector && <span className="block text-amber-700">Fuentes en conflicto</span>}
                      <span className="block text-slate-500">
                        Longitud {proposal?.evidencia_longitud ? "medida" : "pendiente"}
                      </span>
                      <span className="block text-blue-700">{row.tramos.length} tramos para revisar</span>
                    </td>
                    <td className="px-3 py-3">
                      {row.incluir && proposal?.origen_referencia === "solo_detalle" ? (
                        <input
                          className="w-64 rounded border px-2 py-1"
                          value={row.motivo_inclusion}
                          onChange={(event) => updateRow(row.id, { motivo_inclusion: event.target.value })}
                          placeholder="Plano y recorrido verificados"
                          aria-label={`Justificación para incluir ${row.referencia}`}
                        />
                      ) : !row.incluir && (
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

        <aside className="space-y-3 rounded-2xl border bg-white p-4 xl:sticky xl:top-4 xl:self-start">
          <div>
            <h2 className="font-bold">Evidencia en el plano</h2>
            <p className="text-sm text-slate-500">
              {showDetail ? detailPage.archivo : selectedPage?.fuente?.archivo || "Plano"} · página {showDetail ? detailPage.pagina : selectedPage?.fuente?.pagina || viewPageNumber} · {selected?.referencia_propuesta}
            </p>
          </div>
          {(detailPage || selectedPage) && <div className="flex gap-2 text-xs">
            {detailPage &&
            <button type="button" className={`rounded border px-3 py-1 ${showDetail ? "bg-slate-900 text-white" : ""}`} onClick={() => setSourceView("detalle")}>Ver detalle</button>
            }
            {selectedPage && <button type="button" className={`rounded border px-3 py-1 ${!showDetail ? "bg-slate-900 text-white" : ""}`} onClick={() => setSourceView("planta")}>Ver planta</button>}
          </div>}
          {!showDetail && <label className="block text-xs font-semibold">Página de la planta
            <select className="mt-1 block w-full rounded border px-2 py-2" value={viewPageNumber} onChange={(event) => { setViewPageNumber(Number(event.target.value)); setDrawingStart(null); }}>
              {(review.paginas || []).map((page) => <option key={page.pagina_motor} value={page.pagina_motor}>{page.fuente?.archivo || "Planta"} · pág. {page.fuente?.pagina || page.pagina_motor}</option>)}
            </select>
          </label>}
          {!showDetail && selectedRow && <div className="rounded border bg-slate-50 p-3 text-xs">
            <p>Tramos para {selectedRow.referencia} en esta página: {selectedSegments.length}. {calibration?.estado === "calibrado" ? "Escala calibrada con cotas." : "Sin escala verificada: no se pueden trazar metros desde píxeles."}</p>
            {availableSegments.filter((segment) => segment.pagina_motor === viewPageNumber).map((segment) => <label key={segment.id} className="mt-2 flex items-center gap-2">
              <input type="checkbox" checked={selectedRow.tramos.some((item) => item.id === segment.id)} onChange={(event) => setSegments(selectedRow, event.target.checked ? [...selectedRow.tramos, { id: segment.id }] : selectedRow.tramos.filter((item) => item.id !== segment.id))} />
              Eje propuesto {segment.id} · {segment.longitud_m.toFixed(2)} m
            </label>)}
            {selectedRow.tramos.filter((segment) => segment.id.startsWith("manual-") && segment.pagina_motor === viewPageNumber).map((segment) => <button key={segment.id} type="button" className="mt-2 block text-red-700 underline" onClick={() => setSegments(selectedRow, selectedRow.tramos.filter((item) => item.id !== segment.id))}>Quitar tramo trazado · {segment.longitud_m.toFixed(2)} m</button>)}
            {calibration?.estado === "calibrado" && <button type="button" className="mt-3 rounded bg-blue-800 px-3 py-2 text-white" onClick={() => setDrawingStart({ pending: true })}>{drawingStart ? "Elegí dos extremos en la planta" : "Trazar un tramo"}</button>}
            {!!selectedRow.tramos.length && <button type="button" className="mt-2 block text-amber-800 underline" onClick={() => { updateRow(selectedRow.id, { tramos: [] }); setDrawingStart(null); }}>Quitar trazos y usar longitud manual (sin 3D)</button>}
          </div>}
          {(showDetail ? detailPage?.imagen : selectedPage?.imagen) ? (
            <div className="relative overflow-auto rounded border bg-slate-100">
              <div className="relative min-w-full">
                <img className={`block h-auto w-full ${drawingStart && !showDetail ? "cursor-crosshair" : ""}`} onClick={drawingStart && !showDetail ? drawSegment : undefined} src={showDetail ? detailPage.imagen : selectedPage.imagen} alt={showDetail ? "Detalle de la sección localizada" : "Planta con el tipo de cimiento seleccionado"} />
                {!showDetail && selectedPage && <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${selectedPage.ancho_visual_pt} ${selectedPage.alto_visual_pt}`} preserveAspectRatio="none" aria-hidden="true">
                  {selectedSegments.map((segment) => <line key={segment.id} x1={segment.inicio.x} y1={segment.inicio.y} x2={segment.fin.x} y2={segment.fin.y} stroke="#dc2626" strokeWidth={Math.max(selectedPage.ancho_visual_pt / 450, 2)} strokeLinecap="round" />)}
                  {drawingStart && !drawingStart.pending && <circle cx={drawingStart.x} cy={drawingStart.y} r={Math.max(selectedPage.ancho_visual_pt / 200, 4)} fill="#2563eb" />}
                </svg>}
                {markerStyle && (
                  <div className="pointer-events-none absolute border-2 border-red-600 bg-red-500/20 shadow-[0_0_0_2px_white]" style={markerStyle} />
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm">No se pudo generar la vista previa.</p>
          )}
          <p className="text-xs text-slate-500">
            {showDetail ? "La marca ubica la ficha del detalle. Comprobá cotas y subtipo antes de confirmar." :
              "La marca localiza una aparición del tipo; las líneas rojas son los tramos seleccionados. La longitud no se deduce del número de rótulos."}
          </p>
          {selected?.conflicto_fichas_lector && <p role="alert" className="rounded bg-amber-50 p-2 text-xs text-amber-900">{selected.conflicto_fichas_lector}</p>}
        </aside>
      </section>

      <section className="space-y-4 rounded-2xl border bg-white p-5">
        <h2 className="text-xl font-bold">Confirmación profesional</h2>
        <p className="text-sm text-slate-600">
          El material puede dejarse sin confirmar: el sistema calculará el volumen geométrico y mostrará el subtotal por material como pendiente.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-semibold">
            Profesional responsable
            <input className="mt-1 block w-full rounded border px-3 py-2" value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
          </label>
          <label className="text-sm font-semibold">
            Criterio aplicado
            <input className="mt-1 block w-full rounded border px-3 py-2" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Ej. Cotas y recorridos comprobados contra la planta" />
          </label>
        </div>
        <button
          className="rounded bg-slate-900 px-5 py-3 font-semibold text-white disabled:cursor-wait disabled:opacity-60"
          type="button"
          disabled={saving || !ready}
          onClick={submit}
        >
          {saving ? "Guardando y calculando…" : "Guardar revisión y calcular"}
        </button>
      </section>
    </main>
  );
}
