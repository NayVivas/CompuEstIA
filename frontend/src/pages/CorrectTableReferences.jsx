import { useState } from 'react';
const key = r => `${r.sha256}:${r.pagina}:${r.fila}`;
export default function CorrectTableReferences({ audit, onConfirm, onSource }) {
  const rows = (audit.incidencias || [])
    .filter(issue => issue.codigo === 'referencia_duplicada_cuadro' && !issue.resuelta)
    .flatMap(issue => issue.fuentes.map(source => ({
      ...source,
      issueId: issue.id,
      referencia_original: source.texto,
    })));
  const [values, setValues] = useState(() => Object.fromEntries(rows.map(r => [key(r), r.referencia_correcta || r.referencia_original])));
  const [reviewer, setReviewer] = useState(''); const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  if (!rows.length) return null;
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      if (reviewer.trim().length < 2 || reason.trim().length < 10) throw new Error('Indicá revisor y un motivo de al menos 10 caracteres.');
      const corrections = rows.filter(r => values[key(r)].trim().toUpperCase() !== r.referencia_original).map(r => ({ sha256: r.sha256, pagina: r.pagina, fila: r.fila, referencia_original: r.referencia_original, referencia_correcta: values[key(r)].trim().toUpperCase(), revisor: reviewer.trim(), motivo: reason.trim() }));
      if (!corrections.length) throw new Error('Modificá la referencia de la fila incorrecta antes de guardar. Por ejemplo, cambiá únicamente la segunda aparición de F12 a F13.');
      await onConfirm(corrections);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <details open className="rounded border-2 border-blue-300 bg-white p-4"><summary className="font-bold">Corregir referencias del cuadro</summary>
    <form onSubmit={submit} className="mt-3 space-y-3">
      <p>Modificá únicamente la fila equivocada. La corrección se aplica a los datos del cálculo, conserva el rótulo original y debe superar la revalidación del backend.</p>
      {rows.map(r => <label key={key(r)} className="block rounded border p-3">{r.archivo} · página {r.pagina} · fila {r.fila} · original: {r.referencia_original}
        <button type="button" className="ml-3 text-blue-800 underline" onClick={() => onSource(r,r.issueId)}>Ver fila en el plano</button>
        <input aria-label={`Referencia de fila ${r.fila}, página ${r.pagina}`} required maxLength={30} className="mt-2 block rounded border p-2" value={values[key(r)]} onChange={e => setValues(v => ({ ...v,[key(r)]:e.target.value }))} />
      </label>)}
      <label className="block">Profesional revisor<input required autoComplete="name" minLength={2} maxLength={160} className="block w-full rounded border p-2" value={reviewer} onChange={e => setReviewer(e.target.value)} /></label>
      <label className="block">Motivo y evidencia de la corrección<textarea required autoComplete="off" minLength={10} maxLength={1000} placeholder="Ej.: La segunda fila F12 corresponde a F13 según la planta de fundaciones." className="block w-full rounded border p-2" value={reason} onChange={e => setReason(e.target.value)} /></label>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <button disabled={busy} className="rounded bg-blue-800 px-4 py-2 text-white">{busy ? 'Validando…' : 'Guardar corrección y revalidar'}</button>
    </form>
  </details>;
}
