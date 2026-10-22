export default function Processing({ progress = 0, documentCount = 0 }) {
  return <main className="mx-auto flex max-w-3xl flex-col items-center gap-6 px-8 py-20 text-center" aria-busy="true">
    <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-teal-600" aria-hidden="true" />
    <h1 className="text-3xl font-bold">Analizando documentación</h1>
    <p>{documentCount} documento{documentCount === 1 ? "" : "s"} enviado{documentCount === 1 ? "" : "s"}. El servidor revisa el contenido y las fuentes para el cómputo.</p>
    <div className="h-2 w-full overflow-hidden rounded bg-slate-200" aria-hidden="true"><div className="h-full bg-teal-600 transition-all" style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>
    <p className="text-sm text-slate-500" role="status">Indicador de espera estimado. El análisis termina cuando responde el servidor; si encuentra un problema, se abrirá la revisión correspondiente.</p>
  </main>;
}
