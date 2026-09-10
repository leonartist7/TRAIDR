export function instrumentLabel(instrumentId: string): string {
  return instrumentId.split(":").at(-1) ?? instrumentId;
}

export function compactScore(value: number | null): string {
  return value === null ? "—" : Math.round(value).toString();
}

export function formatUtc(value: string | null): string {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Invalid timestamp";
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

export function formatAge(value: string | null): string {
  if (!value) return "Unknown age";
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).valueOf()) / 1000));
  if (!Number.isFinite(seconds)) return "Unknown age";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

export function humanizeReason(value: string): string {
  return value.toLowerCase().replaceAll("_", " ");
}
