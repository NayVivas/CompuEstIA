import { useMemo, useState } from "react";

const numberFormatter = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 3,
});

const coordinateFormatter = new Intl.NumberFormat("es-AR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
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

function formatCoordinate(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "—";
  }

  return coordinateFormatter.format(numericValue);
}

function compareReferences(left, right) {
  return String(left).localeCompare(String(right), "es", {
    numeric: true,
    sensitivity: "base",
  });
}

function numericValue(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function SummaryCard({ label, value, detail, tone = "slate" }) {
  const tones = {
    slate: "border-slate-200 bg-white",
    emerald: "border-emerald-200 bg-emerald-50/70",
    amber: "border-amber-200 bg-amber-50/70",
  };

  return (
    <div className={`rounded-2xl border p-4 ${tones[tone] || tones.slate}`}>
      <span className="text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
        {label}
      </span>
      <strong className="mt-2 block font-display text-xl font-bold text-ink">
        {value}
      </strong>
      <span className="mt-1 block text-[10px] leading-4 text-slate-400">
        {detail}
      </span>
    </div>
  );
}

function UnitMetric({ label, value, detail }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
      <span className="block text-[9px] font-extrabold uppercase tracking-[0.1em] text-slate-400">
        {label}
      </span>
      <strong className="mt-1.5 block text-sm font-extrabold text-ink">
        {value}
      </strong>
      {detail ? (
        <span className="mt-0.5 block text-[9px] text-slate-400">
          {detail}
        </span>
      ) : null}
    </div>
  );
}

