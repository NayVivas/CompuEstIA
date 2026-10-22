const numberFormatter = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 3,
});

const TOLERANCIA = 0.001;

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

function agruparPorReferencia(items) {
  const groups = new Map();

  items.forEach((item) => {
    const referencia = item.referencia;

    if (!groups.has(referencia)) {
      groups.set(referencia, {
        referencia,
        cantidadFundaciones: toNumber(
          item.cantidad_fundaciones
        ),
        rows: [],
      });
    }

    groups.get(referencia).rows.push(item);
  });

  return Array.from(groups.values());
}

function verificarFila(item) {
  const cantidadIndicada =
    toNumber(item.cantidad_indicada) || 1;

  const cantidadPosiciones = toNumber(
    item.cantidad_posiciones
  );

  const cantidadBarrasCalculada =
    cantidadPosiciones * cantidadIndicada;

  const metrosPorFundacionCalculados =
    toNumber(item.cantidad_barras) *
    toNumber(item.longitud_barra_m);

  const metrosTotalesCalculados =
    toNumber(item.metros_por_fundacion) *
    toNumber(item.cantidad_fundaciones);

  const pesoPorFundacionCalculado =
    toNumber(item.metros_por_fundacion) *
    toNumber(item.peso_unitario_kg_m);

  const pesoTotalCalculado =
    toNumber(item.metros_totales) *
    toNumber(item.peso_unitario_kg_m);

  const separacionRealCalculada =
    cantidadPosiciones > 1
      ? toNumber(
          item.longitud_disponible_m
        ) /
        (cantidadPosiciones - 1)
      : 0;

  const separacionRealCm =
    toNumber(item.separacion_real_m) * 100;

  const separacionCumple =
    separacionRealCm <=
    toNumber(item.separacion_cm) +
      TOLERANCIA;

  const comprobaciones = {
    cantidadBarras: coinciden(
      cantidadBarrasCalculada,
      item.cantidad_barras
    ),
    metrosPorFundacion: coinciden(
      metrosPorFundacionCalculados,
      item.metros_por_fundacion
    ),
    metrosTotales: coinciden(
      metrosTotalesCalculados,
      item.metros_totales
    ),
    pesoPorFundacion: coinciden(
      pesoPorFundacionCalculado,
      item.peso_por_fundacion_kg
    ),
    pesoTotal: coinciden(
      pesoTotalCalculado,
      item.peso_total_kg
    ),
    separacionReal: coinciden(
      separacionRealCalculada,
      item.separacion_real_m
    ),
    separacionCumple,
  };

  const verificada = Object.values(
    comprobaciones
  ).every(Boolean);

  return {
    verificada,
    comprobaciones,
    calculados: {
      cantidadBarras: cantidadBarrasCalculada,
      metrosPorFundacion:
        metrosPorFundacionCalculados,
      metrosTotales: metrosTotalesCalculados,
      pesoPorFundacion:
        pesoPorFundacionCalculado,
      pesoTotal: pesoTotalCalculado,
      separacionReal:
        separacionRealCalculada,
    },
  };
}

