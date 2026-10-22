import { useState } from "react";
import Icon from "../components/Icon";

function NewProject({ onCancel, onCreate }) {
  const [form, setForm] = useState({
    name: "",
    client: "",
    location: "",
    type: "Edificio residencial",
    description: "",
  });

  const [error, setError] = useState("");

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));

    setError("");
  }

  function handleSubmit(event) {
    event.preventDefault();

    if (!form.name.trim()) {
      setError("Ingresá el nombre del proyecto.");
      return;
    }

    if (!form.client.trim()) {
      setError("Ingresá el cliente o comitente.");
      return;
    }

    if (!form.location.trim()) {
      setError("Ingresá la ubicación del proyecto.");
      return;
    }

    onCreate({
      ...form,
      name: form.name.trim(),
      client: form.client.trim(),
      location: form.location.trim(),
      description: form.description.trim(),
    });
  }

  return (
    <main className="mx-auto w-full max-w-[1100px] px-5 py-10 sm:px-8 lg:px-10 lg:py-12">
      {/* Header */}
      <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
        <div>
          <div className="inline-flex items-center gap-3 text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">
            <span className="h-px w-8 bg-accent" />
            Gestión de proyectos
          </div>

          <h1 className="mt-3 font-display text-4xl font-bold tracking-[-0.035em] text-ink sm:text-5xl">
            Nuevo proyecto
          </h1>

          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
            Creá el proyecto donde vas a organizar planos, análisis y
            resultados.
          </p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-xs font-bold text-ink transition hover:border-slate-400"
        >
          <Icon name="arrowRight" size={16} />
          Volver
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="mt-8">
        <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_20px_50px_rgba(16,34,53,.06)]">
          <div className="border-b border-slate-100 px-6 py-5 sm:px-8">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-950 text-white">
                <Icon name="building" size={19} />
              </div>

              <div>
                <h2 className="font-display text-lg font-bold text-ink">
                  Información general
                </h2>

                <p className="mt-0.5 text-[11px] text-slate-400">
                  Datos básicos de la obra.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-6 p-6 sm:grid-cols-2 sm:p-8">
            {/* Nombre */}
            <div className="sm:col-span-2">
              <label
                htmlFor="name"
                className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.12em] text-slate-500"
              >
                Nombre del proyecto
              </label>

              <input
                id="name"
                name="name"
                type="text"
                value={form.name}
                onChange={handleChange}
                placeholder="Ej. Edificio Norte"
                className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-medium text-ink outline-none transition placeholder:text-slate-400 focus:border-accent focus:bg-white focus:ring-4 focus:ring-accent/10"
              />
            </div>

            {/* Cliente */}
            <div>
              <label
                htmlFor="client"
                className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.12em] text-slate-500"
              >
                Cliente / Comitente
              </label>

              <input
                id="client"
                name="client"
                type="text"
                value={form.client}
                onChange={handleChange}
                placeholder="Ej. Constructora Norte S.A."
                className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-medium text-ink outline-none transition placeholder:text-slate-400 focus:border-accent focus:bg-white focus:ring-4 focus:ring-accent/10"
              />
            </div>

            {/* Ubicación */}
            <div>
              <label
                htmlFor="location"
                className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.12em] text-slate-500"
              >
                Ubicación
              </label>

              <input
                id="location"
                name="location"
                type="text"
                value={form.location}
                onChange={handleChange}
                placeholder="Ej. Buenos Aires"
                className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-medium text-ink outline-none transition placeholder:text-slate-400 focus:border-accent focus:bg-white focus:ring-4 focus:ring-accent/10"
              />
            </div>

            {/* Tipo */}
            <div>
              <label
                htmlFor="type"
                className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.12em] text-slate-500"
              >
                Tipo de proyecto
              </label>

              <select
                id="type"
                name="type"
                value={form.type}
                onChange={handleChange}
                className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm font-medium text-ink outline-none transition focus:border-accent focus:bg-white focus:ring-4 focus:ring-accent/10"
              >
                <option>Edificio residencial</option>
                <option>Conjunto de viviendas</option>
                <option>Estructura industrial</option>
                <option>Edificio comercial</option>
                <option>Obra civil</option>
                <option>Otro</option>
              </select>
            </div>

            {/* Descripción */}
            <div>
              <label
                htmlFor="description"
                className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.12em] text-slate-500"
              >
                Descripción
              </label>

              <textarea
                id="description"
                name="description"
                value={form.description}
                onChange={handleChange}
                placeholder="Descripción opcional del proyecto..."
                rows={3}
                className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-ink outline-none transition placeholder:text-slate-400 focus:border-accent focus:bg-white focus:ring-4 focus:ring-accent/10"
              />
            </div>
          </div>

          {/* Error */}
          {error ? (
            <div className="mx-6 mb-6 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 sm:mx-8">
              <Icon name="x" size={17} />

              <span className="text-xs font-semibold text-red-700">
                {error}
              </span>
            </div>
          ) : null}

          {/* Actions */}
          <div className="flex flex-col-reverse justify-end gap-3 border-t border-slate-100 bg-slate-50/60 px-6 py-5 sm:flex-row sm:px-8">
            <button
              type="button"
              onClick={onCancel}
              className="min-h-11 rounded-lg border border-slate-300 bg-white px-5 text-xs font-bold text-slate-600 transition hover:border-slate-400 hover:text-ink"
            >
              Cancelar
            </button>

            <button
              type="submit"
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-slate-950 px-5 text-xs font-bold text-white shadow-sm transition hover:-translate-y-px hover:bg-slate-800"
            >
              <Icon name="check" size={17} />
              Crear proyecto
            </button>
          </div>
        </section>
      </form>
    </main>
  );
}

export default NewProject;