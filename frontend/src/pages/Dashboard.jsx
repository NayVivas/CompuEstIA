import Icon from "../components/Icon";
import { confirmedConcreteVolume } from "../utils/analysisMetrics";

const format = (value) => new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(value);

export default function Dashboard({
  projects = [],
  analyses = [],
  onNewAnalysis,
  onOpenProject,
  onOpenDemo,
}) {
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
     <div className="mt-7 grid gap-4 sm:grid-cols-2">

  {/* PROYECTOS */}
  <button
    type="button"
    onClick={onNewAnalysis}
    className="group relative flex min-h-28 items-center gap-4 overflow-hidden
    rounded-2xl border border-teal-300/40
    bg-gradient-to-br from-teal-400 via-teal-500 to-emerald-600
    p-5 text-left text-white
    shadow-[0_10px_35px_rgba(20,184,166,0.35)]
    transition-all duration-300
    hover:-translate-y-2 hover:scale-[1.02]
    hover:shadow-[0_16px_45px_rgba(20,184,166,0.55)]
    active:scale-[0.98]"
  >
    <span className="absolute -right-5 -top-8 h-36 w-36 rounded-full bg-white/10 transition-transform duration-500 group-hover:scale-150" />

    <span className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/20 shadow-inner ring-1 ring-white/30">
      <Icon name="folder" size={34} />
    </span>

    <span className="relative flex-1">
      <span className="block text-lg font-black tracking-wide">
        {projects.length ? "MIS PROYECTOS" : "CREAR PROYECTO"}
      </span>
      <span className="mt-1 block text-xs font-medium text-white/90">
        Gestioná tus análisis estructurales
      </span>
      <span className="mt-3 inline-flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider">
        Ingresar <Icon name="arrow-right" size={16} />
      </span>
    </span>
  </button>

  {/* DEMOSTRACIÓN */}
  <button
    type="button"
    onClick={onOpenDemo}
    className="group relative flex min-h-28 items-center gap-4 overflow-hidden
    rounded-2xl border border-blue-300/40
    bg-gradient-to-br from-blue-500 via-blue-600 to-indigo-700
    p-5 text-left text-white
    shadow-[0_10px_35px_rgba(59,130,246,0.4)]
    transition-all duration-300
    hover:-translate-y-2 hover:scale-[1.02]
    hover:shadow-[0_16px_45px_rgba(59,130,246,0.65)]
    active:scale-[0.98]"
  >
    <span className="absolute -right-5 -top-8 h-36 w-36 rounded-full bg-white/10 transition-transform duration-500 group-hover:scale-150" />

    <span className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/20 shadow-inner ring-1 ring-white/30">
      <Icon name="box" size={36} />
    </span>

    <span className="relative flex-1">
      <span className="flex flex-wrap items-center gap-2">
        <span className="text-lg font-black tracking-wide">PROYECTO 8</span>
        <span className="rounded-full border border-white/40 bg-white/20 px-2.5 py-1 text-[9px] font-black tracking-widest">
          DEMO
        </span>
      </span>
      <span className="mt-1 block text-xs font-medium text-white/90">
        Explorá resultados y modelo tridimensional
      </span>
      <span className="mt-3 inline-flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider">
        Ver demostración <Icon name="arrow-up-right" size={16} />
      </span>
    </span>
  </button>

</div>
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
