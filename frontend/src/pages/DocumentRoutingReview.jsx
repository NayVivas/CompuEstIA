import { useEffect, useRef, useState } from "react";

import DocumentPageEditor from './DocumentPageEditor';
import TechnicalFindings from './TechnicalFindings';
import { getDecisions, applyDecisions, getTechnicalNotes, getPdf, fileHash, getRowCorrections, storeRowCorrections, getTechnicalResolutions, storeTechnicalResolutions } from '../services/documentReviewStorage';
import { iniciarAnalisis } from '../services/api';
const EMPTY_FILES = [];
const label = (value) => String(value).replaceAll("_", " ");
const textSource = (method) => ({
  ocr_tesseract: "texto recuperado por OCR",
  texto_nativo_mas_ocr: "texto nativo complementado por OCR",
  texto_nativo: "texto nativo",
}[method] || "texto leído");
function download(review) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(review, null, 2)], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = "clasificacion_documental.json";
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function DocumentRoutingReview({ review: originalReview, error, onConfirm, onBack, projectId, files = EMPTY_FILES, onReviewUpdated }) {
  const [review, setReview] = useState(originalReview);
  const [editing, setEditing] = useState(null);
  const [notice, setNotice] = useState('');
  const [loadError, setLoadError] = useState('');
  const [ready, setReady] = useState(false);
  const technicalViewer = useRef(null);
  const [technicalSource, setTechnicalSource] = useState(null);
  const [technicalNotes, setTechnicalNotes] = useState([]);
  const [technicalResolutions, setTechnicalResolutions] = useState([]);
  useEffect(() => { if (technicalSource) technicalViewer.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [technicalSource]);
  useEffect(() => {
    let active = true;
    Promise.all([getDecisions(projectId), getTechnicalNotes(projectId), getTechnicalResolutions(projectId)]).then(([decisions, notes, resolutions]) => { if (active) { setReview(applyDecisions(originalReview, decisions)); setTechnicalNotes(notes); setTechnicalResolutions(resolutions); setReady(true); } }).catch(e => { if (active) setLoadError(e.message); });
    return () => { active = false; };
  }, [originalReview, projectId]);
  async function correctRows(corrections) {
    const originals = [];
    for (const doc of review.documentos) {
      let original = await getPdf(doc.sha256);
      if (!original) for (const candidate of files) if (await fileHash(candidate) === doc.sha256) { original = candidate; break; }
      if (!original) throw new Error(`Recargá el PDF original ${doc.nombre} antes de revalidar sus datos.`);
      originals.push(new File([original], doc.nombre, { type: 'application/pdf' }));
    }
    const previous = await getRowCorrections(projectId);
    const previousTechnical = await getTechnicalResolutions(projectId);
    const response = await iniciarAnalisis(
      originals,
      null,
      null,
      projectId,
      false,
      corrections,
      previousTechnical
    );
    if (!response.enrutamiento) throw new Error('No se pudo revalidar la corrección. No se guardó.');
    await storeRowCorrections(projectId, corrections, review.documentos.map(d => d.sha256), previous);
    const appliedTechnical = response.enrutamiento.auditoria_tecnica?.resoluciones_aplicadas || [];
    const savedTechnical = await storeTechnicalResolutions(
      projectId,
      appliedTechnical,
      review.documentos.map(d => d.sha256),
      previousTechnical
    );
    setTechnicalResolutions(savedTechnical);
    setReview(response.enrutamiento); onReviewUpdated?.(response.enrutamiento);
    const discarded = response.enrutamiento.auditoria_tecnica?.resoluciones_obsoletas?.length || 0;
    setNotice(discarded
      ? `Corrección guardada y revalidada. Se retiraron ${discarded} decisiones anteriores que ya no correspondían a conflictos vigentes.`
      : 'Corrección guardada y revalidada. Se volverá a aplicar a estos mismos PDF al calcular.');
  }
  async function resolveTechnical(resolution) {
    const originals = [];
    for (const doc of review.documentos) {
      let original = await getPdf(doc.sha256);
      if (!original) for (const candidate of files) if (await fileHash(candidate) === doc.sha256) { original = candidate; break; }
      if (!original) throw new Error(`Recargá el PDF original ${doc.nombre} antes de revalidar sus datos.`);
      originals.push(new File([original], doc.nombre, { type: 'application/pdf' }));
    }
    const previous = await getTechnicalResolutions(projectId);
    const sameTarget = item => item.accion === resolution.accion && (
      resolution.accion === 'seleccionar_fuente_columna'
        ? item.campo === resolution.campo && item.referencia === resolution.referencia
        : resolution.accion === 'definir_seccion_columna'
          ? item.referencia === resolution.referencia
        : item.sha256 === resolution.sha256 && item.pagina === resolution.pagina && item.referencia_original === resolution.referencia_original
    );
    let next = previous.filter(item => !sameTarget(item));
    if (resolution.accion === 'reasignar_referencia_detalle') {
      next = next.filter(item => !(item.accion === 'seleccionar_fuente_columna' && item.referencia === resolution.referencia_original));
    }
    next.push(resolution);
    const response = await iniciarAnalisis(originals, null, null, projectId, false, null, next);
    if (!response.enrutamiento) throw new Error('No se pudo revalidar la decisión. No se guardó.');
    const applied = response.enrutamiento.auditoria_tecnica?.resoluciones_aplicadas || [];
    const saved = await storeTechnicalResolutions(projectId, applied, review.documentos.map(d => d.sha256), previous);
    setTechnicalResolutions(saved);
    setReview(response.enrutamiento); onReviewUpdated?.(response.enrutamiento);
    const appliedCurrent = applied.some(item => item.incidencia_id === resolution.incidencia_id);
    setNotice(appliedCurrent
      ? 'Decisión técnica guardada, aplicada y revalidada contra los mismos PDF.'
      : 'La incidencia ya no estaba vigente. Se actualizó la revisión y se retiró la selección anterior para permitir continuar.');
  }
  function saved(decision) {
    setReview(current => applyDecisions(current, [decision]));
    setEditing(null); setNotice('Decisión guardada. Se conservará al cerrar y se aplicará al reanalizar este PDF en el mismo proyecto.');
  }
  // La clasificación es automática. Por defecto se muestran únicamente las
  // páginas que de verdad necesitan una decisión humana.
  const [onlyPending, setOnlyPending] = useState(true);
  const documents = review.documentos || [];
  const summary = review.resumen || {};
  const model = review.diagnostico_modelo;
  const calculationAllowed = review.auditoria_tecnica?.politica_calculo?.permite_calculo_parcial !== false;
  const allPages = documents.flatMap((document) => document.paginas || []);
  const pendingPages = allPages.filter((page) => page.requiere_revision);
  const visibleDocuments = documents
    .map((document) => ({
      ...document,
      paginasVisibles: (document.paginas || []).filter(
        (page) => !onlyPending || page.requiere_revision
      ),
    }))
    .filter((document) => document.paginasVisibles.length);
  return <main className="mx-auto max-w-6xl space-y-6 p-6 sm:p-8">
    <header className="space-y-3">
      <h1 className="text-3xl font-bold">Clasificación de la documentación</h1>
      <p>Cada página se analiza por separado. Podés cargar un PDF con varias páginas o varios archivos, sin asignarles funciones previamente.</p>
      <p className="font-semibold">{documents.length} archivos · {summary.paginas ?? allPages.length} páginas · {summary.paginas_clasificadas ?? 0} clasificadas automáticamente · {pendingPages.length} que requieren intervención</p>
      {pendingPages.length === 0 ? <p className="rounded border border-green-200 bg-green-50 p-3 font-semibold text-green-900">No tenés que clasificar las páginas una por una. La clasificación automática no dejó conflictos documentales; podés continuar al paso de fuentes y cómputo.</p> : <p className="rounded border border-amber-200 bg-amber-50 p-3 text-amber-950">Revisá solamente las {pendingPages.length} páginas mostradas abajo. Las demás ya fueron clasificadas por el sistema.</p>}
      <p>{allPages.filter(p => p.decision_documental).length} páginas corregidas por un profesional · {allPages.filter(p => Object.values(p.clasificacion?.propuestas_modelo_sin_evidencia || {}).some(items => items.length)).length} con sugerencias informativas que no bloquean.</p>
      <div className="flex flex-wrap gap-3">
        <button className="rounded border px-4 py-2" onClick={onBack}>Cargar otros documentos</button>
        <button className="rounded border px-4 py-2" onClick={() => download({ ...review, observaciones_tecnicas: technicalNotes })}>Descargar clasificación</button>
        <button className="rounded border px-4 py-2" type="button" onClick={() => setOnlyPending(value => !value)}>{onlyPending ? 'Mostrar todas las páginas (opcional)' : 'Ocultar páginas sin conflictos'}</button>
      </div>
    </header>
    {model?.estado === "disponible" && <p className="rounded border border-green-200 bg-green-50 p-3 text-green-900">EXP22 multimodal operativo. Cada decisión combina el texto aprendido por EXP19 con posición, aspecto renderizado y geometría vectorial del plano; las fuentes de cada etiqueta quedan visibles para auditoría.</p>}
    {model?.estado === "degradado" && <details open className="rounded border border-amber-200 bg-amber-50 p-3"><summary>EXP22 funciona en modo degradado</summary><p>{model.tipo}: {model.mensaje}</p><p>{model.accion}</p><p>El análisis conserva reglas, posición, imagen y geometría del PDF, pero perdió la señal aprendida de EXP19. Las páginas dudosas deben revisarse.</p></details>}
    {model?.estado === "error" && <details open className="rounded border border-amber-200 bg-amber-50 p-3"><summary>El clasificador no está disponible para este análisis</summary><p>{model.tipo}: {model.mensaje}</p><p>{model.accion}</p></details>}
    {notice && <p role="status" className="rounded bg-green-50 p-3 text-green-800">{notice}</p>}
    {loadError && <p role="alert" className="text-red-700">No se pudo recuperar el historial de revisiones: {loadError}. Recargá la página antes de editar.</p>}
    {!ready && !loadError && <p>Cargando decisiones guardadas…</p>}
    {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-700">{error}</p>}
    <div ref={technicalViewer}>{technicalSource && (() => {
      const doc = documents.find(d => d.sha256 === technicalSource.sha256);
      const page = doc?.paginas?.find(p => p.pagina === technicalSource.pagina);
      return doc && page ? <div className="space-y-2 rounded-xl border-2 border-blue-400 bg-blue-50 p-3">
        <p className="font-semibold text-blue-950">Fuente de la inconsistencia seleccionada. Revisá el plano y luego cerrá el visor para continuar con la decisión técnica.</p>
        <DocumentPageEditor key={`${technicalSource.issueId}:${doc.sha256}:${page.pagina}:${technicalSource.fila || ''}`} doc={doc} page={page} files={files} projectId={projectId} technicalOnly initialEvidence={technicalSource.texto} onClose={() => setTechnicalSource(null)} />
      </div> : <p className="rounded border border-red-200 bg-red-50 p-3 text-red-800">No se encontró la página fuente dentro de los documentos de este análisis.</p>;
    })()}</div>
    <TechnicalFindings audit={review.auditoria_tecnica} notes={technicalNotes} resolutions={technicalResolutions} projectId={projectId} ready={ready} onCorrectRows={correctRows} onResolve={resolveTechnical}
      onSaved={record => setTechnicalNotes(current => [...current.filter(n => n.issueId !== record.issueId), record])}
      onSource={(source, issueId) => { setTechnicalSource({ ...source, issueId }); setEditing(null); }} />
    {onlyPending && !visibleDocuments.length && <p className="rounded-xl border border-slate-200 bg-white p-5 text-slate-700">No hay páginas pendientes de clasificación. Las páginas automáticas están ocultas para que puedas concentrarte en continuar el cómputo.</p>}
    {visibleDocuments.map((doc) => <section key={doc.documento_id} className="space-y-4 rounded-2xl border bg-white p-5">
      <h2 className="text-xl font-bold">{doc.nombre} <span className="text-sm font-normal">· {doc.paginas?.length || 0} páginas</span></h2>
      {doc.advertencias?.map((text, i) => <p key={i} className="text-amber-800">{text}</p>)}
      {doc.paginasVisibles.map((page) => <article key={page.pagina} className="space-y-2 rounded-xl border border-slate-200 p-4">
        <h3 className="font-bold">Página {page.pagina} · {label(page.estado || "pendiente")}</h3>
        <p className="text-sm text-slate-500">
          {page.caracteres || 0} caracteres de {textSource(page.metodo_extraccion_texto)} · rotación {page.rotacion || 0}°
        </p>
        {page.clasificacion?.caracteristicas_resumen && <p className="text-xs text-slate-500">Evidencia de página: {page.clasificacion.caracteristicas_resumen.palabras || 0} palabras · {page.clasificacion.caracteristicas_resumen.objetos_vectoriales || 0} objetos vectoriales · compatibilidad técnica {Math.round((page.clasificacion.caracteristicas_resumen.compatibilidad_plano_tecnico || 0) * 100)}%</p>}
        <p className="text-xs text-slate-500">{page.decision_documental ? `Clasificación corregida por ${page.decision_documental.revisor}: ${page.decision_documental.motivo}` : page.requiere_revision ? 'La clasificación automática necesita una decisión profesional en esta página.' : 'Clasificación automática aceptada para el flujo; corregila solo si observás un error.'}</p>
        {page.clasificacion?.motivos_revision?.map((m,i) => <p key={i} className="text-amber-800">{m}</p>)}
        <button disabled={!ready} className="rounded bg-blue-800 px-3 py-2 text-white" onClick={() => { setEditing(`${doc.sha256}:${page.pagina}`); setNotice(''); }}>{page.requiere_revision ? 'Resolver clasificación pendiente' : 'Inspeccionar o corregir (opcional)'}</button>
        {editing === `${doc.sha256}:${page.pagina}` && <DocumentPageEditor key={editing} doc={doc} page={page} files={files} projectId={projectId} onSaved={saved} onClose={() => setEditing(null)} />}
        <dl className="grid gap-3 sm:grid-cols-3">{["disciplinas", "roles_documentales", "contenidos"].map((key) => <div key={key}><dt className="text-xs font-bold uppercase text-slate-500">{label(key)}</dt><dd>{page.clasificacion?.objetivos?.[key]?.etiquetas?.map(label).join(", ") || "Sin identificar"}</dd></div>)}</dl>
        {page.advertencias?.map((message, i) => <p key={i} className="text-sm text-amber-800">{message}</p>)}
        {!!page.clasificacion?.evidencias?.length && <details className="text-sm"><summary>Ver evidencias de la detección automática</summary><ul className="list-disc space-y-1 pl-5">{page.clasificacion.evidencias.map((e, i) => <li key={i}><strong>{label(e.etiqueta)}</strong>: «{e.texto}»{e.origen === "patron_contextual" ? " (inferencia por contexto)" : ""}</li>)}</ul></details>}
        {!!page.clasificacion?.decisiones_multimodales?.length && <details className="text-sm"><summary>Cómo decidió EXP22</summary><ul className="list-disc space-y-1 pl-5">{page.clasificacion.decisiones_multimodales.map((decision, i) => <li key={`${decision.objetivo}-${decision.etiqueta}-${i}`}><strong>{label(decision.objetivo)} · {label(decision.etiqueta)}</strong>: {label(decision.decision)} · fuerza explicable {Math.round((decision.fuerza || 0) * 100)}% · {decision.fuentes?.map(label).join(", ") || "sin fuente registrada"}</li>)}</ul><p className="mt-2 text-xs text-slate-500">La fuerza explicable resume evidencia acumulada; no es una probabilidad estadística.</p></details>}
        {Object.values(page.clasificacion?.propuestas_modelo_sin_evidencia || {}).some((items) => items.length) && <details className="text-sm text-amber-800"><summary>Sugerencias informativas no corroboradas</summary><p>EXP19 sugirió estas etiquetas, pero las demás modalidades no aportaron apoyo suficiente. No bloquean la página ni habilitan cantidades. Podés incorporarlas o descartarlas al revisar la clasificación.</p><ul className="list-disc pl-5">{Object.entries(page.clasificacion.propuestas_modelo_sin_evidencia).filter(([, items]) => items.length).map(([key, items]) => <li key={key}>{label(key)}: {items.map(label).join(", ")}</li>)}</ul></details>}
        {page.error_modelo && !model && <details className="text-sm"><summary>El modelo local falló: ver diagnóstico</summary><p className="break-words">{page.error_modelo.tipo}: {page.error_modelo.mensaje}</p><p>Se usaron reglas de texto como respaldo. No son predicciones del modelo.</p></details>}
        {!!page.muestra_texto && <details className="text-sm"><summary>Texto leído en esta página</summary><pre className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-3">{page.muestra_texto}</pre></details>}
      </article>)}
    </section>)}
    <section className="space-y-3 rounded-xl border bg-slate-50 p-5">
      <h2 className="font-bold">Cómo continúa el cómputo</h2>
      <ol className="list-decimal space-y-1 pl-5"><li>La aplicación clasifica todas las páginas y solo deriva dudas reales.</li><li>El sistema selecciona las fuentes estructurales y detecta inconsistencias concretas.</li><li>El profesional confirma dimensiones o corrige los datos señalados, no todas las páginas.</li><li>Se ejecuta el motor y se revisan las cantidades y exclusiones antes de aprobar.</li></ol>
      <p>Corregir una referencia resuelve ese dato; no valida otras familias. El motor actual necesita fuentes inequívocas y no calcula todas las familias del proyecto.</p>
      <h2 className="font-bold">Cómputo disponible</h2>
      <p>Clasificar los planos no significa que todas sus disciplinas tengan un motor de cantidades implementado.</p>
      {review.capacidad_computo && <div className={`rounded border p-3 ${review.capacidad_computo.estado === 'tipologia_no_implementada' ? 'border-amber-300 bg-amber-50 text-amber-950' : 'border-blue-200 bg-blue-50 text-blue-950'}`}>
        <strong>{label(review.capacidad_computo.estado)}.</strong> {review.capacidad_computo.motivo}
        {review.capacidad_computo.alcance_si_revisa_geometria && <p className="mt-1 text-sm">{review.capacidad_computo.alcance_si_revisa_geometria}</p>}
      </div>}
      {review.motor?.disponible ? <>
        <p className="rounded border border-green-200 bg-green-50 p-3 font-semibold text-green-900">Las fuentes necesarias fueron seleccionadas automáticamente. No hace falta clasificar cada página; continuá con la revisión de datos o el cómputo.</p>
        <p>Fuentes seleccionadas para {review.motor.nombre.toLowerCase()}:</p>
        <ul className="list-disc space-y-2 pl-5">{Object.entries(review.fuentes_por_rol || {}).map(([rol, source]) => <li key={rol}>
          <strong>{label(rol)}:</strong> {source.archivo}, {source.paginas?.length > 1 ? `páginas ${source.paginas.join(', ')} (conjunto complementario)` : `página ${source.pagina}`}
          {source.modo_geometria && <> · modo {label(source.modo_geometria)}</>}
          {!!source.tipologias?.length && <> · {source.tipologias.map(label).join(', ')}</>}
          {!!source.motivos?.length && <ul className="ml-5 list-disc text-sm text-slate-600">{source.motivos.map((reason, index) => <li key={index}>{reason}</li>)}</ul>}
        </li>)}</ul>
        {!calculationAllowed && <p className="rounded border border-red-200 bg-red-50 p-3 text-red-800">Resolvé primero las inconsistencias que bloquean la familia. Los conflictos de un elemento aislado no impiden un cómputo parcial.</p>}
        {onConfirm ? <button disabled={!calculationAllowed} className="rounded bg-slate-900 px-4 py-3 text-white disabled:cursor-not-allowed disabled:opacity-50" onClick={onConfirm}>{review.requiere_revision_geometrica ? 'Revisar dimensiones y continuar' : 'Revalidar fuentes y ejecutar cómputo'}</button> : <p>Para calcular, volvé a cargar los documentos originales.</p>}
      </> : <>
        <p>No se ejecutó un cómputo automático. Esto no se resuelve clasificando todas las páginas: el motor no pudo elegir una fuente estructural o no reconoce todavía la tipología. {review.capacidad_computo?.motivo}</p>
        <details open><summary>Diagnóstico exacto de las fuentes</summary><ul className="list-disc pl-5">{review.motor?.motivos?.map((message, i) => <li key={i}>{message}</li>)}</ul></details>
      </>}
      {!!review.motores?.length && <details><summary>Estado de todos los motores</summary><ul className="mt-2 space-y-2">{review.motores.map(engine => <li key={engine.id} className="rounded border bg-white p-2"><strong>{engine.nombre}:</strong> {label(engine.estado)}{engine.motivo ? ` · ${engine.motivo}` : ''}</li>)}</ul></details>}
    </section>
  </main>;
}
