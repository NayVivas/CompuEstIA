import { useState } from "react";

const keyFor = (row) => `${row.referencia_original}:${row.aparicion_original}`;

export default function FoundationTableReview({ review, error, onConfirm, onBack }) {
  const rows = review.filas || [];
  const previous = review.decision?.correcciones_referencias_cuadro || [];
  const [values, setValues] = useState(() => ({
    ...Object.fromEntries(rows.map((r) => [keyFor(r), r.referencia])),
    ...Object.fromEntries(previous.map((r) => [`${r.referencia_original}:${r.aparicion}`, r.referencia_correcta])),
  }));
  const [reasons, setReasons] = useState(() => Object.fromEntries(previous.map((r) => [`${r.referencia_original}:${r.aparicion}`, r.motivo])));
  const [reviewer, setReviewer] = useState(review.decision?.revisor || "");
  const [selected, setSelected] = useState(rows[0]);
  const [zoom, setZoom] = useState(true);
  const [formError, setFormError] = useState("");
  const page = review.paginas?.find((p) => p.pagina === selected?.pagina);
  const box = selected?.caja_visual;
  const changed = rows.filter((row) => values[keyFor(row)]?.trim().toUpperCase() !== row.referencia);

  function submit(event) {
    event.preventDefault();
    if (!changed.length) {
      setFormError("Corregí al menos una referencia. Podés mantener la aparición que esté bien.");
      return;
    }
    if (changed.some((row) => (reasons[keyFor(row)] || "").trim().length < 10)) {
      setFormError("Escribí un motivo de al menos 10 caracteres para cada corrección.");
      return;
    }
    setFormError("");
    onConfirm({
      huellas_archivos: review.huellas_archivos,
      revisor: reviewer.trim(),
      correcciones_referencias_cuadro: changed.map((row) => ({
        referencia_original: row.referencia_original,
        aparicion: row.aparicion_original,
        referencia_correcta: values[keyFor(row)].trim().toUpperCase(),
        motivo: reasons[keyFor(row)].trim(),
      })),
    });
  }

  return (
    <main className="mx-auto max-w-[1500px] px-5 py-8 sm:px-8">
      <button type="button" onClick={onBack} className="mb-5 text-sm font-bold text-slate-600">← Volver a los archivos</button>
      <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <p className="text-xs font-bold uppercase tracking-widest text-amber-800">Revisión requerida · Fundaciones</p>
        <h1 className="mt-2 text-2xl font-bold text-slate-950">Referencias repetidas en el cuadro</h1>
        <p className="mt-2 text-sm text-amber-950">{review.mensaje}</p>
        <p className="mt-2 text-xs text-amber-800">El cálculo está pendiente. Esta revisión no genera cantidades provisionales.</p>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-2">
        <form onSubmit={submit} className="space-y-4">
          {review.referencias_planta_sin_cuadro?.length > 0 && (
            <div className="rounded-xl border border-cyan-200 bg-cyan-50 p-4 text-sm text-cyan-950">
              Referencias candidatas leídas en la planta y ausentes del cuadro: <strong>{review.referencias_planta_sin_cuadro.join(", ")}</strong>.
              <p className="mt-1 text-xs">Son indicios para revisar. Ninguna corrección se aplica automáticamente.</p>
            </div>
          )}
          {rows.map((row) => {
            const key = keyFor(row);
            const modified = values[key]?.trim().toUpperCase() !== row.referencia;
            return (
              <section key={key} className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h2 className="font-bold text-slate-950">{row.referencia_original} · aparición {row.aparicion_original}</h2>
                    <p className="mt-1 text-xs text-slate-500">Fila {row.numero_fila} · página {row.pagina}</p>
                    <p className="mt-2 text-sm text-slate-700">Dimensiones: {["x", "y", "h"].map((d) => row.dimensiones_m?.[d] ?? "—").join(" × ")} m</p>
                  </div>
                  <button type="button" onClick={() => { setSelected(row); setZoom(true); }} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-teal-700">Ver evidencia</button>
                </div>
                <label className="mt-4 block text-xs font-bold text-slate-700" htmlFor={`ref-${key}`}>Referencia validada</label>
                <input id={`ref-${key}`} required maxLength={30} value={values[key]} onChange={(e) => setValues({ ...values, [key]: e.target.value })} className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm" />
                <p className="mt-1 text-xs text-slate-500">{modified ? "Esta aparición se corregirá al confirmar." : "Esta aparición se mantendrá con su referencia actual."}</p>
                {modified && <>
                  <label className="mt-4 block text-xs font-bold text-slate-700" htmlFor={`reason-${key}`}>Motivo de la corrección</label>
                  <textarea id={`reason-${key}`} required minLength={10} maxLength={1000} value={reasons[key] || ""} onChange={(e) => setReasons({ ...reasons, [key]: e.target.value })} className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm" placeholder="Indicá qué evidencia del plano justifica el cambio." />
                </>}
              </section>
            );
          })}
          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <label htmlFor="table-reviewer" className="text-sm font-bold text-slate-800">Profesional que revisa</label>
            <input id="table-reviewer" required minLength={2} maxLength={160} value={reviewer} onChange={(e) => setReviewer(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm" placeholder="Nombre y apellido" />
            <p className="mt-2 text-xs leading-5 text-slate-500">Se guardarán el nombre declarado, fecha, motivo y archivos revisados. La corrección se reutiliza para estos mismos PDF en este proyecto.</p>
            {(error || formError) && <p role="alert" className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error || formError}</p>}
            <button type="submit" className="primary-button mt-5 w-full">Guardar corrección y reprocesar</button>
          </section>
        </form>

        <aside className="rounded-2xl border border-slate-200 bg-white p-5 xl:sticky xl:top-5">
          <h2 className="font-bold text-slate-900">Evidencia del cuadro</h2>
          <p className="mt-1 break-all text-xs text-slate-500">{review.archivo} · página {selected?.pagina}</p>
          <button type="button" onClick={() => setZoom(!zoom)} className="my-4 text-xs font-bold text-teal-700">{zoom ? "Ver lámina completa" : "Acercar a la fila"}</button>
          {page && box ? (
            <svg role="img" aria-label={`Ubicación de ${selected.referencia_original}, aparición ${selected.aparicion_original}`} className="max-h-[70vh] w-full rounded-lg border border-slate-200 bg-slate-50" viewBox={zoom ? `0 ${Math.max(0, box.y0 - 60)} ${page.ancho} ${Math.min(page.alto, 150)}` : `0 0 ${page.ancho} ${page.alto}`}>
              <image href={page.imagen} width={page.ancho} height={page.alto} />
              <rect x={box.x0 - 3} y={box.y0 - 3} width={box.x1 - box.x0 + 6} height={box.y1 - box.y0 + 6} fill="#fbbf2450" stroke="#d97706" strokeWidth="1" />
            </svg>
          ) : <p className="text-sm text-slate-500">Vista previa no disponible. Revisá el PDF original.</p>}
          {review.advertencias?.map((warning) => <p key={warning} className="mt-3 text-xs text-amber-800">{warning}</p>)}
        </aside>
      </div>
    </main>
  );
}
