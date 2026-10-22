import CorrectTableReferences from './CorrectTableReferences';
import { useState } from 'react';
import { saveTechnicalNote } from '../services/documentReviewStorage';
const label = value => String(value).replaceAll('_', ' ');

const sourceKey = source => [
  source.sha256,
  source.pagina,
  source.fila || '',
  source.texto || '',
  JSON.stringify(source.dimensiones_m || []),
  JSON.stringify(source.barras || []),
  source.estribo?.texto_original || '',
  source.referencia_correcta || '',
].join(':');

function sourceDescription(source) {
  const parts = [`${source.archivo} · página ${source.pagina}`];
  if (source.fila) parts.push(`fila ${source.fila}`);
  if (source.texto) parts.push(source.texto);
  return parts.join(' · ');
}

function SourceEntry({ source, issueId, onSource }) {
  return <li className="rounded border border-slate-200 bg-slate-50 p-3">
    <button
      type="button"
      className="text-left font-semibold text-blue-800 underline"
      onClick={() => onSource(source, issueId)}
    >
      Ver en el plano: {sourceDescription(source)}
    </button>
    {source.referencia_correcta && <p className="mt-2">Corrección aplicada: {source.texto} → {source.referencia_correcta}. {source.revisor}: {source.motivo}</p>}
    {source.dimensiones_m && <p className="mt-2">Sección candidata: {source.dimensiones_m.join(' × ')} m</p>}
    {source.barras && <p className="mt-2">Barras: {source.barras.map(bar => `${bar.cantidad} Ø ${bar.diametro_pulgadas}″`).join(' + ')}</p>}
    {source.estribo && <p>Estribo: {source.estribo.texto_original}</p>}
  </li>;
}

function SourceList({ issue, onSource }) {
  const sources = [...new Map((issue.fuentes || []).map(source => [sourceKey(source), source])).values()];
  const visible = sources.slice(0, 3);
  const hidden = sources.slice(3);
  const pages = new Set(sources.map(source => `${source.sha256}:${source.pagina}`)).size;
  if (!sources.length) return null;
  return <div className="space-y-2">
    <p className="text-sm font-semibold text-slate-700">
      {sources.length} {sources.length === 1 ? 'evidencia' : 'evidencias'} en {pages} {pages === 1 ? 'página' : 'páginas'}
    </p>
    <ul className="space-y-2">
      {visible.map(source => <SourceEntry key={sourceKey(source)} source={source} issueId={issue.id} onSource={onSource} />)}
    </ul>
    {!!hidden.length && <details className="rounded border border-slate-200 bg-white p-3">
      <summary className="cursor-pointer font-semibold text-blue-900">Ver las otras {hidden.length} evidencias</summary>
      <ul className="mt-3 space-y-2">
        {hidden.map(source => <SourceEntry key={sourceKey(source)} source={source} issueId={issue.id} onSource={onSource} />)}
      </ul>
    </details>}
  </div>;
}

function NoteForm({ issue, stored, projectId, onSaved }) {
  const [name, setName] = useState(''); const [reason, setReason] = useState('');
  const [status, setStatus] = useState(''); const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault(); setBusy(true); setStatus('');
    try {
      if (name.trim().length < 2 || reason.trim().length < 10) throw new Error('Completá revisor y una observación de al menos 10 caracteres.');
      const record = await saveTechnicalNote(projectId, issue.id, { revisor: name.trim(), motivo: reason.trim() }, stored?.version || 0);
      onSaved(record); setReason(''); setStatus('Observación guardada. La inconsistencia sigue pendiente.');
    } catch (e) { setStatus(e.message); } finally { setBusy(false); }
  }
  return <details><summary>Documentar revisión técnica</summary>
    <form onSubmit={save} className="mt-3 space-y-2">
      <label className="block">Revisor<input required autoComplete="name" minLength={2} maxLength={160} className="block w-full rounded border p-2" value={name} onChange={e => setName(e.target.value)} /></label>
      <label className="block">Observación<textarea required autoComplete="off" minLength={10} maxLength={1000} placeholder="Describí qué verificaste y qué falta resolver." className="block w-full rounded border p-2" value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={busy} className="rounded border px-3 py-2">Guardar observación sin resolver</button>
    </form>{status && <p role="status">{status}</p>}
    {stored?.historial?.map((h,i) => <p key={i} className="mt-2 text-sm">{h.fecha} · {h.revisor}: {h.motivo}</p>)}
  </details>;
}

