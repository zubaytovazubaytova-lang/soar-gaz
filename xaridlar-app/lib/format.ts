export function formatSom(n: number): string {
  return n.toLocaleString("uz-UZ") + " so'm";
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("uz-UZ", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
