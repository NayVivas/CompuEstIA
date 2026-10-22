import { useState } from "react";
import Icon from "../components/Icon";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(event) {
    event.preventDefault();

    setError("");

    if (!email.trim() || !password.trim()) {
      setError("Ingresá tu email y contraseña.");
      return;
    }

    // Autenticación provisoria.
    // Más adelante esto se conecta con Django.
    onLogin();
  }

  return (
    <main className="min-h-screen bg-mist">
      <div className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
        {/* Panel izquierdo */}
        <section className="relative hidden overflow-hidden bg-slate-950 lg:flex">
          <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-accent/15 blur-3xl" />
          <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />

          <div className="relative flex w-full flex-col justify-between p-12 xl:p-16">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 text-accent">
                <Icon name="scan" size={22} />
              </div>

              <div>
                <p className="font-display text-base font-bold tracking-tight text-white">
                  CómputoEstIA
                </p>
                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-slate-500">
                  Ingeniería + IA
                </p>
              </div>
            </div>

            <div className="max-w-xl">
              <p className="mb-5 text-[10px] font-extrabold uppercase tracking-[0.2em] text-accent">
                Ingeniería · Ciencia de datos · IA
              </p>

              <h1 className="font-display text-5xl font-bold leading-[1.02] tracking-[-0.045em] text-white xl:text-6xl">
                Del plano al{" "}
                <span className="text-accent">
                  dato confiable.
                </span>
              </h1>

              <p className="mt-6 max-w-lg text-sm leading-7 text-slate-400">
                Una plataforma para organizar documentación técnica,
                analizar planos y transformar información de ingeniería
                en resultados medibles y trazables.
              </p>

              <div className="mt-8 flex flex-wrap gap-2">
                {[
                  "Cómputos métricos",
                  "Visión computacional",
                  "Trazabilidad",
                ].map((item) => (
                  <span
                    key={item}
                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wider text-slate-400"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-600">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              Entorno de ingeniería inteligente
            </div>
          </div>
        </section>

        {/* Panel derecho */}
        <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-8">
          <div className="w-full max-w-[430px]">
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-accent">
                <Icon name="scan" size={22} />
              </div>

              <div>
                <p className="font-display text-base font-bold tracking-tight text-ink">
                  CómputoEstIA
                </p>
                <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-slate-400">
                  Ingeniería + IA
                </p>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-[0_25px_70px_rgba(16,34,53,.08)] sm:p-9">
              <div>
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent">
                  <Icon name="lock" size={21} />
                </div>

                <p className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">
                  Acceso a la plataforma
                </p>

                <h2 className="mt-2 font-display text-3xl font-bold tracking-tight text-ink">
                  Ingresá a tu cuenta
                </h2>

                <p className="mt-3 text-sm leading-6 text-slate-500">
                  Accedé a tus proyectos, documentación y análisis de
                  ingeniería.
                </p>
              </div>

              <form
                onSubmit={handleSubmit}
                className="mt-8 space-y-5"
              >
                <div>
                  <label
                    htmlFor="email"
                    className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.14em] text-slate-500"
                  >
                    Email
                  </label>

                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="nombre@empresa.com"
                    autoComplete="email"
                    className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-medium text-ink outline-none transition placeholder:text-slate-400 focus:border-accent focus:bg-white focus:ring-4 focus:ring-accent/10"
                  />
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <label
                      htmlFor="password"
                      className="block text-[10px] font-extrabold uppercase tracking-[0.14em] text-slate-500"
                    >
                      Contraseña
                    </label>

                    <button
                      type="button"
                      className="text-[10px] font-bold text-accent-dark transition hover:text-accent"
                    >
                      ¿Olvidaste tu contraseña?
                    </button>
                  </div>

                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(event) =>
                      setPassword(event.target.value)
                    }
                    placeholder="••••••••"
                    autoComplete="current-password"
                    className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-medium text-ink outline-none transition placeholder:text-slate-400 focus:border-accent focus:bg-white focus:ring-4 focus:ring-accent/10"
                  />
                </div>

                {error ? (
                  <div
                    role="alert"
                    className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs font-semibold text-red-600"
                  >
                    {error}
                  </div>
                ) : null}

                <button
                  type="submit"
                  className="flex h-12 w-full items-center justify-center gap-3 rounded-xl bg-slate-950 text-xs font-extrabold text-white shadow-[0_12px_30px_rgba(16,34,53,.15)] transition hover:-translate-y-0.5 hover:bg-ink"
                >
                  Ingresar
                  <Icon name="arrowRight" size={17} />
                </button>
              </form>

              <div className="mt-7 flex items-center justify-center gap-2 text-[10px] font-semibold text-slate-400">
                <Icon name="shield" size={14} />
                Acceso seguro a tu entorno de trabajo
              </div>
            </div>

            <p className="mt-6 text-center text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
              CómputoEstIA · v0.1
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}