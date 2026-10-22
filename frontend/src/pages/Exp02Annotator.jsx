import { useCallback, useEffect, useMemo, useState } from "react";
import { exp02ExportarUrl, exp02GuardarAnotacion, exp02ImagenUrl, exp02Paginas, exp02Resumen } from "../services/exp02";

const DISCIPLINAS = {
  arquitectura: "Arquitectura", estructura: "Estructura", sanitarias: "Sanitarias", electricidad: "Electricidad", gas: "Gas",
  climatizacion: "Climatización", incendio: "Incendio", implantacion_topografia: "Implantación / topografía", otra: "Otra", desconocida: "Desconocida / revisión"
};
const ROLES = {
  planta: "Planta", corte: "Corte", elevacion_fachada: "Elevación / fachada", detalle: "Detalle", cuadro_planilla: "Cuadro / planilla",
  isometrico: "Isométrico", esquema_diagrama: "Esquema / diagrama", implantacion: "Implantación", situacion: "Situación / emplazamiento",
  memoria_especificacion: "Memoria / especificación", indice_lista_planos: "Índice / lista de planos", modelo_3d: "Modelo 3D / axonometría", otro: "Otro"
};
const CONTENIDOS = {
  Estructura: {
    fundaciones: "Fundaciones", columnas_pilares: "Columnas / pilares", vigas: "Vigas", losas_forjados: "Losas / forjados", muros_estructurales: "Muros estructurales",
    escaleras_estructurales: "Escaleras estructurales", cubiertas_estructurales: "Cubiertas estructurales", armaduras_acero: "Armaduras / acero", elementos_estructurales_generales: "Elementos estructurales generales"
  },
  Arquitectura: {
    distribucion_espacios: "Distribución / espacios", pisos: "Pisos", cielorrasos: "Cielorrasos", cubiertas: "Cubiertas", puertas_carpinterias: "Puertas / carpinterías",
    ventanas_carpinterias: "Ventanas / carpinterías", fachadas: "Fachadas", terminaciones: "Terminaciones", detalles_constructivos: "Detalles constructivos"
  },
  Sanitarias: {
    agua_fria: "Agua fría", agua_caliente: "Agua caliente", cloacal: "Cloacal", pluvial: "Pluvial", artefactos_sanitarios: "Artefactos sanitarios", canerias_sanitarias: "Cañerías sanitarias"
  },
  Electricidad: {
    iluminacion: "Iluminación", tomacorrientes: "Tomacorrientes", fuerza: "Fuerza", tableros: "Tableros", canalizaciones: "Canalizaciones", baja_tension: "Baja tensión"
  },
  Gas: { gas_general: "Gas general", artefactos_gas: "Artefactos de gas", regulacion_gas: "Regulación", canerias_gas: "Cañerías de gas" },
  Climatización: { equipos_climatizacion: "Equipos", conductos_climatizacion: "Conductos", distribucion_climatizacion: "Distribución", control_climatizacion: "Control" },
  Incendio: { deteccion_incendio: "Detección", extincion_incendio: "Extinción", senalizacion_incendio: "Señalización", red_incendio: "Red de incendio" },
  "Implantación / topografía": { terreno: "Terreno", ejes_replanteo: "Ejes / replanteo", niveles: "Niveles", coordenadas: "Coordenadas", implantacion: "Implantación" },
  Otro: { otro: "Otro contenido" }
};
const LEGACY = {
  planta_fundaciones: { d: ["estructura"], r: ["planta"], c: ["fundaciones"] }, columnas: { d: ["estructura"], r: ["planta"], c: ["columnas_pilares"] },
  vigas: { d: ["estructura"], r: ["planta"], c: ["vigas"] }, losas: { d: ["estructura"], r: ["planta"], c: ["losas_forjados"] },
  cuadro_fundaciones: { d: ["estructura"], r: ["cuadro_planilla"], c: ["fundaciones"] }, detalle_estructural: { d: ["estructura"], r: ["detalle"], c: ["elementos_estructurales_generales"] }
};

function toggle(list, value) { return list.includes(value) ? list.filter(x => x !== value) : [...list, value]; }
function Chip({active, children, onClick}) { return <button type="button" onClick={onClick} className={`rounded-lg border px-2.5 py-1.5 text-[10px] font-bold transition ${active ? "border-accent bg-accent/[.09] text-slate-900" : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"}`}>{children}</button>; }
function Section({title, hint, children}) { return <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4"><div><p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">{title}</p>{hint && <p className="mt-1 text-[9px] leading-4 text-slate-400">{hint}</p>}</div><div className="mt-3 flex flex-wrap gap-1.5">{children}</div></div>; }

