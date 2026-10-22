import { useEffect, useRef, useState } from 'react';
import { getDocument, GlobalWorkerOptions, Util } from 'pdfjs-dist';
import worker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { fileHash, getPdf, storePdf, saveDecision } from '../services/documentReviewStorage';
GlobalWorkerOptions.workerSrc = worker;
const groups = ['disciplinas', 'roles_documentales', 'contenidos'];
const label = value => String(value).replaceAll('_', ' ');
const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/\s+/g, ' ').trim();

function PdfPage({ file, number, evidence }) {
  const canvas = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [status, setStatus] = useState('Preparando página…');
  useEffect(() => {
    let cancelled = false; let loading; let render;
    async function draw() {
      try {
        const data = new Uint8Array(await file.arrayBuffer());
        if (cancelled) return;
        loading = getDocument({ data });
        const pdf = await loading.promise;
        const page = await pdf.getPage(number);
        if (cancelled) return;
        const original = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({ scale: Math.min(1000 / original.width, 2) * zoom });
        const element = canvas.current; element.width = viewport.width; element.height = viewport.height;
        const context = element.getContext('2d');
        render = page.render({ canvasContext: context, viewport }); await render.promise;
        const content = await page.getTextContent();
        if (cancelled) return;
        let count = 0;
        const needle = normalize(evidence || '');
        if (needle) for (const item of content.items) {
          if (!item.str || !normalize(item.str).includes(needle)) continue;
          const m = Util.transform(viewport.transform, item.transform);
          const angle = Math.atan2(m[1], m[0]);
          const h = Math.hypot(m[2], m[3]);
          context.save(); context.translate(m[4], m[5]); context.rotate(angle);
          context.fillStyle = 'rgba(255,180,0,0.35)'; context.fillRect(0, -h, item.width * viewport.scale, h * 1.25); context.restore(); count++;
        }
        setStatus(needle ? (count ? `${count} coincidencias resaltadas. El resaltado abarca el fragmento de texto que contiene la evidencia.` : 'Sin coincidencia directa: el texto puede estar dividido en fragmentos. Revisá visualmente la página.') : 'Seleccioná una evidencia para resaltarla.');
      } catch (error) { if (!cancelled) setStatus(`No se pudo mostrar el PDF: ${error.message}`); }
    }
    draw();
    return () => { cancelled = true; render?.cancel(); loading?.destroy(); };
  }, [file, number, evidence, zoom]);
  return <div><div className="flex items-center gap-3"><button type="button" onClick={() => setZoom(z => Math.max(.5, z - .25))}>− Zoom</button><button type="button" onClick={() => setZoom(z => Math.min(3, z + .25))}>+ Zoom</button><span>{number}: {status}</span></div><div className="max-h-[70vh] overflow-auto border bg-slate-100"><canvas ref={canvas} /></div></div>;
}

