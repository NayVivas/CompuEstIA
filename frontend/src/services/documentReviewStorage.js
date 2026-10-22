const DB = 'computoestia-document-review';

function storageError(error) {
  if (error?.name === 'QuotaExceededError') {
    return new Error('No hay espacio suficiente en el navegador para guardar esta revisión. Liberá almacenamiento del sitio y volvé a intentar.');
  }
  if (error?.name === 'ConcurrentEditError') return error;
  if (error?.message && error.name !== 'AbortError') return error;
  return new Error('No se pudo completar el guardado local. Recargá la revisión y volvé a intentar.');
}

function concurrentEditError() {
  const error = new Error('La revisión cambió mientras se estaba guardando. Se conservaron los datos existentes; recargá la revisión antes de volver a editar.');
  error.name = 'ConcurrentEditError';
  return error;
}

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value).sort().map(key => [key, stableValue(value[key])])
    );
  }
  return value;
}

const stableStringify = value => JSON.stringify(stableValue(value));
function withoutPersistenceMetadata(record) {
  const businessRecord = { ...record };
  delete businessRecord.kind;
  delete businessRecord.scope;
  delete businessRecord.historial;
  return businessRecord;
}

function sameRecordSet(left, right, stripMetadata = false) {
  const normalize = records => records
    .map(record => stableStringify(stripMetadata ? withoutPersistenceMetadata(record) : record))
    .sort();
  return stableStringify(normalize(left)) === stableStringify(normalize(right));
}

async function transact(storeName, mode, action) {
  const db = await new Promise((resolve, reject) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => { r.result.createObjectStore('decisions'); r.result.createObjectStore('pdfs'); };
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.onblocked = () => reject(new Error('Cerrá otras pestañas para habilitar el guardado.'));
  });
  try { return await new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, mode); let result; let failure;
    const fail = error => {
      failure = storageError(error);
      try { tx.abort(); } catch { reject(failure); }
    };
    try {
      action(tx.objectStore(storeName), (value) => { result = value; }, tx, fail);
    } catch (error) {
      fail(error);
    }
    tx.oncomplete = () => resolve(result);
    tx.onabort = () => reject(failure || storageError(tx.error));
    tx.onerror = () => {};
  }); } finally { db.close(); }
}
export async function fileHash(file) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer())), b => b.toString(16).padStart(2, '0')).join('');
}
export const getPdf = (sha) => transact('pdfs', 'readonly', (s, done) => { s.get(sha).onsuccess = e => done(e.target.result); });
export async function storePdf(sha, file) {
  if (await fileHash(file) !== sha) throw new Error('Este archivo no corresponde al PDF analizado. Seleccioná el original exacto.');
  return transact('pdfs', 'readwrite', s => s.put(file, sha));
}
export const getDecisions = (scope) => transact('decisions', 'readonly', (s, done) => {
  s.getAll().onsuccess = e => done(e.target.result.filter(d => d.scope === String(scope) && !d.kind));
});
export function saveDecision(scope, decision, expectedVersion = 0) {
  const key = JSON.stringify([String(scope), decision.sha256, decision.pagina]);
  return transact('decisions', 'readwrite', (s, done, _tx, fail) => {
    s.get(key).onsuccess = e => {
      const previous = e.target.result;
      if ((previous?.version || 0) !== expectedVersion) { fail(concurrentEditError()); return; }
      const saved = { ...decision, scope: String(scope), version: expectedVersion + 1,
        historial: [...(previous?.historial || []), { ...decision, fecha: new Date().toISOString() }] };
      s.put(saved, key); done(saved);
    };
  });
}
export function applyDecisions(review, decisions) {
  const next = structuredClone(review);
  for (const doc of next.documentos || []) for (const page of doc.paginas || []) {
    const decision = decisions.find(d => d.sha256 === doc.sha256 && d.pagina === page.pagina);
    if (!decision) continue;
    page.clasificacion_automatica ||= structuredClone(page.clasificacion || {});
    page.decision_documental = decision;
    page.clasificacion = { ...page.clasificacion, metodo: 'revision_profesional', propuestas_modelo_sin_evidencia: {}, motivos_revision: [], tiene_sugerencias: false,
      objetivos: Object.fromEntries(Object.entries(decision.objetivos).map(([k, etiquetas]) => [k, { etiquetas }])) };
    page.estado = 'revisado_profesional'; page.requiere_revision = page.caracteres < 10;
  }
  const pages = (next.documentos || []).flatMap(d => d.paginas || []);
  next.resumen = { ...next.resumen, paginas_para_revision: pages.filter(p => p.requiere_revision).length };
  return next;
}

