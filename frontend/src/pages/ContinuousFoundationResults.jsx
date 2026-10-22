function amount(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "—";
}

export default function ContinuousFoundationResults({
  results,
  error,
  onBack,
  onNewAnalysis,
  onDownload,
}) {
  if (!results) {
    return (
      <main className="mx-auto max-w-5xl p-8">
        <p className="rounded-2xl border bg-white p-8 text-center">
          {error || "No hay resultados disponibles."}
        </p>
      </main>
    );
  }

  const rows = results.cimientos_corridos_detalle || [];
  const alerts = results.alertas_analisis || [];
  const excluded = results.elementos_excluidos || [];

  return (
    <main className="mx-auto max-w-[1450px] space-y-7 px-5 py-10 sm:px-8">
      <header className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[.18em] text-blue-700">Cómputo revisado</p>
          <h1 className="mt-2 text-4xl font-bold">Cimientos corridos</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">
            Cantidades geométricas calculadas con secciones y longitudes confirmadas por el profesional.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-lg border bg-white px-4 py-3 text-sm font-bold" type="button" onClick={onBack}>Volver a análisis</button>
          <button className="rounded-lg border bg-white px-4 py-3 text-sm font-bold" type="button" onClick={onDownload}>Descargar JSON</button>
          <button className="rounded-lg bg-slate-900 px-4 py-3 text-sm font-bold text-white" type="button" onClick={onNewAnalysis}>Nuevo análisis</button>
        </div>
      </header>

      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</p>}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <article className="rounded-2xl border bg-white p-5">
          <p className="text-xs font-bold uppercase text-slate-500">Longitud total</p>
          <p className="mt-2 text-3xl font-bold">{amount(results.longitud_total_cimientos_corridos_m)} m</p>
        </article>
        <article className="rounded-2xl border bg-white p-5">
          <p className="text-xs font-bold uppercase text-slate-500">Volumen geométrico</p>
          <p className="mt-2 text-3xl font-bold">{amount(results.volumen_cimientos_corridos_m3, 3)} m³</p>
        </article>
        <article className="rounded-2xl border bg-white p-5">
          <p className="text-xs font-bold uppercase text-slate-500">Tipos incluidos</p>
          <p className="mt-2 text-3xl font-bold">{results.cantidad_tipos_fundacion ?? rows.length}</p>
        </article>
        <article className="rounded-2xl border bg-white p-5">
          <p className="text-xs font-bold uppercase text-slate-500">Material clasificado</p>
          <p className="mt-2 text-lg font-bold">
            {rows.every((row) => row.material) ? "Confirmado" : "Parcial o pendiente"}
          </p>
        </article>
      </section>

      <section className="overflow-hidden rounded-2xl border bg-white">
        <div className="border-b px-5 py-4">
          <h2 className="text-xl font-bold">Detalle por tipo</h2>
        </div>
        <div className="overflow-auto">
          <table className="min-w-[950px] w-full text-left text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Superior</th>
                <th className="px-4 py-3">Base</th>
                <th className="px-4 py-3">Altura</th>
                <th className="px-4 py-3">Área</th>
                <th className="px-4 py-3">Longitud</th>
                <th className="px-4 py-3">Volumen</th>
                <th className="px-4 py-3">Material</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row) => (
                <tr key={row.identificador || row.referencia}>
                  <td className="px-4 py-3 font-bold">{row.referencia}</td>
                  <td className="px-4 py-3">{amount(row.ancho_superior_m)} m</td>
                  <td className="px-4 py-3">{amount(row.ancho_base_m)} m</td>
                  <td className="px-4 py-3">{amount(row.altura_m)} m</td>
                  <td className="px-4 py-3">{amount(row.area_seccion_m2, 3)} m²</td>
                  <td className="px-4 py-3">{amount(row.longitud_m)} m</td>
                  <td className="px-4 py-3 font-semibold">{amount(row.volumen_total_m3, 3)} m³</td>
                  <td className="px-4 py-3">{row.material_nombre || "Sin confirmar"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {!!excluded.length && <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
        <h2 className="text-xl font-bold text-amber-950">Tipos sin longitud incluida en este cómputo</h2>
        <p className="mt-1 text-sm text-amber-900">El detalle puede aportar los anchos y la altura de sección, pero sin un recorrido longitudinal verificado estos tipos no aportan volumen al total.</p>
        <ul className="mt-3 space-y-2 text-sm text-amber-950">
          {excluded.map((item) => <li key={item.id}><strong>{item.referencia}:</strong> {item.motivo_exclusion}</li>)}
        </ul>
      </section>}

      {!!alerts.length && (
        <section className="space-y-3">
          <h2 className="text-xl font-bold">Pendientes y alcance</h2>
          {alerts.map((alert) => (
            <article key={alert.id} className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
              <h3 className="font-bold text-amber-950">{alert.titulo}</h3>
              <p className="mt-1 text-sm text-amber-900">{alert.mensaje}</p>
              {alert.accion_recomendada && <p className="mt-2 text-sm font-semibold text-amber-950">Acción: {alert.accion_recomendada}</p>}
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
