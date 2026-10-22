import Icon from "./Icon";

function Header({ onNewAnalysis, onNavigate }) {
  return (
    <header className="sticky top-0 z-30 h-[76px] border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="flex h-full items-center justify-between px-6 lg:px-8">
        {/* Mobile logo */}
        <div className="flex items-center gap-3 lg:hidden">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-950 text-white">
            <Icon name="layers" size={18} />
          </div>

          <div>
            <p className="font-display text-sm font-bold tracking-tight text-ink">
              CómputoEstIA
            </p>
            <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-slate-400">
              Ingeniería inteligente
            </p>
          </div>
        </div>

        {/* System status */}
        <div className="hidden items-center gap-2 lg:flex">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent" />
          </span>

          <span className="text-xs font-medium text-slate-500">
            Sistema operativo
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onNewAnalysis}
            className="inline-flex items-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            <Icon name="plus" size={17} />
            <span>Nuevo análisis</span>
          </button>

          <button
            type="button"
            onClick={() => onNavigate("dashboard")}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-700 transition hover:bg-slate-200"
            aria-label="Ir al dashboard"
          >
            LS
          </button>
        </div>
      </div>
    </header>
  );
}

export default Header;