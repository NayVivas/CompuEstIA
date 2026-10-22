const numberFormatter = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 3,
});

function formatNumber(value, unit = "") {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "—";
  }

  return `${numberFormatter.format(numericValue)}${
    unit ? ` ${unit}` : ""
  }`;
}

function EncofradoDetail({
  items = [],
  totalGeneral = 0,
}) {
  const totalDetalle = items.reduce(
    (total, item) =>
      total + Number(item.area_total_m2 || 0),
    0
  );

  const diferencia =
    Number(totalGeneral || 0) - totalDetalle;

  const totalCoincide =
    Math.abs(diferencia) < 0.001;

  const filasVerificadas = items.every(
    (item) =>
      !item.comprobaciones ||
      item.comprobaciones.estado === "verificado"
  );

  const verificado =
    totalCoincide && filasVerificadas;

  if (items.length === 0) {
    return (
      <div className="p-10 text-center">
        <p className="text-sm font-semibold text-slate-500">
          No se recibió el detalle de encofrado.
        </p>
      </div>
    );
  }

  return (
    <div className="min-w-0 p-5 sm:p-7">
      <div
        className={`rounded-2xl border p-5 ${
          verificado
            ? "border-emerald-200 bg-emerald-50"
            : "border-red-200 bg-red-50"
        }`}
      >
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <span
              className={`text-[10px] font-extrabold uppercase tracking-[0.14em] ${
                verificado
                  ? "text-emerald-700"
                  : "text-red-700"
              }`}
            >
              Control de trazabilidad
            </span>

            <h3
              className={`mt-1 text-base font-extrabold ${
                verificado
                  ? "text-emerald-950"
                  : "text-red-950"
              }`}
            >
              {verificado
                ? "El detalle coincide con el total general"
                : "El detalle presenta diferencias"}
            </h3>
          </div>

          <div className="grid grid-cols-3 gap-5 text-right">
            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Suma del detalle
              </span>
              <strong className="mt-1 block text-sm text-ink">
                {formatNumber(totalDetalle, "m²")}
              </strong>
            </div>

            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Total general
              </span>
              <strong className="mt-1 block text-sm text-ink">
                {formatNumber(totalGeneral, "m²")}
              </strong>
            </div>

            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Diferencia
              </span>
              <strong
                className={`mt-1 block text-sm ${
                  totalCoincide
                    ? "text-emerald-700"
                    : "text-red-700"
                }`}
              >
                {formatNumber(diferencia, "m²")}
              </strong>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {items.map((item, index) => {
          const dimensiones =
            item.dimensiones_m || {};

          const caras = item.caras || [];
          const elementos = item.elementos || [];
          const formula = item.formula || {};
          const comprobaciones =
            item.comprobaciones || {};

          const filaVerificada =
            comprobaciones.estado === "verificado";

          return (
            <details
              key={item.referencia}
              className="group overflow-hidden rounded-2xl border border-slate-200 bg-white"
              open={index === 0}
            >
              <summary className="flex cursor-pointer list-none flex-col justify-between gap-4 p-5 transition hover:bg-slate-50 sm:flex-row sm:items-center">
                <div className="flex items-center gap-3">
                  <span className="flex h-11 min-w-11 items-center justify-center rounded-xl bg-slate-950 px-3 text-xs font-extrabold text-white">
                    {item.referencia}
                  </span>

                  <div>
                    <strong className="block text-sm font-extrabold text-ink">
                      {item.cantidad} fundaciones
                    </strong>

                    <span className="mt-0.5 block text-[10px] font-semibold text-slate-400">
                      {dimensiones.x !== undefined
                        ? `${formatNumber(
                            dimensiones.x
                          )} × ${formatNumber(
                            dimensiones.y
                          )} × ${formatNumber(
                            dimensiones.h
                          )} m`
                        : "Dimensiones no detalladas"}
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-6 sm:justify-end">
                  <div>
                    <span className="block text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      Unitario
                    </span>

                    <strong className="mt-1 block text-sm text-ink">
                      {formatNumber(
                        item.area_unitaria_m2,
                        "m²"
                      )}
                    </strong>
                  </div>

                  <div>
                    <span className="block text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      Total
                    </span>

                    <strong className="mt-1 block text-sm text-accent-dark">
                      {formatNumber(
                        item.area_total_m2,
                        "m²"
                      )}
                    </strong>
                  </div>

                  <span
                    className={`rounded-full px-3 py-1.5 text-[9px] font-extrabold uppercase ${
                      filaVerificada
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {filaVerificada
                      ? "Verificado"
                      : "Revisar detalle"}
                  </span>

                  <span className="text-slate-400 transition group-open:rotate-180">
                    ▼
                  </span>
                </div>
              </summary>

              <div className="border-t border-slate-100 bg-slate-50/60 p-5 sm:p-6">
                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      Fórmula aplicada
                    </span>

                    <strong className="mt-2 block text-sm text-ink">
                      {formula.expresion ||
                        "2 × (X + Y) × h"}
                    </strong>

                    <span className="mt-1 block text-xs text-slate-500">
                      {formula.sustitucion ||
                        "Sustitución no disponible"}
                    </span>

                    <div className="mt-3 border-t border-slate-100 pt-3">
                      <span className="text-[10px] font-semibold text-slate-500">
                        Resultado:
                      </span>{" "}
                      <strong className="text-xs text-ink">
                        {formatNumber(
                          formula.resultado_m2 ??
                            item.area_unitaria_m2,
                          "m²"
                        )}
                      </strong>
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      Criterio técnico
                    </span>

                    <p className="mt-2 text-xs font-semibold leading-5 text-slate-600">
                      {item.criterio?.descripcion ||
                        "Cuatro caras laterales de la zapata."}
                    </p>

                    <p className="mt-2 text-[10px] leading-5 text-slate-400">
                      No se incluyen la base ni la cara
                      superior.
                    </p>
                  </div>
                </div>

                <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <div className="border-b border-slate-100 px-4 py-3">
                    <h4 className="text-xs font-extrabold text-ink">
                      Desglose por caras
                    </h4>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[650px] border-collapse">
                      <thead>
                        <tr className="bg-slate-50">
                          {[
                            "Cara",
                            "Largo",
                            "Alto",
                            "Operación",
                            "Área",
                            "Incluida",
                          ].map((heading) => (
                            <th
                              key={heading}
                              className="border-b border-slate-100 px-4 py-3 text-left text-[9px] font-extrabold uppercase tracking-wider text-slate-400"
                            >
                              {heading}
                            </th>
                          ))}
                        </tr>
                      </thead>

                      <tbody>
                        {caras.length === 0 ? (
                          <tr>
                            <td
                              className="px-4 py-8 text-center text-xs text-amber-700"
                              colSpan={6}
                            >
                              El backend todavía no entregó
                              el desglose de las cuatro caras.
                            </td>
                          </tr>
                        ) : (
                          caras.map((cara) => (
                            <tr key={cara.cara}>
                              <td className="border-b border-slate-100 px-4 py-3 text-xs font-extrabold text-ink">
                                {cara.cara}
                              </td>

                              <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                {formatNumber(
                                  cara.largo_m,
                                  "m"
                                )}
                              </td>

                              <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                {formatNumber(
                                  cara.alto_m,
                                  "m"
                                )}
                              </td>

                              <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                {cara.sustitucion}
                              </td>

                              <td className="border-b border-slate-100 px-4 py-3 text-xs font-extrabold text-ink">
                                {formatNumber(
                                  cara.area_m2,
                                  "m²"
                                )}
                              </td>

                              <td className="border-b border-slate-100 px-4 py-3">
                                <span
                                  className={`rounded-full px-2.5 py-1 text-[9px] font-extrabold ${
                                    cara.incluida_en_computo
                                      ? "bg-emerald-50 text-emerald-700"
                                      : "bg-slate-100 text-slate-500"
                                  }`}
                                >
                                  {cara.incluida_en_computo
                                    ? "Sí"
                                    : "No"}
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
                  <div>
                    <h4 className="text-xs font-extrabold text-ink">
                      Control individual en obra
                    </h4>

                    <p className="mt-1 text-[10px] leading-5 text-slate-400">
                      Son identificadores internos. La
                      asociación definitiva con ejes o
                      coordenadas se incorporará después.
                    </p>
                  </div>

                  {elementos.length === 0 ? (
                    <p className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-xs text-amber-700">
                      El backend todavía no entregó los
                      elementos individuales.
                    </p>
                  ) : (
                    <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {elementos.map((elemento) => (
                        <div
                          key={elemento.identificador}
                          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <strong className="text-xs text-ink">
                              {elemento.identificador}
                            </strong>

                            <span className="text-[10px] font-extrabold text-accent-dark">
                              {formatNumber(
                                elemento.area_encofrado_esperada_m2,
                                "m²"
                              )}
                            </span>
                          </div>

                          <span className="mt-1 block text-[9px] text-slate-400">
                            {elemento.ubicacion_confirmada
                              ? "Ubicación confirmada"
                              : "Ubicación pendiente"}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </details>
          );
        })}
      </div>
    </div>
  );
}

export default EncofradoDetail;