export const getTechnicalNotes = (scope) => transact('decisions', 'readonly', (s, done) => {
  s.getAll().onsuccess = e => done(e.target.result.filter(d => d.scope === String(scope) && d.kind === 'technical'));
});
export function saveTechnicalNote(scope, issueId, note, expectedVersion = 0) {
  const key = JSON.stringify(['technical', String(scope), issueId]);
  return transact('decisions', 'readwrite', (s, done, _tx, fail) => {
    s.get(key).onsuccess = e => {
      const old = e.target.result;
      if ((old?.version || 0) !== expectedVersion) { fail(concurrentEditError()); return; }
      const saved = { kind: 'technical', scope: String(scope), issueId, version: expectedVersion + 1,
        historial: [...(old?.historial || []), { ...note, fecha: new Date().toISOString() }] };
      s.put(saved, key); done(saved);
    };
  });
}
export const getRowCorrections = (scope) => transact('decisions', 'readonly', (s, done) => {
  s.getAll().onsuccess = e => done(e.target.result.filter(d => d.scope === String(scope) && d.kind === 'row_correction'));
});
export function storeRowCorrections(scope, corrections, hashes, previous) {
  return transact('decisions', 'readwrite', (s, done, _tx, fail) => {
    s.getAll().onsuccess = e => {
      const existing = e.target.result.filter(d => d.scope === String(scope) && d.kind === 'row_correction' && hashes.includes(d.sha256));
      const expected = previous.filter(d => hashes.includes(d.sha256));
      if (!sameRecordSet(existing, expected)) {
        if (sameRecordSet(existing, corrections, true)) { done(existing); return; }
        fail(concurrentEditError()); return;
      }
      const key = d => JSON.stringify(['row_correction', String(scope), d.sha256, d.pagina, d.fila]);
      for (const d of existing) s.delete(key(d));
      const saved = corrections.map(d => {
        const old = existing.find(x => key(x) === key(d));
        return { ...d, kind: 'row_correction', scope: String(scope), historial: [...(old?.historial || []), { ...d, fecha: new Date().toISOString() }] };
      });
      for (const d of saved) s.put(d,key(d));
      done(saved);
    };
  });
}

export const getTechnicalResolutions = (scope) => transact('decisions', 'readonly', (s, done) => {
  s.getAll().onsuccess = e => done(e.target.result.filter(d => d.scope === String(scope) && d.kind === 'technical_resolution'));
});
export function storeTechnicalResolutions(scope, resolutions, hashes, previous) {
  return transact('decisions', 'readwrite', (s, done, _tx, fail) => {
    s.getAll().onsuccess = e => {
      const existing = e.target.result.filter(d => d.scope === String(scope) && d.kind === 'technical_resolution' && hashes.includes(d.sha256));
      const expected = previous.filter(d => hashes.includes(d.sha256));
      if (!sameRecordSet(existing, expected)) {
        // Un doble envío puede terminar después de que la misma decisión ya se
        // guardó. En ese caso el resultado es idempotente y no debe presentarse
        // como un conflicto entre pestañas.
        if (sameRecordSet(existing, resolutions, true)) { done(existing); return; }
        fail(concurrentEditError()); return;
      }
      const key = d => d.accion === 'seleccionar_fuente_columna'
        ? JSON.stringify(['technical_resolution', String(scope), d.accion, d.campo, d.referencia])
        : d.accion === 'definir_seccion_columna'
          ? JSON.stringify(['technical_resolution', String(scope), d.accion, d.referencia])
        : JSON.stringify(['technical_resolution', String(scope), d.accion, d.sha256, d.pagina, d.referencia_original]);
      for (const d of existing) s.delete(key(d));
      const saved = resolutions.map(d => {
        const old = existing.find(x => key(x) === key(d));
        return { ...d, kind: 'technical_resolution', scope: String(scope),
          historial: [...(old?.historial || []), { ...d, fecha: new Date().toISOString() }] };
      });
      for (const d of saved) s.put(d, key(d));
      done(saved);
    };
  });
}

export const getGeometryDecision = (scope, sourceIdentity) => transact('decisions', 'readonly', (s, done) => {
  const key = JSON.stringify(['geometry_review', String(scope), sourceIdentity]);
  s.get(key).onsuccess = event => done(event.target.result || null);
});

export function saveGeometryDecision(scope, decision) {
  const key = JSON.stringify(['geometry_review', String(scope), decision.identidad_fuentes]);
  return transact('decisions', 'readwrite', (s, done) => {
    const saved = {
      ...decision,
      kind: 'geometry_review',
      scope: String(scope),
      fecha_guardado: new Date().toISOString(),
    };
    s.put(saved, key);
    done(saved);
  });
}