export default function Exp02Annotator({ dataset = "exp02" }) {
  const isExp16 = dataset === "exp16";
  const reviewerStorageKey = `${dataset}-reviewer`;
  const [summary, setSummary] = useState(null), [projectId, setProjectId] = useState(""), [pages, setPages] = useState([]), [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true), [saving, setSaving] = useState(false), [error, setError] = useState("");
  const [reviewer, setReviewer] = useState(() => localStorage.getItem(reviewerStorageKey) || "");
  const [filter, setFilter] = useState("pendientes");
  const [disciplines, setDisciplines] = useState([]), [roles, setRoles] = useState([]), [contents, setContents] = useState([]);
  const [decision, setDecision] = useState("pendiente"), [ambiguous, setAmbiguous] = useState("no"), [reason, setReason] = useState(""), [evidence, setEvidence] = useState(""), [notes, setNotes] = useState("");
  const [includeMetrics, setIncludeMetrics] = useState(true);

  const load = useCallback(async (pid = projectId) => {
    setLoading(true); setError("");
    try { const [s, p] = await Promise.all([exp02Resumen(dataset), exp02Paginas(pid || undefined, dataset)]); setSummary(s); setPages(p); setIndex(0); if (!pid && s.proyectos?.length) setProjectId(s.proyectos[0]); }
    catch (e) { setError(e.message); } finally { setLoading(false); }
  }, [dataset, projectId]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setProjectId(""); setFilter("pendientes"); load("");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [dataset]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!projectId) return undefined;
    const timer = window.setTimeout(() => load(projectId), 0);
    return () => window.clearTimeout(timer);
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const visiblePages = useMemo(() => filter === "todas" ? pages : filter === "ambiguas" ? pages.filter(p => p.anotacion?.ambiguo === "si") : filter === "ocr" ? pages.filter(p => p.requiere_ocr === true || String(p.requiere_ocr).toLowerCase() === "true") : pages.filter(p => p.anotacion?.decision !== "confirmada"), [pages, filter]);
  const current = visiblePages[index] || null;

  useEffect(() => {
    if (!current) return;
    const a = current.anotacion || {}, legacy = a.label_ground_truth && LEGACY[a.label_ground_truth];
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDisciplines(a.disciplinas || legacy?.d || (a.disciplina && a.disciplina !== "mixto" ? [a.disciplina] : []));
    setRoles(a.roles_documentales || legacy?.r || (a.rol_documental && a.rol_documental !== "mixto" ? [a.rol_documental] : []));
    setContents(a.contenidos || legacy?.c || (a.subtipo_documental && a.subtipo_documental !== "mixto" ? [a.subtipo_documental] : []));
    setReviewer(a.revisor || reviewer); setDecision(a.decision || "pendiente"); setAmbiguous(a.ambiguo || "no"); setReason(a.motivo_ambiguedad || ""); setEvidence(a.evidencia_profesional || ""); setNotes(a.observaciones || "");
    setIncludeMetrics(a.incluir_en_metricas ?? true);
  }, [current?.proyecto_id, current?.documento, current?.pagina]); // eslint-disable-line react-hooks/exhaustive-deps

  function move(delta) { setIndex(i => Math.max(0, Math.min(visiblePages.length - 1, i + delta))); }
  async function save(goNext = true) {
    if (!current) return;
    if (!reviewer.trim()) return setError("Ingresá el nombre del revisor profesional antes de guardar.");
    if (!disciplines.length) return setError("Seleccioná al menos una disciplina. Si la página no permite identificarla, usá Desconocida / revisión.");
    if (!roles.length) return setError("Seleccioná al menos un rol documental.");
    if (!contents.length) return setError("Seleccioná al menos un contenido técnico. Si no hay contenido específico, usá Otro contenido.");
    if (ambiguous === "si" && !reason.trim()) return setError("Una página ambigua requiere un motivo.");
    setSaving(true); setError("");
    try {
      const payload = { proyecto_id: String(current.proyecto_id), documento: String(current.documento), pagina: Number(current.pagina), disciplinas: disciplines, roles_documentales: roles, contenidos: contents,
        revisor: reviewer.trim(), decision, ambiguo: ambiguous, motivo_ambiguedad: reason.trim(), evidencia_profesional: evidence.trim(), observaciones: notes.trim() };
      if (isExp16) payload.incluir_en_metricas = includeMetrics;
      const result = await exp02GuardarAnotacion(payload, dataset); localStorage.setItem(reviewerStorageKey, reviewer.trim());
      setPages(prev => prev.map(p => p.proyecto_id === current.proyecto_id && p.documento === current.documento && Number(p.pagina) === Number(current.pagina) ? {...p, anotacion: result.anotacion} : p));
      setSummary(await exp02Resumen(dataset)); if (goNext && visiblePages.length > 1) setIndex(i => Math.min(i + 1, visiblePages.length - 1));
    } catch (e) { setError(e.message); } finally { setSaving(false); }
  }
  useEffect(() => { const onKey = e => { if (["TEXTAREA","INPUT","SELECT"].includes(e.target?.tagName)) return; if (e.key === "ArrowRight") move(1); if (e.key === "ArrowLeft") move(-1); if (e.key.toLowerCase() === "s") save(true); }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); });

  if (loading) return <div className="p-8 text-sm font-semibold text-slate-500">Cargando {isExp16 ? "EXP16" : "EXP-02"}…</div>;
  return <div className="flex h-full min-h-0 flex-col bg-slate-50">
    <header className="border-b border-slate-200 bg-white px-6 py-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] font-black uppercase tracking-[.18em] text-accent">{isExp16 ? "EXP16 · Proyectos independientes" : "EXP-02 · Ground Truth científico"}</p><h1 className="mt-1 text-xl font-black text-slate-900">Anotación profesional multietiqueta</h1><p className="mt-1 max-w-3xl text-[11px] text-slate-500">La página puede pertenecer a varias disciplinas, contener varios tipos de representación y mostrar varios sistemas. No se fuerza una única clase.</p></div><a href={exp02ExportarUrl(dataset)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[10px] font-extrabold text-slate-700 hover:bg-slate-50">Exportar Ground Truth {isExp16 ? "JSON" : "CSV"}</a></div></header>
    <div className="grid min-h-0 flex-1 grid-cols-[230px_minmax(0,1fr)_390px]">
      <aside className="min-h-0 overflow-y-auto border-r border-slate-200 bg-white p-4"><select value={projectId} onChange={e=>setProjectId(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700">{summary?.proyectos?.map(p=><option key={p}>{p}</option>)}</select><div className={`mt-3 grid ${isExp16 ? "grid-cols-4" : "grid-cols-3"} gap-1 rounded-lg bg-slate-100 p-1`}><button onClick={()=>setFilter("pendientes")} className={`rounded-md px-1 py-2 text-[9px] font-bold ${filter==="pendientes"?"bg-white shadow-sm":"text-slate-500"}`}>Pend.</button><button onClick={()=>setFilter("todas")} className={`rounded-md px-1 py-2 text-[9px] font-bold ${filter==="todas"?"bg-white shadow-sm":"text-slate-500"}`}>Todas</button><button onClick={()=>setFilter("ambiguas")} className={`rounded-md px-1 py-2 text-[9px] font-bold ${filter==="ambiguas"?"bg-white shadow-sm":"text-slate-500"}`}>Ambig.</button>{isExp16 && <button onClick={()=>setFilter("ocr")} className={`rounded-md px-1 py-2 text-[9px] font-bold ${filter==="ocr"?"bg-white shadow-sm":"text-slate-500"}`}>OCR</button>}</div><div className="mt-3 rounded-lg bg-slate-50 p-3 text-[9px] text-slate-500"><b>{summary?.confirmadas ?? 0}</b> confirmadas · <b>{summary?.pendientes ?? 0}</b> pendientes<br/><b>{summary?.pdfs ?? 0}</b> PDFs · <b>{summary?.total_paginas ?? 0}</b> páginas{isExp16 && <><br/><b>{summary?.requieren_ocr ?? 0}</b> requieren OCR · <b>{summary?.grupos_fuente ?? 0}</b> fuentes</>}</div><div className="mt-3 space-y-1">{visiblePages.map((p,i)=>{const done=p.anotacion?.decision==="confirmada"; const ocr=p.requiere_ocr===true||String(p.requiere_ocr).toLowerCase()==="true"; return <button key={`${p.documento}-${p.pagina}`} onClick={()=>setIndex(i)} className={`w-full rounded-lg border px-3 py-2 text-left ${i===index?"border-accent bg-accent/[.05]":"border-transparent hover:bg-slate-50"}`}><div className="flex items-center justify-between"><span className="truncate text-[10px] font-extrabold text-slate-700">Pág. {p.pagina}</span><span className="flex gap-1">{ocr&&<span className="rounded-full border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[8px] font-bold text-violet-700">OCR</span>}<span className={`rounded-full border px-1.5 py-0.5 text-[8px] font-bold ${done?"bg-emerald-50 text-emerald-700 border-emerald-200":"bg-amber-50 text-amber-700 border-amber-200"}`}>{done?"OK":"Pend."}</span></span></div><p className="mt-1 truncate text-[9px] text-slate-400">{p.documento}</p></button>})}</div></aside>
      <main className="min-h-0 overflow-auto p-5">{current ? <><div className="mb-3 flex items-center justify-between gap-2"><div><p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{current.proyecto_id} · {current.documento}</p><h2 className="mt-1 text-sm font-black text-slate-800">Página {current.pagina}</h2>{isExp16&&<p className="mt-1 text-[9px] text-slate-400">Fuente: {current.grupo_fuente} · {current.tipo_contenido}</p>}</div><span className="rounded-full bg-slate-100 px-2 py-1 text-[9px] font-bold text-slate-500">{index+1} / {visiblePages.length}</span></div><div className="flex min-h-[540px] items-center justify-center overflow-auto rounded-xl border border-slate-200 bg-slate-200/60 p-3 shadow-inner"><img src={exp02ImagenUrl(String(current.proyecto_id),String(current.documento),Number(current.pagina),1.35,dataset)} alt={`Página ${current.pagina}`} className="max-h-[72vh] max-w-full rounded bg-white shadow-lg" /></div><div className="mt-3 flex justify-between"><button disabled={index===0} onClick={()=>move(-1)} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 disabled:opacity-40">← Anterior</button><button disabled={index===visiblePages.length-1} onClick={()=>move(1)} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 disabled:opacity-40">Siguiente →</button></div></> : <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-400">No hay páginas para este filtro.</div>}</main>
      <aside className="min-h-0 overflow-y-auto border-l border-slate-200 bg-slate-50 p-4"><div className="rounded-xl border border-accent/20 bg-white p-4"><p className="text-[10px] font-extrabold uppercase tracking-wider text-accent">Decisión profesional</p><label className="mt-3 block text-[10px] font-bold text-slate-500">Revisor</label><input value={reviewer} onChange={e=>setReviewer(e.target.value)} placeholder="Nombre del revisor" className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs outline-none focus:border-accent"/>
        {isExp16 && current?.sugerencias?.length > 0 && <div className="mt-4 rounded-xl border border-cyan-200 bg-cyan-50 p-3"><p className="text-[9px] font-black uppercase tracking-wider text-cyan-800">Sugerencias para revisar</p><div className="mt-2 space-y-2">{current.sugerencias.map((sugerencia, suggestionIndex)=><p key={`${sugerencia.tipo}-${suggestionIndex}`} className="text-[9px] leading-4 text-cyan-900">• {sugerencia.mensaje}</p>)}</div><p className="mt-2 text-[8px] font-semibold text-cyan-700">No se seleccionan etiquetas automáticamente.</p></div>}
        <Section title="1 · Disciplinas" hint="Puede haber más de una en la misma página.">{Object.entries(DISCIPLINAS).map(([v,l])=><Chip key={v} active={disciplines.includes(v)} onClick={()=>setDisciplines(toggle(disciplines,v))}>{l}</Chip>)}</Section>
        <Section title="2 · Roles documentales" hint="Una lámina puede combinar planta, corte, detalle, etc.">{Object.entries(ROLES).map(([v,l])=><Chip key={v} active={roles.includes(v)} onClick={()=>setRoles(toggle(roles,v))}>{l}</Chip>)}</Section>
        <Section title="3 · Sistemas / contenidos" hint="Marcar solo lo que realmente aparece o está definido en la página.">{Object.entries(CONTENIDOS).map(([group, vals])=><div key={group} className="w-full"><p className="mb-1 mt-1 w-full text-[9px] font-black text-slate-400">{group}</p><div className="flex flex-wrap gap-1.5">{Object.entries(vals).map(([v,l])=><Chip key={v} active={contents.includes(v)} onClick={()=>setContents(toggle(contents,v))}>{l}</Chip>)}</div></div>)}</Section>
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[9px] leading-4 text-slate-500">{disciplines.length ? <>Disciplinas: <b>{disciplines.map(d=>DISCIPLINAS[d]).join(" + ")}</b><br/></>:null}{roles.length ? <>Roles: <b>{roles.map(r=>ROLES[r]).join(" + ")}</b><br/></>:null}{contents.length ? <>Contenidos: <b>{contents.length} seleccionados</b></>:null}</div>
        <label className="mt-4 block text-[10px] font-bold text-slate-500">Estado de decisión</label><div className="mt-1 grid grid-cols-2 gap-1"><button onClick={()=>setDecision("confirmada")} className={`rounded-lg border px-2 py-2 text-[9px] font-bold ${decision==="confirmada"?"border-emerald-300 bg-emerald-50 text-emerald-700":"border-slate-200 bg-white"}`}>Confirmada</button><button onClick={()=>setDecision("pendiente")} className={`rounded-lg border px-2 py-2 text-[9px] font-bold ${decision==="pendiente"?"border-accent bg-accent/[.06]":"border-slate-200 bg-white"}`}>Pendiente</button></div>
        <label className="mt-3 block text-[10px] font-bold text-slate-500">¿Página ambigua?</label><div className="mt-1 flex gap-2"><button onClick={()=>setAmbiguous("no")} className={`flex-1 rounded-lg border px-3 py-2 text-xs font-bold ${ambiguous==="no"?"border-accent bg-accent/[.08]":"border-slate-200 bg-white"}`}>No</button><button onClick={()=>setAmbiguous("si")} className={`flex-1 rounded-lg border px-3 py-2 text-xs font-bold ${ambiguous==="si"?"border-amber-400 bg-amber-50":"border-slate-200 bg-white"}`}>Sí</button></div>
        {ambiguous==="si" && <><label className="mt-3 block text-[10px] font-bold text-slate-500">Motivo de ambigüedad *</label><textarea value={reason} onChange={e=>setReason(e.target.value)} rows={3} className="mt-1 w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-xs" placeholder="Qué impide decidir sin asumir…"/></>}
        <label className="mt-3 block text-[10px] font-bold text-slate-500">Evidencia profesional</label><textarea value={evidence} onChange={e=>setEvidence(e.target.value)} rows={3} className="mt-1 w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-xs" placeholder="Rótulo, título, simbología, cuadro, nota o evidencia gráfica…"/>
        <label className="mt-3 block text-[10px] font-bold text-slate-500">Observaciones</label><textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={2} className="mt-1 w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-xs"/>
        {isExp16 && <label className="mt-3 flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3"><input type="checkbox" checked={includeMetrics} onChange={event=>setIncludeMetrics(event.target.checked)} className="mt-0.5 accent-cyan-500"/><span className="text-[9px] leading-4 text-slate-600"><b>Incluir en métricas</b><br/>Desmarcar solamente si es un duplicado, una revisión repetida o una página que no corresponde al conjunto.</span></label>}
        {error && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-[10px] font-semibold text-red-700">{error}</div>}
        <button disabled={saving || !current} onClick={()=>save(true)} className="mt-4 w-full rounded-lg bg-slate-950 px-4 py-3 text-xs font-extrabold text-white disabled:opacity-50">{saving?"Guardando…":"Guardar y siguiente →"}</button><button disabled={saving || !current} onClick={()=>save(false)} className="mt-2 w-full rounded-lg border border-slate-200 px-4 py-2 text-[10px] font-bold text-slate-600">Guardar sin avanzar</button>
      </div><div className="mt-3 rounded-xl border border-slate-200 bg-white p-3"><p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Regla científica</p><p className="mt-1 text-[9px] leading-4 text-slate-500">No usar el nombre del archivo ni la sugerencia como etiqueta automática. Mirar la página, identificar disciplinas, roles y contenidos, y registrar evidencia.</p><p className="mt-2 text-[9px] text-slate-400">←/→ navegar · S guardar y avanzar</p></div></aside>
    </div>
  </div>;
}