function ReinforcementDetail({ items }) {
  if (!items.length) {
    return (
      <p className="mt-3 text-[10px] text-slate-400">
        No se recibieron armaduras para esta referencia.
      </p>
    );
  }

  return (
    <div className="mt-3 overflow-x-auto rounded-xl border border-slate-100">
      <table className="w-full min-w-[690px] border-collapse">
        <thead>
          <tr className="bg-slate-50">
            {[
              "Nivel / dirección",
              "Especificación",
              "Barras",
              "Longitud",
              "Metros",
              "Peso unitario",
            ].map((heading) => (
              <th
                key={heading}
                className="border-b border-slate-100 px-3 py-2 text-left text-[8px] font-extrabold uppercase tracking-wider text-slate-400"
              >
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr
              key={`${item.nivel}-${item.direccion}-${item.diametro_pulgadas}-${index}`}
            >
              <td className="border-b border-slate-100 px-3 py-2.5 text-[10px] font-bold text-ink">
                {item.nivel || "—"} · {item.direccion || "—"}
              </td>
              <td className="border-b border-slate-100 px-3 py-2.5 text-[10px] text-slate-500">
                Ø {item.diametro_pulgadas || "—"}&quot; c/
                {formatNumber(item.separacion_cm, "cm")}
              </td>
              <td className="border-b border-slate-100 px-3 py-2.5 text-[10px] text-slate-500">
                {formatNumber(item.cantidad_barras)}
              </td>
              <td className="border-b border-slate-100 px-3 py-2.5 text-[10px] text-slate-500">
                {formatNumber(item.longitud_barra_m, "m")}
              </td>
              <td className="border-b border-slate-100 px-3 py-2.5 text-[10px] text-slate-500">
                {formatNumber(item.metros_por_fundacion, "m")}
              </td>
              <td className="border-b border-slate-100 px-3 py-2.5 text-[10px] font-extrabold text-ink">
                {formatNumber(item.peso_por_fundacion_kg, "kg")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UbicacionesDetail({
  locations = [],
  foundations = [],
  formwork = [],
  reinforcements = [],
  validation = {},
}) {
  const [selectedReference, setSelectedReference] = useState("todas");
  const [query, setQuery] = useState("");

  const foundationByReference = useMemo(
    () =>
      new Map(
        foundations.map((item) => [String(item.referencia), item])
      ),
    [foundations]
  );

  const formworkByReference = useMemo(
    () =>
      new Map(formwork.map((item) => [String(item.referencia), item])),
    [formwork]
  );

  const reinforcementByReference = useMemo(() => {
    const grouped = new Map();

    reinforcements.forEach((item) => {
      const reference = String(item.referencia || "");

      if (!grouped.has(reference)) {
        grouped.set(reference, []);
      }

      grouped.get(reference).push(item);
    });

    return grouped;
  }, [reinforcements]);

  const references = useMemo(
    () =>
      [...new Set(locations.map((item) => String(item.referencia || "")))]
        .filter(Boolean)
        .sort(compareReferences),
    [locations]
  );

  const filteredLocations = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("es");

    return [...locations]
      .filter((item) => {
        const reference = String(item.referencia || "");
        const identifier = String(item.identificador || "");

        const matchesReference =
          selectedReference === "todas" || reference === selectedReference;

        const matchesQuery =
          !normalizedQuery ||
          identifier.toLocaleLowerCase("es").includes(normalizedQuery) ||
          reference.toLocaleLowerCase("es").includes(normalizedQuery) ||
          String(item.texto_original || "")
            .toLocaleLowerCase("es")
            .includes(normalizedQuery);

        return matchesReference && matchesQuery;
      })
      .sort(
        (left, right) =>
          numericValue(left.orden_visual_global) -
          numericValue(right.orden_visual_global)
      );
  }, [locations, query, selectedReference]);

  const groupedLocations = useMemo(() => {
    const grouped = new Map();

    filteredLocations.forEach((item) => {
      const reference = String(item.referencia || "Sin referencia");

      if (!grouped.has(reference)) {
        grouped.set(reference, []);
      }

      grouped.get(reference).push(item);
    });

    return [...grouped.entries()].sort(([left], [right]) =>
      compareReferences(left, right)
    );
  }, [filteredLocations]);

  const detectedCount = locations.filter(
    (item) => item.ubicacion_pdf_detectada
  ).length;

  const confirmedAxesCount = locations.filter(
    (item) => item.ejes_confirmados
  ).length;

  const uniqueIdentifiers = new Set(
    locations.map((item) => item.identificador).filter(Boolean)
  ).size;

  const expectedCount =
    numericValue(validation.cantidad_esperada) ||
    foundations.reduce(
      (total, item) => total + numericValue(item.cantidad),
      0
    );

  const countsMatch =
    validation.coincide_con_resumen ??
    (expectedCount > 0 && expectedCount === locations.length);

  if (!locations.length) {
    return (
      <div className="p-6 sm:p-8">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <strong className="block text-sm font-extrabold text-amber-900">
            Todavía no hay ubicaciones individuales
          </strong>
          <p className="mt-2 text-[11px] leading-5 text-amber-800/80">
            Ejecutá un análisis nuevo con el backend actualizado. El resultado
            debe incluir la propiedad ubicaciones_fundaciones.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 sm:p-7">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Elementos esperados"
          value={formatNumber(expectedCount)}
          detail="Según el cómputo por tipos"
        />
        <SummaryCard
          label="Ubicados en PDF"
          value={`${detectedCount}/${locations.length}`}
          detail="Referencias con posición visual"
          tone={detectedCount === locations.length ? "emerald" : "amber"}
        />
        <SummaryCard
          label="Identificadores únicos"
          value={formatNumber(uniqueIdentifiers)}
          detail="Sin repetir F…-NN"
          tone={uniqueIdentifiers === locations.length ? "emerald" : "amber"}
        />
        <SummaryCard
          label="Ejes confirmados"
          value={`${confirmedAxesCount}/${locations.length}`}
          detail="Ubicación apta para replanteo"
          tone={confirmedAxesCount === locations.length ? "emerald" : "amber"}
        />
      </div>

      <div
        className={`mt-4 rounded-2xl border p-4 ${
          countsMatch
            ? "border-emerald-200 bg-emerald-50"
            : "border-rose-200 bg-rose-50"
        }`}
      >
        <strong
          className={`block text-xs font-extrabold ${
            countsMatch ? "text-emerald-900" : "text-rose-900"
          }`}
        >
          {countsMatch
            ? "Conteo individual validado"
            : "El conteo individual requiere revisión"}
        </strong>
        <p
          className={`mt-1 text-[10px] leading-5 ${
            countsMatch ? "text-emerald-800/75" : "text-rose-800/75"
          }`}
        >
          Se encontraron {locations.length} elementos y {uniqueIdentifiers}{" "}
          identificadores únicos. El control se compara contra {expectedCount}{" "}
          elementos esperados.
        </p>
      </div>

      {validation.ejes_disponibles === false ? (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <strong className="block text-xs font-extrabold text-amber-900">
            Ejes estructurales pendientes
          </strong>
          <p className="mt-1 text-[10px] leading-5 text-amber-800/75">
            Las coordenadas mostradas ubican el texto dentro del PDF. Todavía no
            representan coordenadas de obra ni deben utilizarse para replantear.
          </p>
        </div>
      ) : null}

      <div className="mt-5 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 sm:flex-row sm:items-end">
        <label className="flex-1">
          <span className="mb-1.5 block text-[9px] font-extrabold uppercase tracking-[0.12em] text-slate-400">
            Buscar elemento
          </span>
          <input
            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-ink outline-none transition placeholder:text-slate-300 focus:border-accent"
            type="search"
            value={query}
            placeholder="Ejemplo: F7-03"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>

        <label className="sm:w-56">
          <span className="mb-1.5 block text-[9px] font-extrabold uppercase tracking-[0.12em] text-slate-400">
            Filtrar por tipo
          </span>
          <select
            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-ink outline-none transition focus:border-accent"
            value={selectedReference}
            onChange={(event) => setSelectedReference(event.target.value)}
          >
            <option value="todas">Todas las referencias</option>
            {references.map((reference) => (
              <option key={reference} value={reference}>
                {reference}
              </option>
            ))}
          </select>
        </label>

        <div className="flex h-10 items-center rounded-xl border border-slate-200 bg-white px-3 text-[10px] font-bold text-slate-500">
          {filteredLocations.length} de {locations.length}
        </div>
      </div>

      {groupedLocations.length === 0 ? (
        <div className="mt-5 rounded-2xl border border-dashed border-slate-200 px-5 py-12 text-center text-xs font-semibold text-slate-400">
          No hay elementos que coincidan con la búsqueda.
        </div>
      ) : (
        <div className="mt-5 space-y-5">
          {groupedLocations.map(([reference, elements]) => {
            const foundation = foundationByReference.get(reference) || {};
            const formworkItem = formworkByReference.get(reference) || {};
            const reinforcementItems =
              reinforcementByReference.get(reference) || [];

            const steelPerElement = reinforcementItems.reduce(
              (total, item) =>
                total + numericValue(item.peso_por_fundacion_kg),
              0
            );

            const steelTotal = reinforcementItems.reduce(
              (total, item) => total + numericValue(item.peso_total_kg),
              0
            );

            const barsPerElement = reinforcementItems.reduce(
              (total, item) => total + numericValue(item.cantidad_barras),
              0
            );

            return (
              <section
                key={reference}
                className="overflow-hidden rounded-2xl border border-slate-200 bg-white"
              >
                <div className="border-b border-slate-100 bg-slate-50/70 p-4 sm:p-5">
                  <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="rounded-lg bg-slate-950 px-2.5 py-1 text-xs font-extrabold text-white">
                          {reference}
                        </span>
                        <span className="text-[10px] font-bold text-slate-400">
                          {elements.length} elemento
                          {elements.length === 1 ? "" : "s"} mostrado
                          {elements.length === 1 ? "" : "s"}
                        </span>
                      </div>
                      <p className="mt-2 text-[10px] text-slate-400">
                        Dimensiones: {formatNumber(foundation.x)} ×{" "}
                        {formatNumber(foundation.y)} × {formatNumber(foundation.h)} m
                      </p>
                    </div>

                    <div className="text-left sm:text-right">
                      <span className="block text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                        Totales del tipo
                      </span>
                      <strong className="mt-1 block text-xs text-ink">
                        {formatNumber(foundation.volumen_total, "m³")} ·{" "}
                        {formatNumber(formworkItem.area_total_m2, "m²")} ·{" "}
                        {formatNumber(steelTotal, "kg")}
                      </strong>
                    </div>
                  </div>
                </div>

                <div className="grid gap-3 p-4 xl:grid-cols-2 xl:p-5">
                  {elements.map((location) => (
                    <article
                      key={location.identificador}
                      className="rounded-2xl border border-slate-200 p-4 transition hover:border-accent/40 hover:shadow-[0_12px_30px_rgba(16,34,53,.06)]"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <span className="text-[9px] font-extrabold uppercase tracking-[0.12em] text-slate-400">
                            Elemento individual
                          </span>
                          <strong className="mt-1 block font-display text-xl font-bold text-ink">
                            {location.identificador || reference}
                          </strong>
                          <span className="mt-1 block text-[10px] text-slate-400">
                            Página {location.pagina || "—"} · orden visual{" "}
                            {location.orden_visual_global || "—"}
                          </span>
                        </div>

                        <div className="flex flex-col items-end gap-1.5">
                          <span
                            className={`rounded-full px-2.5 py-1 text-[9px] font-extrabold ${
                              location.ubicacion_pdf_detectada
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-rose-100 text-rose-700"
                            }`}
                          >
                            {location.ubicacion_pdf_detectada
                              ? "Ubicada en PDF"
                              : "Ubicación pendiente"}
                          </span>
                          <span
                            className={`rounded-full px-2.5 py-1 text-[9px] font-extrabold ${
                              location.ejes_confirmados
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-amber-100 text-amber-700"
                            }`}
                          >
                            {location.ejes_confirmados
                              ? "Ejes confirmados"
                              : "Ejes pendientes"}
                          </span>
                        </div>
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                        <UnitMetric
                          label="Hormigón"
                          value={formatNumber(
                            foundation.volumen_unitario,
                            "m³"
                          )}
                          detail="por elemento"
                        />
                        <UnitMetric
                          label="Encofrado"
                          value={formatNumber(
                            formworkItem.area_unitaria_m2,
                            "m²"
                          )}
                          detail="por elemento"
                        />
                        <UnitMetric
                          label="Acero"
                          value={formatNumber(steelPerElement, "kg")}
                          detail="por elemento"
                        />
                        <UnitMetric
                          label="Barras"
                          value={formatNumber(barsPerElement)}
                          detail="todas las capas"
                        />
                      </div>

                      <div className="mt-3 grid gap-2 rounded-xl border border-slate-100 bg-slate-50/60 p-3 sm:grid-cols-3">
                        <div>
                          <span className="block text-[8px] font-extrabold uppercase tracking-wider text-slate-400">
                            Centro visual X
                          </span>
                          <strong className="mt-1 block text-[11px] text-ink">
                            {formatCoordinate(location.centro_x_visual)}
                          </strong>
                        </div>
                        <div>
                          <span className="block text-[8px] font-extrabold uppercase tracking-wider text-slate-400">
                            Centro visual Y
                          </span>
                          <strong className="mt-1 block text-[11px] text-ink">
                            {formatCoordinate(location.centro_y_visual)}
                          </strong>
                        </div>
                        <div>
                          <span className="block text-[8px] font-extrabold uppercase tracking-wider text-slate-400">
                            Texto detectado
                          </span>
                          <strong className="mt-1 block text-[11px] text-ink">
                            {location.texto_original || "—"}
                          </strong>
                        </div>
                      </div>

                      <details className="group mt-3 rounded-xl border border-slate-200 bg-white">
                        <summary className="cursor-pointer list-none px-3 py-2.5 text-[10px] font-extrabold text-accent-dark">
                          Ver trazabilidad y armaduras de esta unidad
                        </summary>

                        <div className="border-t border-slate-100 p-3">
                          <div className="grid gap-2 text-[9px] text-slate-500 sm:grid-cols-2">
                            <span>
                              Caja PDF: X {formatCoordinate(location.x0)}–
                              {formatCoordinate(location.x1)}
                            </span>
                            <span>
                              Caja PDF: Y {formatCoordinate(location.y0)}–
                              {formatCoordinate(location.y1)}
                            </span>
                          </div>

                          <ReinforcementDetail items={reinforcementItems} />
                        </div>
                      </details>
                    </article>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default UbicacionesDetail;