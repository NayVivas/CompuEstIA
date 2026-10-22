import Icon from "./Icon";

function PlaceholderView({
  title,
  description,
  icon = "layers",
  action,
  onAction,
}) {
  return (
    <main className="mx-auto w-full max-w-[1440px] px-5 py-10 sm:px-8 lg:px-10 lg:py-12">
      <div className="flex min-h-[520px] items-center justify-center">
        <section className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-[0_20px_50px_rgba(16,34,53,.06)] sm:p-12">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-lg">
            <Icon name={icon} size={28} />
          </div>

          <h1 className="mt-6 font-display text-3xl font-bold tracking-tight text-ink">
            {title}
          </h1>

          <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-slate-500">
            {description}
          </p>

          {action ? (
            <button
              type="button"
              onClick={onAction}
              className="mt-7 inline-flex items-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-800"
            >
              {action}
              <Icon name="arrowRight" size={17} />
            </button>
          ) : null}
        </section>
      </div>
    </main>
  );
}

export default PlaceholderView;