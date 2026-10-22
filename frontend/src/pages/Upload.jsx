import { useRef } from "react";
import Icon from "../components/Icon";

function formatBytes(bytes) {
  if (!bytes) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ProgressSteps() {
  const steps = ["Cargar", "Clasificar", "Revisar", "Calcular"];
  return (
    <div className="mx-auto flex w-full max-w-[820px] items-center px-2" aria-label="Progreso del flujo">
      {steps.map((label, index) => (
        <div className="flex flex-1 items-center" key={label}>
          <div className="flex items-center gap-2.5">
            <span className={`flex h-9 w-9 items-center justify-center rounded-full border text-[10px] font-extrabold ${index === 0 ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-400"}`}>
              0{index + 1}
            </span>
            <span className={`hidden text-[11px] font-bold sm:block ${index === 0 ? "text-ink" : "text-slate-400"}`}>
              {label}
            </span>
          </div>
          {index < steps.length - 1 ? <span className="mx-3 h-px flex-1 bg-slate-200" /> : null}
        </div>
      ))}
    </div>
  );
}

export default function Upload({ files = [], error, backendStatus, backendError, onFilesSelected, onClear, onStart }) {
  const inputRef = useRef(null);

  return (
    <main className="mx-auto w-full max-w-[1440px] px-5 py-10 sm:px-8 lg:px-10 lg:py-14">
      <div className="mx-auto max-w-5xl">
        <div className="mb-5 inline-flex items-center gap-3 text-[10px] font-extrabold uppercase tracking-[0.2em] text-accent-dark">
          <span className="h-px w-8 bg-accent" />
          Carga inteligente de documentación
        </div>

        <h1 className="max-w-3xl font-display text-4xl font-bold leading-[1.02] tracking-[-0.045em] text-ink sm:text-5xl lg:text-[58px]">
          Subí los planos. <span className="bg-gradient-to-r from-accent-dark via-accent to-cyan-500 bg-clip-text text-transparent">El sistema los clasifica.</span>
        </h1>

        <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-500 sm:text-base">
          Podés cargar PDF sueltos o uno de varias páginas. El sistema propone la clasificación y presenta las medidas respaldadas para revisión antes de calcular.
        </p>
        <p className="mt-3 max-w-3xl rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">
          Para probar cómputos, empezá con plantas, detalles, cuadros y pórticos estructurales. Los planos de arquitectura e instalaciones pueden añadirse como contexto; clasificarlos no implica que aporten cantidades estructurales.
        </p>

        {backendStatus ? (
          <p className="mt-4 inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[11px] font-bold text-emerald-800">
            Backend conectado · API {backendStatus.version} · {backendStatus.build}
          </p>
        ) : null}
        {backendError ? (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
            <strong>No se puede iniciar un análisis todavía.</strong> {backendError}
          </div>
        ) : null}
        {backendStatus?.ocr && !backendStatus.ocr.listo ? <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950" role="status"><strong>El OCR no está operativo.</strong> {backendStatus.ocr.mensaje} Ejecutá <code>INSTALAR_OCR_WINDOWS.bat</code> y después <code>VERIFICAR_ENTORNO.bat</code>. El texto nativo puede analizarse, pero no se podrán recuperar con fiabilidad las cotas dibujadas o escaneadas hasta completar este paso.</div> : null}

        <div className="my-10">
          <ProgressSteps />
        </div>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-[0_20px_50px_rgba(16,34,53,.07)] sm:p-7 lg:p-8">
          <input
            ref={inputRef}
            className="sr-only"
            type="file"
            accept="application/pdf,.pdf"
            multiple
            onChange={(event) => { onFilesSelected(event.target.files); event.target.value = ""; }}
          />

          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="flex w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/60 px-6 py-12 text-center transition hover:border-accent/50 hover:bg-accent/[0.025]"
          >
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 text-accent">
              <Icon name="upload" size={25} />
            </span>
            <strong className="mt-4 text-sm font-extrabold text-ink">Seleccionar planos PDF</strong>
            <span className="mt-1 text-xs text-slate-400">Podés seleccionar varios archivos a la vez · máximo 25 MB por PDF</span>
          </button>

          {files.length ? (
            <div className="mt-6 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-accent-dark">Documentos cargados</span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-500">{files.length} PDF{files.length === 1 ? "" : "s"}</span>
              </div>

              {files.map((file, index) => (
                <div key={`${file.name}-${file.size}-${index}`} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-500">
                    <Icon name="file" size={17} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-bold text-ink">{file.name}</div>
                    <div className="mt-0.5 text-[10px] text-slate-400">{formatBytes(file.size)} · pendiente de clasificación</div>
                  </div>
                  <button type="button" onClick={() => onClear(index)} className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label={`Quitar ${file.name}`}>
                    <Icon name="x" size={14} />
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          {error ? (
            <div className="mt-4 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs font-semibold text-red-600" role="alert">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-100 font-extrabold">!</span>
              {error}
            </div>
          ) : null}

          <div className="mt-7 flex flex-col gap-4 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-400">
              <Icon name="shield" size={16} />
              Las medidas propuestas y los límites de lectura se muestran para revisión profesional.
            </div>
            <button
              className="inline-flex min-h-12 items-center justify-center gap-3 rounded-xl border border-accent bg-accent px-6 text-xs font-extrabold text-white shadow-[0_10px_25px_rgba(36,183,166,.2)] transition hover:border-accent-dark hover:bg-accent-dark disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none"
              type="button"
              onClick={() => onStart()}
              disabled={!files.length || Boolean(backendError)}
            >
              Analizar documentación
              <Icon name="arrowRight" size={18} />
            </button>
          </div>
        </section>

      </div>
    </main>
  );
}
