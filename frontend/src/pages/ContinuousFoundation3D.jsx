import { useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Grid, OrbitControls } from "@react-three/drei";
import { Shape } from "three";

import { selectReviewedContinuousSegments } from "../utils/continuous3dSource.js";

function SegmentMesh({ segment, center, selected, onSelect }) {
  const shape = useMemo(() => {
    const base = Number(segment.ancho_base_m);
    const top = Number(segment.ancho_superior_m);
    const height = Number(segment.altura_m);
    const section = new Shape();
    section.moveTo(-base / 2, 0);
    section.lineTo(base / 2, 0);
    section.lineTo(top / 2, height);
    section.lineTo(-top / 2, height);
    section.closePath();
    return section;
  }, [segment.ancho_base_m, segment.ancho_superior_m, segment.altura_m]);
  const scale = Number(segment.puntos_por_metro);
  const dx = (segment.fin.x - segment.inicio.x) / scale;
  const dz = (segment.fin.y - segment.inicio.y) / scale;
  const length = Math.hypot(dx, dz);
  return <mesh
    position={[(segment.inicio.x - center.x) / scale, 0, (segment.inicio.y - center.y) / scale]}
    rotation={[0, Math.atan2(dx, dz), 0]}
    onClick={(event) => { event.stopPropagation(); onSelect(segment.id); }}
    castShadow receiveShadow
  >
    <extrudeGeometry args={[shape, { depth: length, bevelEnabled: false, steps: 1 }]} />
    <meshStandardMaterial color={selected ? "#f97316" : "#0d9488"} roughness={0.8} metalness={0.05} />
  </mesh>;
}

export default function ContinuousFoundation3D({ project, results, onBack }) {
  const segments = useMemo(() => selectReviewedContinuousSegments(results), [results]);
  const pages = [...new Map(segments.map((item) => [
    `${item.fuente.sha256}:${item.fuente.pagina}`,
    { key: `${item.fuente.sha256}:${item.fuente.pagina}`, label: `${item.fuente.archivo || "Plano"} · pág. ${item.fuente.pagina}` },
  ])).values()];
  const [selectedPage, setSelectedPage] = useState(pages[0]?.key || "");
  const [selectedId, setSelectedId] = useState(null);
  const page = pages.some((item) => item.key === selectedPage) ? selectedPage : pages[0]?.key;
  const visible = segments.filter((item) => `${item.fuente.sha256}:${item.fuente.pagina}` === page);
  const allPoints = visible.flatMap((item) => [item.inicio, item.fin]);
  const center = {
    x: allPoints.length ? (Math.min(...allPoints.map((point) => point.x)) + Math.max(...allPoints.map((point) => point.x))) / 2 : 0,
    y: allPoints.length ? (Math.min(...allPoints.map((point) => point.y)) + Math.max(...allPoints.map((point) => point.y))) / 2 : 0,
  };
  const span = visible.length ? Math.max(
    (Math.max(...allPoints.map((point) => point.x)) - Math.min(...allPoints.map((point) => point.x))) / Number(visible[0].puntos_por_metro),
    (Math.max(...allPoints.map((point) => point.y)) - Math.min(...allPoints.map((point) => point.y))) / Number(visible[0].puntos_por_metro),
    8,
  ) : 8;
  const chosen = segments.find((item) => item.id === selectedId);
  const tracedLength = segments.reduce((sum, item) => sum + Number(item.longitud_m), 0);
  const totalLength = Number(results?.longitud_total_cimientos_corridos_m) || 0;

  return <main className="mx-auto max-w-[1500px] space-y-5 p-6 sm:p-8">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="text-xs font-bold uppercase tracking-wider text-teal-700">Modelo 3D revisado</p>
        <h1 className="text-3xl font-bold">Cimientos corridos · {project?.name || project?.nombre || "Proyecto"}</h1>
        <p className="text-sm text-slate-600">Cada volumen corresponde a un tramo ubicado en una planta y confirmado en la revisión.</p>
      </div>
      <button type="button" onClick={onBack} className="rounded border bg-white px-4 py-2">Volver al proyecto</button>
    </header>
    {!segments.length ? <p className="rounded-xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-950">Este análisis contiene longitudes, pero ningún tramo con extremos, escala y sección confirmados. Revisá la planta y trazá los recorridos sobre una página calibrada para construir el 3D.</p> : <>
      <div className="flex flex-wrap items-center gap-4 rounded-xl border bg-white p-4 text-sm">
        <label>Página
          <select value={page} onChange={(event) => { setSelectedPage(event.target.value); setSelectedId(null); }} className="ml-2 rounded border p-2">
            {pages.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
        </label>
        <span>{segments.length} tramos con geometría · {tracedLength.toFixed(2)} m representados de {totalLength.toFixed(2)} m computados</span>
      </div>
      {Math.abs(tracedLength - totalLength) > 0.05 && <p className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm">El cómputo incluye longitudes sin recorrido verificable. El modelo 3D representa solo {tracedLength.toFixed(2)} m; el resto no se dibuja.</p>}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="h-[580px] overflow-hidden rounded-xl border bg-slate-900">
          <Canvas key={page} shadows camera={{ position: [span * 0.65, span * 0.9, span * 0.9], fov: 50, near: 0.1, far: Math.max(span * 20, 100) }}>
            <color attach="background" args={["#0f172a"]} />
            <ambientLight intensity={1.5} /><directionalLight position={[12, 22, 15]} intensity={2.4} castShadow />
            <Grid args={[Math.max(span * 1.5, 20), Math.max(span * 1.5, 20)]} cellSize={1} cellColor="#475569" sectionColor="#64748b" fadeDistance={span * 3} />
            {visible.map((item) => <SegmentMesh key={item.id} segment={item} center={center} selected={item.id === selectedId} onSelect={setSelectedId} />)}
            <OrbitControls makeDefault target={[0, 0, 0]} minDistance={1} maxDistance={Math.max(span * 6, 30)} />
          </Canvas>
        </div>
        <aside className="rounded-xl border bg-white p-5 text-sm">
          <h2 className="text-lg font-bold">Recorrido seleccionado</h2>
          {chosen ? <dl className="mt-3 space-y-2">
            <div><dt className="font-semibold">Referencia</dt><dd>{chosen.referencia}</dd></div>
            <div><dt className="font-semibold">Origen</dt><dd>{chosen.fuente.archivo} · pág. {chosen.fuente.pagina}</dd></div>
            <div><dt className="font-semibold">Longitud</dt><dd>{Number(chosen.longitud_m).toFixed(2)} m</dd></div>
            <div><dt className="font-semibold">Sección</dt><dd>{chosen.ancho_superior_m} / {chosen.ancho_base_m} × {chosen.altura_m} m</dd></div>
            <div><dt className="font-semibold">Verificación</dt><dd>{chosen.origen_trazo === "manual_calibrado" ? "Trazado por el profesional" : "Eje propuesto y confirmado"}</dd></div>
          </dl> : <p className="mt-3 text-slate-600">Tocá un tramo para ver sus datos y su página de origen.</p>}
        </aside>
      </div>
    </>}
  </main>;
}