function ArmadurasDetail({
  items = [],
  totalGeneral = 0,
}) {
  const grupos =
    agruparPorReferencia(items);

  const pesoDetalle = items.reduce(
    (total, item) =>
      total +
      toNumber(item.peso_total_kg),
    0
  );

  const metrosTotales = items.reduce(
    (total, item) =>
      total +
      toNumber(item.metros_totales),
    0
  );

  const barrasTotales = items.reduce(
    (total, item) =>
      total +
      toNumber(item.cantidad_barras) *
        toNumber(
          item.cantidad_fundaciones
        ),
    0
  );

  const diferenciaCalculada =
    toNumber(totalGeneral) - pesoDetalle;

  const diferencia =
    Math.abs(diferenciaCalculada) <=
    TOLERANCIA
      ? 0
      : diferenciaCalculada;

  const pesoCoincide = coinciden(
    pesoDetalle,
    totalGeneral
  );

  const filasVerificadas = items.every(
    (item) =>
      verificarFila(item).verificada
  );

  const todoVerificado =
    pesoCoincide && filasVerificadas;

  if (items.length === 0) {
    return (
      <div className="p-10 text-center">
        <p className="text-sm font-semibold text-slate-500">
          No se recibió el detalle de armaduras.
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
        <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-center">
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
                ? "El detalle de acero coincide con el total general"
                : "Existen diferencias en el detalle de acero"}
            </h3>
          </div>

          <div className="grid grid-cols-2 gap-5 text-right sm:grid-cols-4">
            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Peso del detalle
              </span>

              <strong className="mt-1 block text-sm text-ink">
                {formatNumber(
                  pesoDetalle,
                  "kg"
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
                  "kg"
                )}
              </strong>
            </div>

            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Metros de barras
              </span>

              <strong className="mt-1 block text-sm text-ink">
                {formatNumber(
                  metrosTotales,
                  "m"
                )}
              </strong>
            </div>

            <div>
              <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                Diferencia
              </span>

              <strong
                className={`mt-1 block text-sm ${
                  pesoCoincide
                    ? "text-emerald-700"
                    : "text-red-700"
                }`}
              >
                {formatNumber(
                  diferencia,
                  "kg"
                )}
              </strong>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-emerald-200/70 pt-4">
          <span className="rounded-full bg-white px-3 py-1.5 text-[9px] font-extrabold text-slate-600">
            {items.length} especificaciones
          </span>

          <span className="rounded-full bg-white px-3 py-1.5 text-[9px] font-extrabold text-slate-600">
            {grupos.length} tipos de fundación
          </span>

          <span className="rounded-full bg-white px-3 py-1.5 text-[9px] font-extrabold text-slate-600">
            {formatNumber(
              barrasTotales
            )} barras colocadas
          </span>
        </div>
      </div>

      {/* CRITERIOS */}

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
            Cantidad de barras
          </span>

          <strong className="mt-2 block text-xs text-ink">
            Posiciones × cantidad indicada
          </strong>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
            Metros totales
          </span>

          <strong className="mt-2 block text-xs text-ink">
            Barras × longitud × fundaciones
          </strong>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
            Peso total
          </span>

          <strong className="mt-2 block text-xs text-ink">
            Metros totales × kg/m
          </strong>
        </div>
      </div>

      {/* GRUPOS POR FUNDACIÓN */}

      <div className="mt-5 space-y-3">
        {grupos.map((grupo, groupIndex) => {
          const pesoTotalGrupo =
            grupo.rows.reduce(
              (total, item) =>
                total +
                toNumber(
                  item.peso_total_kg
                ),
              0
            );

          const pesoPorFundacion =
            grupo.rows.reduce(
              (total, item) =>
                total +
                toNumber(
                  item.peso_por_fundacion_kg
                ),
              0
            );

          const metrosPorFundacion =
            grupo.rows.reduce(
              (total, item) =>
                total +
                toNumber(
                  item.metros_por_fundacion
                ),
              0
            );

          const metrosGrupo =
            grupo.rows.reduce(
              (total, item) =>
                total +
                toNumber(
                  item.metros_totales
                ),
              0
            );

          const barrasPorFundacion =
            grupo.rows.reduce(
              (total, item) =>
                total +
                toNumber(
                  item.cantidad_barras
                ),
              0
            );

          const barrasGrupo =
            barrasPorFundacion *
            grupo.cantidadFundaciones;

          const niveles = [
            ...new Set(
              grupo.rows.map(
                (item) => item.nivel
              )
            ),
          ];

          const grupoVerificado =
            grupo.rows.every(
              (item) =>
                verificarFila(item)
                  .verificada
            ) &&
            coinciden(
              pesoPorFundacion *
                grupo.cantidadFundaciones,
              pesoTotalGrupo
            );

          const elementos = Array.from(
            {
              length: Math.max(
                0,
                Math.trunc(
                  grupo.cantidadFundaciones
                )
              ),
            },
            (_, index) => ({
              identificador: `${
                grupo.referencia
              }-${String(index + 1).padStart(
                2,
                "0"
              )}`,
              pesoKg: pesoPorFundacion,
              metros: metrosPorFundacion,
              barras: barrasPorFundacion,
            })
          );

          return (
            <details
              key={grupo.referencia}
              className="group overflow-hidden rounded-2xl border border-slate-200 bg-white"
              open={groupIndex === 0}
            >
              <summary className="flex cursor-pointer list-none flex-col justify-between gap-4 p-5 transition hover:bg-slate-50 xl:flex-row xl:items-center">
                <div className="flex items-center gap-3">
                  <span className="flex h-11 min-w-11 items-center justify-center rounded-xl bg-slate-950 px-3 text-xs font-extrabold text-white">
                    {grupo.referencia}
                  </span>

                  <div>
                    <strong className="block text-sm font-extrabold text-ink">
                      {
                        grupo.cantidadFundaciones
                      }{" "}
                      fundaciones
                    </strong>

                    <span className="mt-0.5 block text-[10px] font-semibold text-slate-400">
                      {grupo.rows.length} especificaciones ·{" "}
                      {niveles.join(" / ")}
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-5 xl:justify-end">
                  <div>
                    <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                      Barras/fund.
                    </span>

                    <strong className="mt-1 block text-sm text-ink">
                      {formatNumber(
                        barrasPorFundacion
                      )}
                    </strong>
                  </div>

                  <div>
                    <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                      Peso/fund.
                    </span>

                    <strong className="mt-1 block text-sm text-ink">
                      {formatNumber(
                        pesoPorFundacion,
                        "kg"
                      )}
                    </strong>
                  </div>

                  <div>
                    <span className="block text-[9px] font-extrabold uppercase text-slate-400">
                      Peso total
                    </span>

                    <strong className="mt-1 block text-sm text-accent-dark">
                      {formatNumber(
                        pesoTotalGrupo,
                        "kg"
                      )}
                    </strong>
                  </div>

                  <span
                    className={`rounded-full px-3 py-1.5 text-[9px] font-extrabold uppercase ${
                      grupoVerificado
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {grupoVerificado
                      ? "Verificado"
                      : "Revisar"}
                  </span>

                  <span className="text-slate-400 transition group-open:rotate-180">
                    ▼
                  </span>
                </div>
              </summary>

              <div className="border-t border-slate-100 bg-slate-50/60 p-5 sm:p-6">
                {/* RESUMEN DEL GRUPO */}

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {[
                    {
                      label: "Barras colocadas",
                      value: formatNumber(
                        barrasGrupo
                      ),
                    },
                    {
                      label: "Metros por fundación",
                      value: formatNumber(
                        metrosPorFundacion,
                        "m"
                      ),
                    },
                    {
                      label: "Metros totales",
                      value: formatNumber(
                        metrosGrupo,
                        "m"
                      ),
                    },
                    {
                      label: "Peso total",
                      value: formatNumber(
                        pesoTotalGrupo,
                        "kg"
                      ),
                    },
                  ].map((metric) => (
                    <div
                      key={metric.label}
                      className="rounded-xl border border-slate-200 bg-white p-4"
                    >
                      <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                        {metric.label}
                      </span>

                      <strong className="mt-2 block text-base text-ink">
                        {metric.value}
                      </strong>
                    </div>
                  ))}
                </div>

                {/* TABLA DE ESPECIFICACIONES */}

                <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <div className="border-b border-slate-100 px-4 py-3">
                    <h4 className="text-xs font-extrabold text-ink">
                      Especificaciones de armadura
                    </h4>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[1550px] border-collapse">
                      <thead>
                        <tr className="bg-slate-50">
                          {[
                            "Nivel",
                            "Dirección",
                            "Diámetro",
                            "Separación indicada",
                            "Separación real",
                            "Barras/fund.",
                            "Long. barra",
                            "Metros/fund.",
                            "Fundaciones",
                            "Barras totales",
                            "Metros totales",
                            "Peso kg/m",
                            "Peso/fund.",
                            "Peso total",
                            "Control",
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
                        {grupo.rows.map(
                          (item, rowIndex) => {
                            const control =
                              verificarFila(
                                item
                              );

                            const barrasTotalesFila =
                              toNumber(
                                item.cantidad_barras
                              ) *
                              toNumber(
                                item.cantidad_fundaciones
                              );

                            return (
                              <tr
                                key={`${item.referencia}-${item.nivel}-${item.direccion}-${rowIndex}`}
                                className="hover:bg-accent/[0.025]"
                              >
                                <td className="border-b border-slate-100 px-4 py-3 text-xs font-extrabold text-ink">
                                  {item.nivel}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {item.direccion}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  Ø{" "}
                                  {
                                    item.diametro_pulgadas
                                  }
                                  &quot;
                                  <span className="ml-1 text-[9px] text-slate-400">
                                    (
                                    {formatNumber(
                                      item.diametro_mm,
                                      "mm"
                                    )}
                                    )
                                  </span>
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {formatNumber(
                                    item.separacion_cm,
                                    "cm"
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {formatNumber(
                                    toNumber(
                                      item.separacion_real_m
                                    ) * 100,
                                    "cm"
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {
                                    item.cantidad_barras
                                  }
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {formatNumber(
                                    item.longitud_barra_m,
                                    "m"
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {formatNumber(
                                    item.metros_por_fundacion,
                                    "m"
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {
                                    item.cantidad_fundaciones
                                  }
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {formatNumber(
                                    barrasTotalesFila
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {formatNumber(
                                    item.metros_totales,
                                    "m"
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {formatNumber(
                                    item.peso_unitario_kg_m,
                                    "kg/m"
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
                                  {formatNumber(
                                    item.peso_por_fundacion_kg,
                                    "kg"
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3 text-xs font-extrabold text-ink">
                                  {formatNumber(
                                    item.peso_total_kg,
                                    "kg"
                                  )}
                                </td>

                                <td className="border-b border-slate-100 px-4 py-3">
                                  <span
                                    className={`rounded-full px-2.5 py-1 text-[9px] font-extrabold ${
                                      control.verificada
                                        ? "bg-emerald-50 text-emerald-700"
                                        : "bg-red-50 text-red-700"
                                    }`}
                                  >
                                    {control.verificada
                                      ? "OK"
                                      : "Revisar"}
                                  </span>
                                </td>
                              </tr>
                            );
                          }
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* FÓRMULAS */}

                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <span className="text-[9px] font-extrabold uppercase text-slate-400">
                      Metros por fundación
                    </span>

                    <strong className="mt-2 block text-xs text-ink">
                      Cantidad de barras × longitud
                    </strong>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <span className="text-[9px] font-extrabold uppercase text-slate-400">
                      Metros totales
                    </span>

                    <strong className="mt-2 block text-xs text-ink">
                      Metros/fundación × cantidad
                    </strong>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <span className="text-[9px] font-extrabold uppercase text-slate-400">
                      Peso
                    </span>

                    <strong className="mt-2 block text-xs text-ink">
                      Metros totales × peso kg/m
                    </strong>
                  </div>
                </div>

                {/* CONTROL INDIVIDUAL */}

                <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
                  <h4 className="text-xs font-extrabold text-ink">
                    Control individual en obra
                  </h4>

                  <p className="mt-1 text-[10px] leading-5 text-slate-400">
                    Cada elemento debe verificar estas
                    cantidades de acero. Los identificadores
                    son internos hasta relacionarlos con los
                    ejes del plano.
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
                          <strong className="text-xs text-ink">
                            {
                              elemento.identificador
                            }
                          </strong>

                          <div className="mt-2 grid grid-cols-3 gap-2 text-[9px]">
                            <div>
                              <span className="block text-slate-400">
                                Barras
                              </span>
                              <b className="text-ink">
                                {
                                  elemento.barras
                                }
                              </b>
                            </div>

                            <div>
                              <span className="block text-slate-400">
                                Metros
                              </span>
                              <b className="text-ink">
                                {formatNumber(
                                  elemento.metros,
                                  "m"
                                )}
                              </b>
                            </div>

                            <div>
                              <span className="block text-slate-400">
                                Peso
                              </span>
                              <b className="text-accent-dark">
                                {formatNumber(
                                  elemento.pesoKg,
                                  "kg"
                                )}
                              </b>
                            </div>
                          </div>

                          <span className="mt-2 block text-[9px] text-slate-400">
                            Medición de campo pendiente
                          </span>
                        </div>
                      )
                    )}
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

export default ArmadurasDetail;