function ResolutionForm({ issue, audit, onResolve }) {
  const supportedActions = new Set([
    'reasignar_referencia_detalle',
    'seleccionar_fuente_columna',
    'definir_seccion_columna',
  ]);
  const hasSupportedAction = (issue.opciones_resolucion || [])
    .some(action => supportedActions.has(action));
  const mapping = issue.codigo === 'columna_sin_detalle_localizado';
  const manualSection = issue.codigo === 'seccion_columna_no_interpretable';
  const candidates = (audit.catalogos?.detalles_columnas || []).filter(source => source.compatible_motor && source.referencia !== issue.referencia);
  const alternatives = issue.fuentes || [];
  const options = mapping ? candidates : alternatives;
  const [selected, setSelected] = useState('0');
  const [reviewer, setReviewer] = useState('');
  const [reason, setReason] = useState('');
  const [dimension1, setDimension1] = useState('');
  const [dimension2, setDimension2] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  if (!hasSupportedAction) return null;
  if (!options.length) return null;
  async function submit(event) {
    event.preventDefault(); setStatus(''); setBusy(true);
    try {
      if (reviewer.trim().length < 2 || reason.trim().length < 10) throw new Error('Completá revisor y fundamento técnico de al menos 10 caracteres.');
      const source = options[Number(selected)];
      const resolution = mapping ? {
        accion: 'reasignar_referencia_detalle', incidencia_id: issue.id,
        sha256: source.sha256, pagina: source.pagina,
        referencia_original: source.referencia, referencia_correcta: issue.referencia,
        revisor: reviewer.trim(), motivo: reason.trim(),
      } : manualSection ? {
        accion: 'definir_seccion_columna', incidencia_id: issue.id,
        referencia: issue.referencia, sha256: source.sha256, pagina: source.pagina,
        dimension_1_m: Number(dimension1), dimension_2_m: Number(dimension2),
        revisor: reviewer.trim(), motivo: reason.trim(),
      } : {
        accion: 'seleccionar_fuente_columna', incidencia_id: issue.id,
        campo: issue.codigo === 'secciones_diferentes' ? 'seccion' : 'armadura',
        referencia: issue.referencia, sha256: source.sha256, pagina: source.pagina,
        revisor: reviewer.trim(), motivo: reason.trim(),
      };
      await onResolve(resolution);
    } catch (error) { setStatus(error.message); } finally { setBusy(false); }
  }
  const selectedSource = options[Number(selected)];
  return <details className="rounded border border-blue-200 bg-blue-50 p-3">
    <summary className="cursor-pointer font-semibold">Resolver esta inconsistencia y revalidar</summary>
    <form onSubmit={submit} className="mt-3 space-y-3">
      <label className="block">{mapping ? `Detalle que realmente corresponde a ${issue.referencia}` : manualSection ? 'Detalle revisado' : 'Fuente válida para este elemento y nivel'}
        <select className="mt-1 block w-full rounded border p-2" value={selected} onChange={event => setSelected(event.target.value)}>
          {options.map((source, index) => <option value={index} key={`${source.sha256}:${source.pagina}:${index}`}>
            {mapping ? `${source.referencia} · ` : ''}{source.archivo} · página {source.pagina}
            {source.dimensiones_m ? ` · ${source.dimensiones_m.join(' × ')} m` : ''}
          </option>)}
        </select>
      </label>
      {mapping && <p className="text-sm">Se reinterpretará solo este rótulo del detalle como <strong>{issue.referencia}</strong>. El PDF original y su texto quedan intactos.</p>}
      {!mapping && selectedSource && <div className="rounded border border-blue-100 bg-white p-3 text-sm">
        <strong>Fuente seleccionada:</strong> {sourceDescription(selectedSource)}
        {selectedSource.dimensiones_m && <p>Sección: {selectedSource.dimensiones_m.join(' × ')} m</p>}
        {selectedSource.barras && <p>Barras: {selectedSource.barras.map(bar => `${bar.cantidad} Ø ${bar.diametro_pulgadas}″`).join(' + ')}</p>}
        {selectedSource.estribo && <p>Estribo: {selectedSource.estribo.texto_original}</p>}
      </div>}
      {manualSection && <div className="grid gap-3 sm:grid-cols-2">
        <label>Dimensión 1 (m)<input required type="number" min="0.05" max="5" step="0.001" className="mt-1 block w-full rounded border p-2" value={dimension1} onChange={event => setDimension1(event.target.value)} /></label>
        <label>Dimensión 2 (m)<input required type="number" min="0.05" max="5" step="0.001" className="mt-1 block w-full rounded border p-2" value={dimension2} onChange={event => setDimension2(event.target.value)} /></label>
      </div>}
      <label className="block">Profesional revisor<input required autoComplete="name" minLength={2} maxLength={160} className="mt-1 block w-full rounded border p-2" value={reviewer} onChange={event => setReviewer(event.target.value)} /></label>
      <label className="block">Fundamento técnico<textarea required autoComplete="off" minLength={10} maxLength={1000} placeholder="Indicá qué plano, nivel, cota o detalle respalda esta decisión." className="mt-1 block w-full rounded border p-2" value={reason} onChange={event => setReason(event.target.value)} /></label>
      <button disabled={busy} className="rounded bg-blue-800 px-3 py-2 text-white">{busy ? 'Revalidando…' : 'Aplicar decisión y volver a comprobar'}</button>
    </form>
    {status && <p role="alert" className="mt-2 text-red-700">{status}</p>}
  </details>;
}

