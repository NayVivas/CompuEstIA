const numberFormatter = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 5,
});

const TOLERANCIA = 0.00001;

function toNumber(value) {
  const numericValue = Number(value);

  return Number.isFinite(numericValue)
    ? numericValue
    : 0;
}

function formatNumber(value, unit = "") {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "—";
  }

  return `${numberFormatter.format(numericValue)}${
    unit ? ` ${unit}` : ""
  }`;
}

function coinciden(firstValue, secondValue) {
  return (
    Math.abs(
      toNumber(firstValue) -
        toNumber(secondValue)
    ) <= TOLERANCIA
  );
}

function crearElementos(item) {
  const cantidad = Math.max(
    0,
    Math.trunc(toNumber(item.cantidad))
  );

  return Array.from(
    { length: cantidad },
    (_, index) => ({
      identificador: `${item.referencia}-${String(
        index + 1
      ).padStart(2, "0")}`,
      volumen_m3: toNumber(
        item.volumen_unitario
      ),
    })
  );
}

function HormigonDetail({
  items = [],
  totalGeneral = 0,
}) {
  const totalDetalle = items.reduce(
    (total, item) =>
      total +
      toNumber(item.volumen_total),
    0
  );

  const diferenciaCalculada =
    toNumber(totalGeneral) - totalDetalle;

  const diferencia =
    Math.abs(diferenciaCalculada) <= TOLERANCIA
      ? 0
      : diferenciaCalculada;

  const detalleCoincide = coinciden(
    totalDetalle,
    totalGeneral
  );

  const filasVerificadas = items.every(
    (item) => {
      const volumenCalculado =
        toNumber(item.x) *
        toNumber(item.y) *
        toNumber(item.h);

      const totalCalculado =
        toNumber(item.volumen_unitario) *
        toNumber(item.cantidad);

      return (
        coinciden(
          volumenCalculado,
          item.volumen_unitario
        ) &&
        coinciden(
          totalCalculado,
          item.volumen_total
        )
      );
    }
  );

  const todoVerificado =
    detalleCoincide && filasVerificadas;

  if (items.length === 0) {
    return (
      <div className="p-10 text-center">
        <p className="text-sm font-semibold text-slate-500">
          No se recibió el detalle de hormigón.
        </p>
      </div>
    );
  }

  return (
    <div className="min-w-0 p-5 sm:p-7">
      {/* CONTROL GENERAL */}

      <div
        className={`rounded-2xl border p-5 ${
          todoVerificado
            ? "border-emerald-200 bg-emerald-50"
            : "border-red-200 bg-red-50"
        }`}
      >
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <span
              className={`text-[10px] font-extrabold uppercase tracking-[0.14em] ${
                todoVerificado
                  ? "text-emerald-700"
                  : "text-red-700"
              }`}
            >
              Control de trazabilidad
            </span>

            <h3
              className={`mt-1 text-base font-extrabold ${
                todoVerificado
                  ? "text-emerald-950"
                  : "text-red-950"
              }`}
            >
              {todoVerificado
                ? "Los volúmenes coinciden con el total general"
                : "Existen diferencias en los volúmenes"}
            </h3>
          </div>

          <div className="grid grid-cols-3 gap-5 text-right">
            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Suma del detalle
              </span>

              <strong className="mt-1 block text-sm text-ink">
                {formatNumber(
                  totalDetalle,
                  "m³"
                )}
              </strong>
            </div>

            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Total general
              </span>

              <strong className="mt-1 block text-sm text-ink">
                {formatNumber(
                  totalGeneral,
                  "m³"
                )}
              </strong>
            </div>

            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Diferencia
              </span>

              <strong
                className={`mt-1 block text-sm ${
                  detalleCoincide
                    ? "text-emerald-700"
                    : "text-red-700"
                }`}
              >
                {formatNumber(
                  diferencia,
                  "m³"
                )}
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* FUNDACIONES */}

      <div className="mt-5 space-y-3">
        {items.map((item, index) => {
          const volumenCalculado =
            toNumber(item.x) *
            toNumber(item.y) *
            toNumber(item.h);

          const totalCalculado =
            toNumber(item.volumen_unitario) *
            toNumber(item.cantidad);

          const volumenCoincide = coinciden(
            volumenCalculado,
            item.volumen_unitario
          );

          const totalCoincide = coinciden(
            totalCalculado,
            item.volumen_total
          );

          const filaVerificada =
            volumenCoincide && totalCoincide;

          const elementos =
            crearElementos(item);

          const sumaElementos =
            elementos.reduce(
              (total, elemento) =>
                total +
                elemento.volumen_m3,
              0
            );

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
                      {formatNumber(item.x)} ×{" "}
                      {formatNumber(item.y)} ×{" "}
                      {formatNumber(item.h)} m
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-6 sm:justify-end">
                  <div>
                    <span className="block text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      Volumen unitario
                    </span>

                    <strong className="mt-1 block text-sm text-ink">
                      {formatNumber(
                        item.volumen_unitario,
                        "m³"
                      )}
                    </strong>
                  </div>

                  <div>
                    <span className="block text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      Volumen total
                    </span>

                    <strong className="mt-1 block text-sm text-accent-dark">
                      {formatNumber(
                        item.volumen_total,
                        "m³"
                      )}
                    </strong>
                  </div>

                  <span
                    className={`rounded-full px-3 py-1.5 text-[9px] font-extrabold uppercase ${
                      filaVerificada
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {filaVerificada
                      ? "Verificado"
                      : "Revisar"}
                  </span>

                  <span className="text-slate-400 transition group-open:rotate-180">
                    ▼
                  </span>
                </div>
              </summary>

              <div className="border-t border-slate-100 bg-slate-50/60 p-5 sm:p-6">
                {/* DIMENSIONES */}

                <div className="grid gap-3 sm:grid-cols-3">
                  {[
                    {
                      label: "Dimensión X",
                      value: item.x,
                    },
                    {
                      label: "Dimensión Y",
                      value: item.y,
                    },
                    {
                      label: "Altura h",
                      value: item.h,
                    },
                  ].map((dimension) => (
                    <div
                      key={dimension.label}
                      className="rounded-xl border border-slate-200 bg-white p-4"
                    >
                      <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                        {dimension.label}
                      </span>

                      <strong className="mt-2 block text-lg text-ink">
                        {formatNumber(
                          dimension.value,
                          "m"
                        )}
                      </strong>
                    </div>
                  ))}
                </div>

                {/* FÓRMULAS */}

                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      Volumen unitario
                    </span>

                    <strong className="mt-2 block text-sm text-ink">
                      V = X × Y × h
                    </strong>

                    <span className="mt-1 block text-xs text-slate-500">
                      {formatNumber(item.x)} ×{" "}
                      {formatNumber(item.y)} ×{" "}
                      {formatNumber(item.h)}
                    </span>

                    <div className="mt-3 border-t border-slate-100 pt-3">
                      <span className="text-[10px] text-slate-500">
                        Calculado:
                      </span>{" "}
                      <strong className="text-xs text-ink">
                        {formatNumber(
                          volumenCalculado,
                          "m³"
                        )}
                      </strong>

                      <span className="mx-2 text-slate-300">
                        |
                      </span>

                      <span className="text-[10px] text-slate-500">
                        Backend:
                      </span>{" "}
                      <strong className="text-xs text-ink">
                        {formatNumber(
                          item.volumen_unitario,
                          "m³"
                        )}
                      </strong>
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                      Volumen total
                    </span>

                    <strong className="mt-2 block text-sm text-ink">
                      V total = V unitario × cantidad
                    </strong>

                    <span className="mt-1 block text-xs text-slate-500">
                      {formatNumber(
                        item.volumen_unitario
                      )}{" "}
                      × {item.cantidad}
                    </span>

                    <div className="mt-3 border-t border-slate-100 pt-3">
                      <span className="text-[10px] text-slate-500">
                        Calculado:
                      </span>{" "}
                      <strong className="text-xs text-ink">
                        {formatNumber(
                          totalCalculado,
                          "m³"
                        )}
                      </strong>

                      <span className="mx-2 text-slate-300">
                        |
                      </span>

                      <span className="text-[10px] text-slate-500">
                        Backend:
                      </span>{" "}
                      <strong className="text-xs text-ink">
                        {formatNumber(
                          item.volumen_total,
                          "m³"
                        )}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* ELEMENTOS INDIVIDUALES */}

                <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
                  <h4 className="text-xs font-extrabold text-ink">
                    Control individual en obra
                  </h4>

                  <p className="mt-1 text-[10px] leading-5 text-slate-400">
                    Cada elemento debe verificar las mismas
                    dimensiones y el mismo volumen unitario.
                    Los identificadores son internos hasta
                    relacionarlos con los ejes del plano.
                  </p>

                  <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {elementos.map(
                      (elemento) => (
                        <div
                          key={
                            elemento.identificador
                          }
                          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <strong className="text-xs text-ink">
                              {
                                elemento.identificador
                              }
                            </strong>

                            <span className="text-[10px] font-extrabold text-accent-dark">
                              {formatNumber(
                                elemento.volumen_m3,
                                "m³"
                              )}
                            </span>
                          </div>

                          <span className="mt-1 block text-[9px] text-slate-400">
                            Medición de campo pendiente
                          </span>
                        </div>
                      )
                    )}
                  </div>

                  <div className="mt-4 flex flex-wrap justify-between gap-3 border-t border-slate-100 pt-4">
                    <span className="text-[10px] font-semibold text-slate-500">
                      Suma de elementos individuales
                    </span>

                    <strong className="text-xs text-ink">
                      {formatNumber(
                        sumaElementos,
                        "m³"
                      )}
                    </strong>
                  </div>
                </div>
              </div>
            </details>
          );
        })}
      </div>
    </div>
  );
}

export default HormigonDetail;