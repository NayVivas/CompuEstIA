import { useState } from "react";
import { documentarIncidencia } from "../services/api";

export default function IncidentReview({ review, onBack, onRetry, onUpdate, error }) {
  const [revisor, setRevisor] = useState("");
  const [motivo, setMotivo] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(event, id) {
    event.preventDefault(); setBusy(true); setStatus("");
    try { onUpdate(await documentarIncidencia(review.analisis_id, id, { revisor, motivo })); setStatus("Observación guardada. El análisis sigue bloqueado."); }
    catch (e) { setStatus(e.message); }
    finally { setBusy(false); }
  }
  return <main className="mx-auto max-w-4xl space-y-5 p-8">
    <h1 className="text-2xl font-bold">Análisis pendiente de revisión</h1>
    <p>No hay cantidades válidas para este análisis. Corregí la fuente o la causa indicada y volvé a procesar.</p>
    <p className="text-sm">Identificador: {review.analisis_id}</p>
    {(review.resultado?.incidencias || []).map((item) => <article key={item.id} className="space-y-3 rounded-xl border border-amber-300 bg-white p-6">
      <h2 className="font-bold">{item.titulo}</h2><p>{item.mensaje}</p>
      {item.evidencias?.map((e, i) => <p key={i}>{e.etiqueta}: {String(e.valor ?? "")}</p>)}
      <form onSubmit={(event) => save(event, item.id)} className="space-y-3">
        <label className="block">Profesional revisor<input required minLength={2} maxLength={160} className="block w-full rounded border p-2" value={revisor} onChange={(e) => setRevisor(e.target.value)} /></label>
        <label className="block">Observación<textarea required minLength={10} maxLength={1000} className="block w-full rounded border p-2" value={motivo} onChange={(e) => setMotivo(e.target.value)} /></label>
        <button disabled={busy} className="rounded border px-4 py-2">Guardar observación sin desbloquear</button>
      </form>
      {item.observaciones?.map((note, i) => <p key={i} className="text-sm">{note.revisor}: {note.motivo} · {note.fecha}</p>)}
    </article>)}
    {(status || error) && <p role="status">{status || error}</p>}
    <div className="flex gap-4"><button onClick={onBack} className="rounded border p-3">Revisar archivos</button><button onClick={onRetry} className="rounded bg-slate-900 p-3 text-white">Reintentar análisis</button></div>
  </main>;
}
