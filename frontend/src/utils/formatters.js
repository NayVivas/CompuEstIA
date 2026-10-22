export function parseVolume(value) {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    value === "—"
  ) {
    return 0;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }

  const normalized = String(value)
    .replace(",", ".")
    .replace(/[^\d.-]/g, "");

  const parsed = parseFloat(normalized);

  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatVolume(value, decimals = 1) {
  const volume = parseVolume(value);

  return `${volume.toFixed(decimals)} m³`;
}

export function formatVolumeOrDash(value, decimals = 1) {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    value === "—"
  ) {
    return "—";
  }

  const volume = parseVolume(value);

  if (volume === 0) {
    return "—";
  }

  return `${volume.toFixed(decimals)} m³`;
}

export function sumVolumes(items = [], field = "volume") {
  return items.reduce((total, item) => {
    return total + parseVolume(item?.[field]);
  }, 0);
}

export function formatConfidence(value, decimals = 1) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  const confidence = Number(value);

  if (!Number.isFinite(confidence)) {
    return "—";
  }

  return `${confidence.toFixed(decimals)}%`;
}