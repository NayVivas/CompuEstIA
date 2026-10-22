// Mismos límites que la API. No se exige una cantidad exacta de documentos.
export const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024;
export const MAX_TOTAL_SIZE_BYTES = 250 * 1024 * 1024;
export const MAX_FILES_PER_ANALYSIS = 50;
export const INITIAL_FILES = [];
export function isPdfFile(file) {
  return Boolean(file && /\.pdf$/i.test(file.name));
}
