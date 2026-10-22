import Icon from "../components/Icon";
import { confirmedConcreteVolume, latestCompletedByProject } from "../utils/analysisMetrics";

function Projects({
  projects = [],
  analyses = [],
  onNewProject,
  onOpenProject,
}) {
  const completed = analyses.filter((analysis) => analysis.status === "Completado" && analysis.resultado);
  const totalAnalyses = completed.length;

  const totalDocuments = projects.reduce(
    (total, project) => total + Number(project.documents || 0),
    0
  );

  const totalVolume = confirmedConcreteVolume(analyses);
  const latestByProject = new Map(latestCompletedByProject(analyses).map((analysis) => [analysis.projectId, analysis]));

  const activeProjects = projects.filter(
    (project) =>
      project.status === "En análisis" ||
      project.status === "Pendiente"
  ).length;

  function getStatusClasses(status) {
    if (status === "Completado") {
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    }

    if (status === "En análisis") {
      return "border-accent/30 bg-accent/10 text-accent-dark";
    }

    return "border-slate-200 bg-slate-50 text-slate-500";
  }

  function getProjectVolume(project) {
    const latest = latestByProject.get(project.id);
    if (!latest) return "—";
    return `${Number(latest.resultado.volumen_hormigon_m3 || 0).toFixed(1)} m³`;
  }

  return (
    <section className="space-y-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">
            Gestión de obra
          </p>

          <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-ink">
            Proyectos
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Organizá proyectos, documentación técnica y análisis
            de cómputos métricos desde un único entorno.
          </p>
        </div>

        <button
          type="button"
          onClick={onNewProject}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-slate-950 px-5 text-xs font-extrabold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-ink"
        >
          <Icon name="plus" size={17} />
          Nuevo proyecto
        </button>
      </div>

      {/* Metrics */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
              Proyectos activos
            </p>

            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-accent-dark">
              <Icon name="folder" size={17} />
            </div>
          </div>

          <p className="mt-4 font-display text-3xl font-bold tracking-tight text-ink">
            {activeProjects}
          </p>

          <p className="mt-1 text-[10px] font-medium text-slate-400">
            Pendientes o en análisis
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
              Análisis realizados
            </p>

            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
              <Icon name="scan" size={17} />
            </div>
          </div>

          <p className="mt-4 font-display text-3xl font-bold tracking-tight text-ink">
            {totalAnalyses}
          </p>

          <p className="mt-1 text-[10px] font-medium text-slate-400">
            Procesamientos registrados
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
              Documentos procesados
            </p>

            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
              <Icon name="file" size={17} />
            </div>
          </div>

          <p className="mt-4 font-display text-3xl font-bold tracking-tight text-ink">
            {totalDocuments}
          </p>

          <p className="mt-1 text-[10px] font-medium text-slate-400">
            Planos y documentación
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
              Hormigón calculado
            </p>

            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
              <Icon name="barChart" size={17} />
            </div>
          </div>

          <p className="mt-4 font-display text-3xl font-bold tracking-tight text-ink">
            {totalVolume.toFixed(1)}
            <span className="ml-1 text-base font-semibold text-slate-400">
              m³
            </span>
          </p>

          <p className="mt-1 text-[10px] font-medium text-slate-400">
            Volumen acumulado
          </p>
        </div>
      </div>

      {/* Projects table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col justify-between gap-3 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center">
          <div>
            <h2 className="font-display text-base font-bold text-ink">
              Todos los proyectos
            </h2>

            <p className="mt-1 text-[10px] font-medium text-slate-400">
              {projects.length}{" "}
              {projects.length === 1
                ? "proyecto registrado"
                : "proyectos registrados"}
            </p>
          </div>

          <div className="flex items-center gap-2 text-[10px] font-semibold text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Entorno de trabajo
          </div>
        </div>

        {projects.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
              <Icon name="folder" size={24} />
            </div>

            <h3 className="mt-5 font-display text-lg font-bold text-ink">
              Todavía no tenés proyectos
            </h3>

            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
              Creá tu primer proyecto para comenzar a cargar
              documentación y realizar análisis.
            </p>

            <button
              type="button"
              onClick={onNewProject}
              className="mt-6 inline-flex h-10 items-center gap-2 rounded-xl bg-slate-950 px-4 text-xs font-extrabold text-white transition hover:bg-ink"
            >
              <Icon name="plus" size={16} />
              Crear proyecto
            </button>
          </div>
        ) : (
          <>
            {/* Desktop */}
            <div className="hidden overflow-x-auto lg:block">
              <table className="w-full min-w-[900px]">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70">
                    <th className="px-5 py-3 text-left text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
                      Proyecto
                    </th>

                    <th className="px-4 py-3 text-left text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
                      Estado
                    </th>

                    <th className="px-4 py-3 text-left text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
                      Documentos
                    </th>

                    <th className="px-4 py-3 text-left text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
                      Análisis
                    </th>

                    <th className="px-4 py-3 text-left text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
                      Hormigón
                    </th>

                    <th className="px-4 py-3 text-left text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
                      Actualizado
                    </th>

                    <th className="px-4 py-3 text-right text-[9px] font-extrabold uppercase tracking-[0.14em] text-slate-400">
                      Acción
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {projects.map((project) => (
                    <tr
                      key={project.id}
                      className="border-b border-slate-100 last:border-0 transition hover:bg-slate-50/60"
                    >
                      <td className="px-5 py-4">
                        <div>
                          <p className="text-xs font-extrabold text-ink">
                            {project.name}
                          </p>

                          <p className="mt-1 text-[10px] font-medium text-slate-400">
                            {project.client ||
                              project.type ||
                              "Proyecto de ingeniería"}
                          </p>
                        </div>
                      </td>

                      <td className="px-4 py-4">
                        <span
                          className={`inline-flex rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${getStatusClasses(
                            project.status
                          )}`}
                        >
                          {project.status}
                        </span>
                      </td>

                      <td className="px-4 py-4 text-xs font-bold text-slate-600">
                        {Number(project.documents || 0)}
                      </td>

                      <td className="px-4 py-4 text-xs font-bold text-slate-600">
                        {completed.filter((analysis) => analysis.projectId === project.id).length}
                      </td>

                      <td className="px-4 py-4 text-xs font-bold text-slate-600">
                        {getProjectVolume(project)}
                      </td>

                      <td className="px-4 py-4 text-[10px] font-semibold text-slate-400">
                        {project.updated || "—"}
                      </td>

                      <td className="px-4 py-4 text-right">
                        <button
                          type="button"
                          onClick={() =>
                            onOpenProject(project.id)
                          }
                          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-[10px] font-extrabold text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 hover:text-ink"
                        >
                          Abrir
                          <Icon
                            name="arrowRight"
                            size={14}
                          />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile */}
            <div className="divide-y divide-slate-100 lg:hidden">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className="p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-extrabold text-ink">
                        {project.name}
                      </h3>

                      <p className="mt-1 truncate text-[10px] font-medium text-slate-400">
                        {project.client ||
                          project.type ||
                          "Proyecto de ingeniería"}
                      </p>
                    </div>

                    <span
                      className={`shrink-0 rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${getStatusClasses(
                        project.status
                      )}`}
                    >
                      {project.status}
                    </span>
                  </div>

                  <div className="mt-5 grid grid-cols-3 gap-3">
                    <div className="rounded-xl bg-slate-50 p-3">
                      <p className="text-[9px] font-extrabold uppercase tracking-[0.12em] text-slate-400">
                        Docs
                      </p>
                      <p className="mt-1 text-sm font-bold text-ink">
                        {Number(project.documents || 0)}
                      </p>
                    </div>

                    <div className="rounded-xl bg-slate-50 p-3">
                      <p className="text-[9px] font-extrabold uppercase tracking-[0.12em] text-slate-400">
                        Análisis
                      </p>
                      <p className="mt-1 text-sm font-bold text-ink">
                        {completed.filter((analysis) => analysis.projectId === project.id).length}
                      </p>
                    </div>

                    <div className="rounded-xl bg-slate-50 p-3">
                      <p className="text-[9px] font-extrabold uppercase tracking-[0.12em] text-slate-400">
                        Hormigón
                      </p>
                      <p className="mt-1 text-sm font-bold text-ink">
                        {getProjectVolume(project)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between">
                    <p className="text-[10px] font-semibold text-slate-400">
                      {project.updated || "—"}
                    </p>

                    <button
                      type="button"
                      onClick={() =>
                        onOpenProject(project.id)
                      }
                      className="inline-flex items-center gap-2 rounded-lg bg-slate-950 px-3 py-2 text-[10px] font-extrabold text-white transition hover:bg-ink"
                    >
                      Abrir proyecto
                      <Icon
                        name="arrowRight"
                        size={14}
                      />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

export default Projects;
