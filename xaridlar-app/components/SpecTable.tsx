import type { Spec } from "@/lib/types";

// Signature element: "do'kon narx yorlig'i" uslubidagi spetsifikatsiya (dashed, mono)
export function SpecTable({ specs, dark = false }: { specs: Spec[]; dark?: boolean }) {
  return (
    <div className="grid sm:grid-cols-2 gap-2">
      {specs.map((s, i) => (
        <div key={i} className={`spec-tag ${dark ? "spec-tag--dark" : ""}`}>
          <span className={dark ? "text-paper/60" : "text-ink-600"}>{s.label}</span>
          <span className="font-semibold text-right">{s.value}</span>
        </div>
      ))}
    </div>
  );
}
