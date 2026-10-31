// Proyectos y resultados se guardan juntos, en una transacción IndexedDB.
// localStorage solo se lee para migrar el historial de versiones anteriores.
const DB_NAME = "computoestia-workspace";
const STORE = "snapshots";
const KEY = "current";
let queue = Promise.resolve();

function serial(task) {
  const operation = queue.then(task);
  queue = operation.catch(() => {});
  return operation;
}

function openDatabase() {
  return new Promise((resolve, reject) => {
    let finished = false;
    const finish = (error, db) => {
      if (finished) { db?.close(); return; }
      finished = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(db);
    };
    const timer = setTimeout(() => finish(new Error("El almacenamiento local no respondió.")), 5000);
    try {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE);
      };
      request.onerror = () => finish(request.error);
      request.onblocked = () => finish(new Error("Cerrá otras pestañas de CómputoEstIA y reintentá el guardado."));
      request.onsuccess = () => finish(null, request.result);
    } catch (error) { finish(error); }
  });
}

async function transaction(mode, data) {
  const db = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const store = tx.objectStore(STORE);
      const request = mode === "readonly" ? store.get(KEY) : store.put(data, KEY);
      // Esperar el commit, no solo el éxito de put: la cuota puede fallar después.
      tx.oncomplete = () => resolve(request.result);
      tx.onabort = () => reject(tx.error || request.error || new Error("No se pudo guardar el historial."));
      tx.onerror = () => {}; // onabort entrega el fallo de la transacción.
    });
  } finally { db.close(); }
}

function validate(data) {
  if (!data || !Array.isArray(data.projects) || !Array.isArray(data.analyses)) {
    throw new Error("El historial guardado tiene un formato no válido. No se reemplazó.");
  }
  return data;
}

const demoSeeds = new Map([
  [1, ["Edificio Norte", "Constructora Norte", "En análisis", 8, 3, 124.6, "Hoy"]],
  [2, ["Viviendas Sur", "Grupo Viviendas Sur", "Completado", 12, 5, 86.2, "Ayer"]],
  [3, ["Nave Industrial", "Industrial Sur", "Pendiente", 5, 0, 0, "08 sep 2026"]],
  [4, ["Centro Comercial", "Desarrollos Córdoba", "Completado", 16, 7, 241.8, "05 sep 2026"]],
]);

// Versiones anteriores guardaban el ejemplo como si fuera un proyecto real.
// Solo retirar registros idénticos al ejemplo, sin PDF ni análisis real.
export function withoutDemoSeeds(data) {
  const removed = new Set(data.projects.filter((project) => {
    const seed = demoSeeds.get(project.id);
    return seed && [project.name, project.client, project.status, project.documents,
      project.analyses, project.volumeValue, project.updated]
      .every((value, index) => value === seed[index])
      && !(project.documentsData || []).length
      && !project.clasificacionDocumental
      && !data.analyses.some((analysis) => analysis.projectId === project.id && analysis.resultado);
  }).map((project) => project.id));
  if (!removed.size) return data;
  return {
    ...data,
    projects: data.projects.filter((project) => !removed.has(project.id)),
    analyses: data.analyses.filter((analysis) => !removed.has(analysis.projectId) || analysis.resultado),
  };
}

function readLegacy(defaults) {
  const read = (key, fallback) => {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) throw new Error("El historial anterior no tiene un formato válido.");
    return parsed;
  };
  return { projects: read("computoestia-projects", defaults.projects), analyses: read("computoestia-analyses", defaults.analyses) };
}

export function loadWorkspace(defaults) {
  return serial(async () => {
    let data = defaults;
    try {
      const stored = await transaction("readonly");
      if (stored !== undefined) return { data: withoutDemoSeeds(validate(stored)), error: null };
      data = withoutDemoSeeds(readLegacy(defaults));
      await transaction("readwrite", validate(data));
      // No se borra nada si la migración no llegó a confirmarse.
      try {
        localStorage.removeItem("computoestia-projects");
        localStorage.removeItem("computoestia-analyses");
      } catch { /* IndexedDB ya contiene la copia completa. */ }
      return { data, error: null };
    } catch (error) {
      // Si IndexedDB está bloqueado, mantener los datos antiguos en memoria.
      try { data = withoutDemoSeeds(readLegacy(defaults)); } catch { /* Mantener originales intactos. */ }
      return { data, error };
    }
  });
}

export function saveWorkspace(data) {
  return serial(() => transaction("readwrite", validate(data)));
}

export function downloadWorkspace(data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify({ version: 1, ...data }, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = "ComputoEstIA_respaldo.json";
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function readSession() {
  try {
    const valor = localStorage.getItem("computoestia-auth");
    const authenticated = valor === "true";

    console.log("[CómputoEstIA][storage] readSession()", {
      origen: "frontend/src/services/workspaceStorage.js > readSession",
      clave: "computoestia-auth",
      valor,
      authenticated,
    });

    return authenticated;
  } catch (error) {
    console.error("[CómputoEstIA][storage] readSession() falló", error);
    return false;
  }
}

export function writeSession(authenticated) {
  try {
    if (authenticated) localStorage.setItem("computoestia-auth", "true");
    else localStorage.removeItem("computoestia-auth");

    console.log("[CómputoEstIA][storage] writeSession()", {
      origen: "frontend/src/services/workspaceStorage.js > writeSession",
      solicitado: authenticated,
      persistido: localStorage.getItem("computoestia-auth"),
    });
  } catch (error) {
    console.error("[CómputoEstIA][storage] writeSession() falló", error);
  }
}