export default function DocumentPageEditor({ doc, page, files, projectId, onSaved, onClose, technicalOnly = false, initialEvidence = '' }) {
  const [file, setFile] = useState(null);
  const [error, setError] = useState('');
  const [evidence, setEvidence] = useState(initialEvidence);
  const [busy, setBusy] = useState(false);
  const [values, setValues] = useState(() => Object.fromEntries(groups.map(k => [k, (page.clasificacion?.objetivos?.[k]?.etiquetas || []).join(', ')])));
  const [reviewer, setReviewer] = useState(page.decision_documental?.revisor || '');
  const [reason, setReason] = useState('');
  const [viewed, setViewed] = useState(false);
  const proposals = (page.clasificacion_automatica || page.clasificacion)?.propuestas_modelo_sin_evidencia || {};
  useEffect(() => {
    let active = true;
    (async () => {
      let found = await getPdf(doc.sha256);
      if (!found) for (const candidate of files || []) if (await fileHash(candidate) === doc.sha256) { found = candidate; break; }
      if (active) setFile(found || null);
      if (found) await storePdf(doc.sha256, found);
    })().catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [doc.sha256, files]);
  async function attach(candidate) {
    if (!candidate) return;
    try { await storePdf(doc.sha256, candidate); setFile(candidate); setError(''); } catch (e) { setError(e.message); }
  }
  async function save(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const objetivos = Object.fromEntries(groups.map(k => [k, [...new Set(values[k].split(',').map(x => x.trim().toLowerCase().replace(/\s+/g, '_')).filter(Boolean))]]));
      if (Object.values(objetivos).some(items => !items.length || items.length > 50 || items.some(x => x.length > 100))) throw new Error('Completá las tres categorías con etiquetas válidas.');
      if (!viewed || !file) throw new Error('Abrí el PDF original y confirmá que revisaste la página.');
      if (reviewer.trim().length < 2 || reason.trim().length < 10) throw new Error('Indicá tu nombre y un motivo de al menos 10 caracteres.');
      const saved = await saveDecision(projectId, { sha256: doc.sha256, pagina: page.pagina, objetivos, revisor: reviewer.trim(), motivo: reason.trim(), fecha: new Date().toISOString() }, page.decision_documental?.version || 0);
      onSaved(saved);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <section className="space-y-4 rounded-xl border-2 border-blue-300 bg-slate-50 p-4" aria-label="Revisión de página">
    <div className="flex justify-between"><h3 className="text-xl font-bold">{doc.nombre} · página {page.pagina}</h3><button type="button" disabled={busy} onClick={onClose}>Cerrar visor</button></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {file ? <PdfPage file={file} number={page.pagina} evidence={evidence} /> : <label>Seleccioná el PDF original para verlo y verificar su identidad:<input type="file" accept="application/pdf" onChange={e => attach(e.target.files[0])} /></label>}
    <div className="flex flex-wrap gap-2">{(page.clasificacion?.evidencias || []).map((e,i) => <button type="button" key={i} className="rounded border bg-white p-2 text-sm" onClick={() => setEvidence(e.texto)}>{label(e.etiqueta)}: {e.texto}</button>)}</div>
    {technicalOnly ? <p>Esta vista muestra la evidencia técnica. Cambiar las categorías de la página no corrige referencias, cotas ni armaduras del plano.</p> : <form onSubmit={save} className="space-y-3">
      <p>Editá las categorías, separadas por comas. Conservarlas confirma la clasificación. Las sugerencias que no incorpores quedarán fuera de la clasificación revisada.</p>
      {groups.map(k => <label key={k} className="block font-semibold">{label(k)}<input className="mt-1 block w-full rounded border bg-white p-2 font-normal" required value={values[k]} onChange={e => setValues(v => ({ ...v, [k]: e.target.value }))} />{proposals[k]?.map(item => <button key={item} type="button" className="m-1 rounded border px-2 text-sm" onClick={() => setValues(v => ({ ...v, [k]: [...new Set([...v[k].split(',').map(x => x.trim()).filter(Boolean), item])].join(', ') }))}>Agregar {label(item)}</button>)}</label>)}
      <label className="block">Revisor<input required minLength={2} maxLength={160} className="block w-full rounded border p-2" value={reviewer} onChange={e => setReviewer(e.target.value)} /></label>
      <label className="block">Motivo de la decisión<textarea required minLength={10} maxLength={1000} className="block w-full rounded border p-2" value={reason} onChange={e => setReason(e.target.value)} /></label>
      <label className="flex gap-2"><input type="checkbox" checked={viewed} onChange={e => setViewed(e.target.checked)} required />Revisé esta página del PDF. Esta decisión valida la clasificación, no las cantidades.</label>
      <button disabled={busy || !file} className="rounded bg-blue-800 px-4 py-2 text-white">{busy ? 'Guardando…' : 'Guardar decisión'}</button>
    </form>}
    {!!page.decision_documental?.historial?.length && <details><summary>Historial de decisiones</summary><ul>{page.decision_documental.historial.map((h,i) => <li key={i} className="my-2">{h.fecha} · {h.revisor}: {h.motivo}<pre className="whitespace-pre-wrap text-xs">{JSON.stringify(h.objetivos, null, 2)}</pre></li>)}</ul></details>}
  </section>;
}
