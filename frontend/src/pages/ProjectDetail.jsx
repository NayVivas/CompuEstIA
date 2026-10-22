import Icon from "../components/Icon";
import {
  sumVolumes,
} from "../utils/formatters";

function formatBytes(bytes) {
  if (!bytes) return "0 KB";

  if (bytes < 1024 * 1024) {
    return `${Math.ceil(bytes / 1024)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(date) {
  if (!date) return "Sin fecha";

  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Sin fecha";
  }

  return parsedDate.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatDateTime(date) {
  if (!date) return "Sin fecha";

  const parsedDate = new Date(date);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Sin fecha";
  }

  return parsedDate.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getDocumentLabel(type) {
  switch (type) {
    case "planta":
      return "Planta de fundaciones";

    case "detalles":
      return "Cuadro de detalles";

    case "columnas":
      return "Plano de columnas";

    default:
      return "Documento";
  }
}

function getDocumentDescription(type) {
  switch (type) {
    case "planta":
      return "Distribución y referencias de fundaciones";

    case "detalles":
      return "Dimensiones y especificaciones";

    case "columnas":
      return "Ubicación de columnas";

    default:
      return "Archivo asociado al proyecto";
  }
}

function getStatusClasses(status) {
  switch (status) {
    case "Completado":
      return "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200";

    case "Procesando":
      return "bg-accent/10 text-accent-dark ring-1 ring-inset ring-accent/20";

    case "Pendiente":
      return "bg-slate-100 text-slate-600 ring-1 ring-inset ring-slate-200";

    case "Error":
      return "bg-red-50 text-red-600 ring-1 ring-inset ring-red-200";

    default:
      return "bg-slate-100 text-slate-600 ring-1 ring-inset ring-slate-200";
  }
}

function formatConfidence(confidence) {
  if (
    confidence === null ||
    confidence === undefined
  ) {
    return "—";
  }

  return `${Number(confidence).toFixed(1)}%`;
}

function formatVolume(volume) {
  if (
    volume === null ||
    volume === undefined
  ) {
    return "—";
  }

  return `${Number(volume).toFixed(1)} m³`;
}

function ProjectDetail({
  project,
  analyses = [],
  onBack,
  onUpload,
  onOpenAnalysis,
}) {
  if (!project) {
    return (
      <main className="px-6 py-8 lg:px-8">
        <div className="mx-auto max-w-5xl rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">
          <Icon
            name="folder"
            size={28}
          />

          <h1 className="mt-4 font-display text-xl font-bold text-ink">
            Proyecto no encontrado
          </h1>

          <button
            type="button"
            onClick={onBack}
            className="mt-5 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white"
          >
            Volver a proyectos
          </button>
        </div>
      </main>
    );
  }

  const documents =
    project.documentsData || [];

  const projectAnalyses = analyses
    .filter(
      (analysis) =>
        analysis.projectId === project.id
    )
    .sort(
      (a, b) =>
        new Date(b.date || 0) -
        new Date(a.date || 0)
    );

  const completedAnalyses =
    projectAnalyses.filter(
      (analysis) =>
        analysis.status === "Completado"
    );

  const totalVolume = sumVolumes(
  projectAnalyses,
  "volume"
);

  return (
    <main className="px-6 py-8 lg:px-8">
      <div className="mx-auto max-w-[1400px]">

        {/* Back */}
        <button
          type="button"
          onClick={onBack}
          className="mb-6 inline-flex items-center gap-2 text-xs font-bold text-slate-400 transition hover:text-slate-700"
        >
          <Icon
            name="arrowRight"
            size={15}
            className="rotate-180"
          />

          Volver a proyectos
        </button>

        {/* Project header */}
        <section className="overflow-hidden rounded-3xl bg-slate-950 p-7 text-white shadow-[0_20px_50px_rgba(16,34,53,.15)] sm:p-8">
          <div className="relative">

            <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-accent/15 blur-3xl" />

            <div className="relative">
              <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-start">

                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-accent">
                      <Icon
                        name="folder"
                        size={16}
                      />
                    </span>

                    <span className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent">
                      Proyecto
                    </span>
                  </div>

                  <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
                    {project.name}
                  </h1>

                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                    {project.description ||
                      "Proyecto de ingeniería sin descripción."}
                  </p>
                </div>

                <span
                  className={`w-fit rounded-full px-3 py-1.5 text-[10px] font-bold ${getStatusClasses(
                    project.status
                  )}`}
                >
                  {project.status}
                </span>
              </div>

              <div className="mt-8 grid gap-4 border-t border-white/10 pt-6 sm:grid-cols-2 lg:grid-cols-4">

                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Cliente
                  </p>

                  <p className="mt-1 text-sm font-semibold text-slate-200">
                    {project.client || "—"}
                  </p>
                </div>

                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Ubicación
                  </p>

                  <p className="mt-1 text-sm font-semibold text-slate-200">
                    {project.location || "—"}
                  </p>
                </div>

                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Tipo de obra
                  </p>

                  <p className="mt-1 text-sm font-semibold text-slate-200">
                    {project.type || "—"}
                  </p>
                </div>

                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Actualizado
                  </p>

                  <p className="mt-1 text-sm font-semibold text-slate-200">
                    {project.updated || "—"}
                  </p>
                </div>

              </div>
            </div>
          </div>
        </section>

        {/* Metrics */}
        <div className="my-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium text-slate-400">
              Documentos
            </p>

            <p className="mt-2 font-display text-2xl font-bold text-ink">
              {project.documents || 0}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium text-slate-400">
              Análisis
            </p>

            <p className="mt-2 font-display text-2xl font-bold text-ink">
              {projectAnalyses.length}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium text-slate-400">
              Análisis completados
            </p>

            <p className="mt-2 font-display text-2xl font-bold text-ink">
              {completedAnalyses.length}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium text-slate-400">
              Hormigón calculado
            </p>

           <p className="font-display text-3xl font-bold tracking-tight text-ink">
  {Number(totalVolume || 0).toFixed(1)}
  <span className="ml-1 text-base font-semibold text-slate-400">
    m³
  </span>
</p>
          </div>

        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">

          {/* Documents */}
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">

            <div className="flex flex-col justify-between gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center">
              <div>
                <h2 className="font-display text-base font-bold text-ink">
                  Documentación
                </h2>

                <p className="mt-1 text-xs text-slate-400">
                  Planos y archivos asociados al proyecto.
                </p>
              </div>

              <button
                type="button"
                onClick={onUpload}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-slate-800"
              >
                <Icon
                  name="upload"
                  size={15}
                />

                Cargar documentación
              </button>
            </div>

            {documents.length === 0 ? (
              <div className="px-6 py-14 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
                  <Icon
                    name="file"
                    size={22}
                  />
                </div>

                <h3 className="mt-4 text-sm font-bold text-ink">
                  Sin documentación cargada
                </h3>

                <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-slate-500">
                  Cargá los planos necesarios para iniciar
                  un análisis.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {documents.map((document) => (
                  <div
                    key={document.id}
                    className="flex items-center gap-4 px-5 py-4 transition hover:bg-slate-50"
                  >
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-500">
                      <Icon
                        name="file"
                        size={20}
                      />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-bold text-ink">
                          {document.name}
                        </p>

                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[8px] font-extrabold uppercase text-slate-500">
                          PDF
                        </span>
                      </div>

                      <p className="mt-1 text-xs text-slate-500">
                        {getDocumentLabel(
                          document.type
                        )}
                      </p>

                      <p className="mt-1 text-[10px] text-slate-400">
                        {getDocumentDescription(
                          document.type
                        )}{" "}
                        ·{" "}
                        {formatBytes(
                          document.size
                        )}{" "}
                        ·{" "}
                        {formatDate(
                          document.uploadedAt
                        )}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}

          </section>

          {/* Analysis summary */}
          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">

            <div className="border-b border-slate-200 px-5 py-4">
              <h2 className="font-display text-base font-bold text-ink">
                Resumen de análisis
              </h2>

              <p className="mt-1 text-xs text-slate-400">
                Estado general del procesamiento.
              </p>
            </div>

            <div className="p-5">

              <div className="rounded-2xl bg-slate-950 p-5 text-white">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">
                    Último análisis
                  </span>

                  <Icon
                    name="activity"
                    size={17}
                    className="text-accent"
                  />
                </div>

                {projectAnalyses.length > 0 ? (
                  <>
                    <p className="mt-4 font-display text-2xl font-bold">
                      Análisis #
                      {projectAnalyses[0].number}
                    </p>

                    <p className="mt-1 text-xs text-slate-400">
                      {formatDateTime(
                        projectAnalyses[0].date
                      )}
                    </p>

                    <div className="mt-5">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold ${getStatusClasses(
                          projectAnalyses[0].status
                        )}`}
                      >
                        {projectAnalyses[0].status}
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="mt-4 font-display text-xl font-bold">
                      Sin análisis
                    </p>

                    <p className="mt-1 text-xs leading-5 text-slate-400">
                      Todavía no se ha procesado documentación
                      de este proyecto.
                    </p>
                  </>
                )}
              </div>

              {projectAnalyses.length > 0 ? (
                <div className="mt-5 space-y-3">

                  {projectAnalyses.slice(0, 3).map(
                    (analysis) => (
                      <button
                        key={analysis.id}
                        type="button"
                        onClick={() =>
                          onOpenAnalysis?.(
                            analysis.id
                          )
                        }
                        className="flex w-full items-center gap-3 rounded-xl border border-slate-200 p-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
                      >
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                          <Icon
                            name="scan"
                            size={16}
                          />
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-bold text-ink">
                              Análisis #
                              {analysis.number}
                            </span>

                            <span
                              className={`rounded-full px-2 py-1 text-[9px] font-bold ${getStatusClasses(
                                analysis.status
                              )}`}
                            >
                              {analysis.status}
                            </span>
                          </div>

                          <div className="mt-1 flex items-center gap-3 text-[10px] text-slate-400">
                            <span>
                              {formatConfidence(
                                analysis.confidence
                              )}
                            </span>

                            <span>
                              {formatVolume(
                                analysis.volume
                              )}
                            </span>
                          </div>
                        </div>

                        <Icon
                          name="arrowRight"
                          size={15}
                        />
                      </button>
                    )
                  )}

                </div>
              ) : null}

              <button
                type="button"
                onClick={onUpload}
                className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-xs font-bold text-slate-600 transition hover:border-slate-300 hover:bg-slate-50"
              >
                <Icon
                  name="scan"
                  size={15}
                />

                {projectAnalyses.length > 0
                  ? "Ejecutar nuevo análisis"
                  : "Iniciar análisis"}
              </button>

            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

export default ProjectDetail;
