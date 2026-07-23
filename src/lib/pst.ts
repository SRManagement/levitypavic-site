// Every tracking write and every stats read uses these so bucket keys
// always line up — writing in one timezone and reading in another would
// silently corrupt the numbers.

const PST_TZ = "America/Los_Angeles";

// "2026-07-22"
export function pstDateKey(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: PST_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

// "2026-07-22T14" (24h hour, PST)
export function pstHourKey(date: Date): string {
  const day = pstDateKey(date);
  const hour = new Intl.DateTimeFormat("en-US", {
    timeZone: PST_TZ,
    hour: "2-digit",
    hour12: false,
  }).format(date);
  // "24" shows up at midnight in some environments — normalize to "00"
  const normalizedHour = hour === "24" ? "00" : hour.padStart(2, "0");
  return `${day}T${normalizedHour}`;
}

// Short hour label for chart axes, e.g. "6 PM"
export function pstHourLabel(hourKey: string): string {
  const [datePart, hourPart] = hourKey.split("T");
  const d = new Date(`${datePart}T${hourPart}:00:00`);
  return new Intl.DateTimeFormat("en-US", {
    timeZone: PST_TZ,
    hour: "numeric",
    hour12: true,
  }).format(d);
}

// Short date label for chart axes, e.g. "Jul 22"
export function pstDateLabel(dateKey: string): string {
  const d = new Date(`${dateKey}T12:00:00`);
  return new Intl.DateTimeFormat("en-US", {
    timeZone: PST_TZ,
    month: "short",
    day: "numeric",
  }).format(d);
}
