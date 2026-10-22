import Icon from "../components/Icon";
import { confirmedConcreteVolume } from "../utils/analysisMetrics";

const format = (value) => new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(value);

export default function Dashboard({ projects = [], analyses = [], onNewAnalysis, onOpenProject }) {
  const completed = analyses.filter((item) => item.status === "Completado" && item.resultado);
  const concrete = confirmedConcreteVolume(analyses);
  const reviewed = projects.filter((item) => item.status === "Revisión requerida" || item.status === "Revisión geométrica requerida").length;
  const recent = [...projects].sort((a, b) => Number(b.id) - Number(a.id)).slice(0, 5);
  const stats = [
    ["Proyectos", projects.length, "folder"],
    ["Análisis completados", completed.length, "check"],
    ["Proyectos para revisar", reviewed, "scan"],
    ["Hormigón identificado", `${format(concrete)} m³`, "barChart"],
  ];

  return <main className="mx-auto max-w-6xl space-y-6 p-6 sm:p-8">
    <header className="rounded-3xl bg-slate-950 p-7 text-white">
      <p className="text-xs font-bold uppercase tracking-widest text-teal-300">Centro de análisis estructural</p>
      <h1 className="mt-3 text-3xl font-bold">CómputoEstIA</h1>
      <p className="mt-2 max-w-2xl text-sm text-slate-300">Cargá planos, revisá evidencias y calculá solo las cantidades respaldadas por el proyecto.</p>
      <button type="button" onClick={onNewAnalysis}
        className="mt-5 rounded-xl bg-teal-500 px-5 py-3 text-sm font-bold text-white hover:bg-teal-600">
        {projects.length ? "Elegir proyecto" : "Crear primer proyecto"}
      </button>
    </header>
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Indicadores del espacio de trabajo">
      {stats.map(([label, value, icon]) => <div key={label} className="rounded-2xl border bg-white p-5">
        <Icon name={icon} size={18} />
        <p className="mt-4 text-xs font-semibold text-slate-500">{label}</p>
        <p className="mt-1 text-2xl font-bold">{value}</p>
      </div>)}
    </section>
    <section className="rounded-2xl border bg-white p-5">
      <h2 className="text-xl font-bold">Proyectos recientes</h2>
      {recent.length === 0 ? <p className="mt-4 text-sm text-slate-600">Todavía no hay proyectos. Creá uno para subir planos y comenzar el análisis.</p> :
        <div className="mt-4 divide-y">{recent.map((project) => <button type="button" key={project.id}
          onClick={() => onOpenProject(project.id)} className="flex w-full items-center justify-between py-3 text-left hover:text-teal-700">
          <span className="font-semibold">{project.name}</span>
          <span className="text-xs text-slate-500">{project.status || "Pendiente"}</span>
        </button>)}</div>}
    </section>
    <p className="text-xs text-slate-500">Los volúmenes geométricos sin material confirmado no se suman al hormigón identificado.</p>
  </main>;
}