function IssueCard({ issue, audit, notes, projectId, onSource, onSaved, ready, onResolve }) {
  return <article className="space-y-3 rounded-lg border bg-white p-4">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <h3 className="text-lg font-bold">{issue.titulo}</h3>
      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${issue.resuelta ? 'bg-green-100 text-green-800' : issue.bloqueo === 'familia' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-900'}`}>
        {issue.resuelta ? 'Resuelta' : issue.bloqueo === 'familia' ? 'Bloquea la familia' : 'Excluye este elemento'}
      </span>
    </div>
    <p className="text-sm">{label(issue.severidad)} · {issue.familia ? label(issue.familia) : 'general'}</p>
    <p>{issue.mensaje}</p>
    <SourceList issue={issue} onSource={onSource} />
    <p><strong>Acción recomendada:</strong> {issue.accion_recomendada}</p>
    {issue.resolucion && <p className="rounded bg-green-50 p-3 text-sm"><strong>Decisión aplicada:</strong> {issue.resolucion.revisor} · {issue.resolucion.motivo}</p>}
    {ready && onResolve && !issue.resuelta && issue.opciones_resolucion?.length > 0 && <ResolutionForm issue={issue} audit={audit} onResolve={onResolve} />}
    {ready && !issue.resuelta && issue.opciones_resolucion?.includes('corregir_fila_cuadro') && (
      <p className="rounded border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
        Esta inconsistencia se resuelve únicamente en el panel <strong>Corregir referencias del cuadro</strong> mostrado arriba. Cambiá solo la fila incorrecta y guardá la corrección.
      </p>
    )}
    {ready && !issue.resuelta && <NoteForm issue={issue} stored={notes.find(note => note.issueId === issue.id)} projectId={projectId} onSaved={onSaved} />}
  </article>;
}

export default function TechnicalFindings({ audit, notes = [], projectId, onSource, onSaved, ready, onCorrectRows, onResolve }) {
  if (!audit) return <section className="rounded border border-amber-300 p-4"><h2 className="font-bold">Inconsistencias técnicas</h2><p>Este análisis es anterior a los controles técnicos preliminares. Volvé a cargar los PDF en un análisis nuevo para ejecutarlos.</p></section>;
  const pending = (audit.incidencias || []).filter(issue => !issue.resuelta);
  const resolved = (audit.incidencias || []).filter(issue => issue.resuelta);
  return <section className="space-y-4 rounded-xl border-2 border-amber-300 bg-amber-50 p-5">
    <h2 className="text-2xl font-bold">Inconsistencias y observaciones técnicas</h2>
    <p>{pending.length} observaciones pendientes · {audit.resumen?.bloqueos_familia || 0} bloquean una familia · {audit.resumen?.elementos_excluidos || 0} excluyen solo elementos afectados.</p>
    {audit.politica_calculo && <p className="rounded bg-white p-3 text-sm">{audit.politica_calculo.criterio}</p>}
    <p className="text-sm">{audit.alcance}</p>
    {!audit.incidencias?.length && <p>No se registraron hallazgos en los controles ejecutados. Consultá su cobertura; esto no valida el proyecto.</p>}
    {ready && onCorrectRows && <CorrectTableReferences key={JSON.stringify(audit.revisiones_aplicadas || [])} audit={audit} onConfirm={onCorrectRows} onSource={onSource} />}
    {pending.map(issue => <IssueCard key={issue.id} issue={issue} audit={audit} notes={notes} projectId={projectId} onSource={onSource} onSaved={onSaved} ready={ready} onResolve={onResolve} />)}
    {!!resolved.length && <details className="rounded-lg border border-green-200 bg-green-50 p-4">
      <summary className="cursor-pointer font-bold text-green-900">Correcciones aplicadas y revalidadas ({resolved.length})</summary>
      <div className="mt-4 space-y-3">
        {resolved.map(issue => <IssueCard key={issue.id} issue={issue} audit={audit} notes={notes} projectId={projectId} onSource={onSource} onSaved={onSaved} ready={ready} onResolve={onResolve} />)}
      </div>
    </details>}
    <details><summary>Controles ejecutados y limitaciones de lectura</summary><ul className="list-disc pl-5">{audit.controles?.map((c,i) => <li key={i}>{c.archivo} · página {c.pagina ?? '—'} · {label(c.control)}: {label(c.estado)}. {c.motivo}</li>)}</ul></details>
  </section>;
}
