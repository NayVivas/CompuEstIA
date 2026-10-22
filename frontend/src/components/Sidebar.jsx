import Icon from "./Icon";

function Sidebar({
  activeView,
  onNavigate,
  selectedProject,
  backendStatus,
  onLogout,
}) {
  const globalItems = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: "dashboard",
    },
    {
      id: "projects",
      label: "Proyectos",
      icon: "folder",
    },
  ];

  const projectItems = [
    {
      id: "documentation",
      label: "Cargar planos",
      icon: "file",
    },
    {
      id: "analysis",
      label: "Análisis",
      icon: "scan",
    },
    { id: "model-3d", label: "Modelo 3D", icon: "scan" },
  ];

  function renderItem(item) {
    const isActive = activeView === item.id;

    return (
      <button
        key={item.id}
        type="button"
        onClick={() => onNavigate(item.id)}
        className={`group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-xs font-semibold transition ${
          isActive
            ? "bg-slate-950 text-white shadow-sm"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        <span
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition ${
            isActive
              ? "bg-white/10 text-accent"
              : "bg-slate-100 text-slate-400 group-hover:text-slate-700"
          }`}
        >
          <Icon name={item.icon} size={17} />
        </span>

        <span className="truncate">
          {item.label}
        </span>
      </button>
    );
  }

  return (
    <aside className="hidden w-[255px] shrink-0 border-r border-slate-200 bg-white lg:flex lg:flex-col">
      {/* ================================================= */}
      {/* LOGO */}
      {/* ================================================= */}

      <div className="border-b border-slate-100 px-5 py-5">
        <button
          type="button"
          onClick={() =>
            onNavigate("dashboard")
          }
          className="flex items-center gap-3 text-left"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-950 text-accent shadow-sm">
            <Icon
              name="scan"
              size={20}
            />
          </div>

          <div>
            <p className="font-display text-sm font-bold tracking-tight text-ink">
              CómputoEstIA
            </p>

            <p className="mt-0.5 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-400">
              Ingeniería + IA
            </p>
          </div>
        </button>
      </div>

      {/* ================================================= */}
      {/* NAVEGACIÓN */}
      {/* ================================================= */}

      <nav className="flex-1 overflow-y-auto px-3 py-5">
        {/* =============================================== */}
        {/* SIN PROYECTO */}
        {/* =============================================== */}

        {!selectedProject ? (
          <div>
            <p className="mb-2 px-3 text-[9px] font-extrabold uppercase tracking-[0.18em] text-slate-400">
              Principal
            </p>

            <div className="space-y-1">
              {globalItems.map(renderItem)}
            </div>
          </div>
        ) : (
          <>
            {/* =========================================== */}
            {/* VOLVER */}
            {/* =========================================== */}

            <button
              type="button"
              onClick={() =>
                onNavigate("projects")
              }
              className="group mb-6 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-[10px] font-bold text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            >
              <Icon
                name="arrowRight"
                size={14}
                className="rotate-180"
              />

              Volver a proyectos
            </button>

            {/* =========================================== */}
            {/* PROYECTO ACTIVO */}
            {/* =========================================== */}

            <div className="mb-6">
              <div className="mb-2 flex items-center justify-between px-3">
                <p className="text-[9px] font-extrabold uppercase tracking-[0.18em] text-slate-400">
                  Proyecto activo
                </p>

                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              </div>

              <div className="rounded-xl border border-accent/20 bg-accent/[0.045] px-3 py-3">
                <p className="truncate text-xs font-extrabold text-ink">
                  {selectedProject.name}
                </p>

                {selectedProject.client ? (
                  <p className="mt-1 truncate text-[10px] font-medium text-slate-400">
                    {selectedProject.client}
                  </p>
                ) : null}
              </div>
            </div>

            {/* =========================================== */}
            {/* SECCIONES DEL PROYECTO */}
            {/* =========================================== */}

            <div>
              <p className="mb-2 px-3 text-[9px] font-extrabold uppercase tracking-[0.18em] text-slate-400">
                Trabajo
              </p>

              <div className="space-y-1">
                {projectItems.map(renderItem)}
              </div>
            </div>
          </>
        )}
      </nav>

      {/* ================================================= */}
      {/* ESTADO / USUARIO */}
      {/* ================================================= */}

      <div className="border-t border-slate-100 p-4">
        <div className="rounded-xl bg-slate-950 px-3 py-3">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className={`relative inline-flex h-2 w-2 rounded-full ${backendStatus ? "bg-accent" : "bg-amber-400"}`} />
            </span>

            <span className="text-[9px] font-bold uppercase tracking-[0.14em] text-slate-300">
              {backendStatus ? "Backend conectado" : "Backend sin verificar"}
            </span>
          </div>

          <p className="mt-2 text-[10px] leading-4 text-slate-500">
            Lectura y revisión estructural
          </p>

          {onLogout ? (
            <button
              type="button"
              onClick={onLogout}
              className="mt-3 w-full rounded-lg border border-white/10 px-3 py-2 text-left text-[10px] font-bold text-slate-400 transition hover:bg-white/5 hover:text-white"
            >
              Cerrar sesión
            </button>
          ) : null}
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
