import Icon from "../components/Icon";
import { confirmedConcreteVolume } from "../utils/analysisMetrics";

function getStatusClasses(status) {
  if (status === "Completado") {
    return "border-accent/20 bg-accent/10 text-accent-dark";
  }

  if (status === "Procesando") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }

  return "border-slate-200 bg-slate-100 text-slate-500";
}

function formatConfidence(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return `${Number(value).toFixed(1)}%`;
}

function formatVolume(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return `${Number(value).toFixed(1)} m³`;
}

export default function Analyses({
  analyses = [],
  projects = [],
  selectedProjectId,
  error,
  onOpenAnalysis,
  onNewAnalysis,
}) {
  const projectAnalyses = analyses
    .filter(
      (analysis) =>
        selectedProjectId === null ||
        analysis.projectId === selectedProjectId
    )
    .sort((a, b) => {
      const dateA = new Date(a.date).getTime();
      const dateB = new Date(b.date).getTime();

      return dateB - dateA;
    });

  const completedAnalyses = projectAnalyses.filter(
    (analysis) => analysis.status === "Completado"
  );

  const processingAnalyses = projectAnalyses.filter(
    (analysis) => analysis.status === "Procesando"
  );

  const averageConfidence =
    completedAnalyses.length > 0
      ? completedAnalyses.reduce(
          (total, analysis) =>
            total + (analysis.confidence || 0),
          0
        ) / completedAnalyses.length
      : 0;

  const totalVolume = confirmedConcreteVolume(projectAnalyses);

  function getProject(analysis) {
    return projects.find(
      (project) => project.id === analysis.projectId
    );
  }

  return (
    <main className="mx-auto w-full max-w-[1440px] px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
      {error && <p role="alert" className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">{error}</p>}
      {/* ================================================= */}
      {/* HEADER */}
      {/* ================================================= */}

      <div className="flex flex-col gap-5 border-b border-slate-200 pb-7 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="mb-4 flex items-center gap-3 text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">
            <span className="h-px w-8 bg-accent" />
            Análisis de ingeniería
          </div>

          <h1 className="font-display text-3xl font-bold tracking-[-0.035em] text-ink sm:text-4xl">
            Análisis
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Historial de análisis realizados sobre la
            documentación de tus proyectos.
          </p>
        </div>
        {onNewAnalysis && <button type="button" onClick={onNewAnalysis}
          className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white">
          Cargar planos y analizar
        </button>}
      </div>

      {/* ================================================= */}
      {/* MÉTRICAS */}
      {/* ================================================= */}

      <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_12px_35px_rgba(16,34,53,.045)]">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[9px] font-extrabold uppercase tracking-[0.16em] text-slate-400">
                Análisis realizados
              </p>

              <p className="mt-2 font-display text-2xl font-bold text-ink">
                {projectAnalyses.length}
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
              <Icon name="scan" size={18} />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_12px_35px_rgba(16,34,53,.045)]">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[9px] font-extrabold uppercase tracking-[0.16em] text-slate-400">
                Completados
              </p>

              <p className="mt-2 font-display text-2xl font-bold text-ink">
                {completedAnalyses.length}
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent">
              <Icon name="check" size={18} />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_12px_35px_rgba(16,34,53,.045)]">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[9px] font-extrabold uppercase tracking-[0.16em] text-slate-400">
                Confianza promedio
              </p>

              <p className="mt-2 font-display text-2xl font-bold text-ink">
                {averageConfidence > 0
                  ? `${averageConfidence.toFixed(1)}%`
                  : "—"}
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
              <Icon name="shield" size={18} />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_12px_35px_rgba(16,34,53,.045)]">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[9px] font-extrabold uppercase tracking-[0.16em] text-slate-400">
                Hormigón calculado
              </p>

              <p className="mt-2 font-display text-2xl font-bold text-ink">
                {formatVolume(totalVolume)}
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
              <Icon name="barChart" size={18} />
            </div>
          </div>
        </div>
      </section>

      {/* ================================================= */}
      {/* ESTADO */}
      {/* ================================================= */}

      {processingAnalyses.length > 0 ? (
        <div className="mt-6 flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-amber-600">
            <Icon name="refresh" size={16} />
          </span>

          <div>
            <p className="text-xs font-extrabold text-amber-800">
              Análisis en procesamiento
            </p>

            <p className="mt-0.5 text-[10px] text-amber-700">
              El sistema continúa procesando la documentación.
            </p>
          </div>
        </div>
      ) : null}

      {/* ================================================= */}
      {/* TABLA */}
      {/* ================================================= */}

      <section className="mt-6 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_15px_40px_rgba(16,34,53,.05)]">
        <div className="border-b border-slate-100 px-6 py-6 sm:px-7">
          <p className="text-[9px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">
            Historial
          </p>

          <h2 className="mt-1 font-display text-xl font-bold text-ink">
            Análisis realizados
          </h2>
        </div>

        {projectAnalyses.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
              <Icon name="scan" size={21} />
            </div>

            <h3 className="mt-4 text-sm font-extrabold text-ink">
              Todavía no hay análisis
            </h3>

            <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-slate-400">
              Cuando proceses documentación de un proyecto,
              sus análisis aparecerán acá.
            </p>
          </div>
        ) : (
          <>
            {/* Header escritorio */}
            <div className="hidden grid-cols-[.7fr_1.5fr_1fr_.8fr_.9fr_1fr] gap-4 border-b border-slate-100 bg-slate-50 px-6 py-3 text-[9px] font-extrabold uppercase tracking-wider text-slate-400 lg:grid">
              <span>Análisis</span>
              <span>Proyecto</span>
              <span>Estado</span>
              <span>Referencias</span>
              <span>Confianza</span>
              <span>Acción</span>
            </div>

            <div>
              {projectAnalyses.map((analysis) => {
                const project = getProject(analysis);

                return (
                  <div
                    key={analysis.id}
                    className="border-b border-slate-100 px-5 py-5 last:border-b-0 sm:px-6"
                  >
                    {/* Desktop */}
                    <div className="hidden items-center lg:grid lg:grid-cols-[.7fr_1.5fr_1fr_.8fr_.9fr_1fr] lg:gap-4">
                      <div>
                        <p className="text-xs font-extrabold text-ink">
                          #
                          {String(
                            analysis.number || 1
                          ).padStart(3, "0")}
                        </p>

                        <p className="mt-1 text-[9px] font-semibold text-slate-400">
                          {new Date(
                            analysis.date
                          ).toLocaleDateString("es-AR")}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs font-extrabold text-ink">
                          {project?.name ||
                            "Proyecto"}
                        </p>

                        <p className="mt-1 text-[9px] font-semibold text-slate-400">
                          {project?.client || "—"}
                        </p>
                      </div>

                      <div>
                        <span
                          className={`inline-flex rounded-full border px-2.5 py-1 text-[9px] font-extrabold uppercase tracking-wider ${getStatusClasses(
                            analysis.status
                          )}`}
                        >
                          {analysis.status}
                        </span>
                      </div>

                      <div className="text-xs font-bold text-slate-600">
                        {analysis.references ?? 0}
                      </div>

                      <div>
                        <p className="text-xs font-extrabold text-ink">
                          {formatConfidence(
                            analysis.confidence
                          )}
                        </p>

                        {analysis.confidence !==
                        null ? (
                          <div className="mt-2 h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full bg-accent"
                              style={{
                                width: `${Math.min(
                                  analysis.confidence,
                                  100
                                )}%`,
                              }}
                            />
                          </div>
                        ) : null}
                      </div>

                      <div>
                        <button
                          type="button"
                          onClick={() =>
                            onOpenAnalysis(
                              analysis.id
                            )
                          }
                          className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-[10px] font-extrabold text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 hover:text-ink"
                        >
                          Ver análisis
                          <Icon
                            name="arrowRight"
                            size={14}
                          />
                        </button>
                      </div>
                    </div>

                    {/* Mobile */}
                    <div className="lg:hidden">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-xs font-extrabold text-ink">
                            Análisis #
                            {String(
                              analysis.number || 1
                            ).padStart(3, "0")}
                          </p>

                          <p className="mt-1 text-[9px] font-semibold text-slate-400">
                            {project?.name ||
                              "Proyecto"}
                          </p>
                        </div>

                        <span
                          className={`rounded-full border px-2.5 py-1 text-[9px] font-extrabold uppercase tracking-wider ${getStatusClasses(
                            analysis.status
                          )}`}
                        >
                          {analysis.status}
                        </span>
                      </div>

                      <div className="mt-5 grid grid-cols-3 gap-3">
                        <div>
                          <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                            Referencias
                          </p>

                          <p className="mt-1 text-sm font-bold text-ink">
                            {analysis.references ??
                              0}
                          </p>
                        </div>

                        <div>
                          <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                            Confianza
                          </p>

                          <p className="mt-1 text-sm font-bold text-ink">
                            {formatConfidence(
                              analysis.confidence
                            )}
                          </p>
                        </div>

                        <div>
                          <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                            Hormigón
                          </p>

                          <p className="mt-1 text-sm font-bold text-ink">
                            {formatVolume(
                              analysis.volume
                            )}
                          </p>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() =>
                          onOpenAnalysis(
                            analysis.id
                          )
                        }
                        className="mt-5 flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-slate-950 text-[10px] font-extrabold text-white"
                      >
                        Ver análisis
                        <Icon
                          name="arrowRight"
                          size={15}
                        />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </section>

      {/* ================================================= */}
      {/* INFORMACIÓN */}
      {/* ================================================= */}

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {[
          {
            icon: "scan",
            title: "Detección",
            text: "Identificación de referencias y elementos estructurales.",
          },
          {
            icon: "layers",
            title: "Asociación",
            text: "Vinculación entre referencias, dimensiones y tipos.",
          },
          {
            icon: "barChart",
            title: "Cómputo",
            text: "Transformación de las detecciones en cantidades medibles.",
          },
        ].map((item) => (
          <div
            key={item.title}
            className="rounded-2xl border border-slate-200 bg-white p-5"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
              <Icon name={item.icon} size={17} />
            </div>

            <h3 className="mt-4 text-xs font-extrabold text-ink">
              {item.title}
            </h3>

            <p className="mt-1 text-[10px] leading-5 text-slate-400">
              {item.text}
            </p>
          </div>
        ))}
      </div>
    </main>
  );
}
