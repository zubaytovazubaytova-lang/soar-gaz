"use client";

import { useState } from "react";
import Link from "next/link";

type Insul = "yaxshi" | "ortacha" | "past";
const FACTOR: Record<Insul, number> = { yaxshi: 0.08, ortacha: 0.1, past: 0.13 };
const INSUL_LABEL: Record<Insul, string> = {
  yaxshi: "Yaxshi (yangi bino, issiq oyna)",
  ortacha: "O'rtacha",
  past: "Past (eski bino, sovuq)",
};

export default function KonsultatsiyaPage() {
  const [area, setArea] = useState(60);
  const [insul, setInsul] = useState<Insul>("ortacha");
  const [ceiling, setCeiling] = useState(2.7);

  // Tavsiya etilgan quvvat (kWt): maydon × koeffitsient × (shift balandligi / 2.7)
  const power = Math.max(6, Math.round(area * FACTOR[insul] * (ceiling / 2.7) * 10) / 10);
  const rec =
    power <= 12
      ? { cat: "gaz-qozonlari", name: "Bir konturli 12 kWt kotel yoki konvektor" }
      : power <= 24
      ? { cat: "gaz-qozonlari", name: "24 kWt ikki konturli kotel" }
      : { cat: "gaz-qozonlari", name: "≥ 30 kWt kotel (mutaxassis bilan hisoblang)" };

  return (
    <div className="container-x py-10 max-w-3xl">
      <span className="chip bg-flame-100 text-flame-700">Konsultatsiya</span>
      <h1 className="font-display font-bold text-3xl mt-3">Quvvat kalkulyatori</h1>
      <p className="text-ink-600 mt-1">
        Xona maydoni va izolatsiya darajasiga qarab tavsiya etilgan gaz koteli quvvatini hisoblang.
      </p>

      <div className="card p-6 mt-6 grid sm:grid-cols-2 gap-6">
        <div className="space-y-5">
          <div>
            <label className="text-sm font-semibold">Xona / uy maydoni: <span className="font-mono text-flame">{area} m²</span></label>
            <input type="range" min={10} max={400} value={area} onChange={(e) => setArea(+e.target.value)} className="w-full accent-flame mt-2" />
          </div>
          <div>
            <label className="text-sm font-semibold">Shift balandligi: <span className="font-mono text-flame">{ceiling} m</span></label>
            <input type="range" min={2.4} max={4} step={0.1} value={ceiling} onChange={(e) => setCeiling(+e.target.value)} className="w-full accent-flame mt-2" />
          </div>
          <div>
            <label className="text-sm font-semibold block mb-2">Izolatsiya darajasi</label>
            <div className="flex flex-col gap-2">
              {(Object.keys(FACTOR) as Insul[]).map((k) => (
                <label key={k} className={`spec-tag cursor-pointer ${insul === k ? "border-flame border-solid bg-flame-50" : ""}`}>
                  <span className="flex items-center gap-2">
                    <input type="radio" checked={insul === k} onChange={() => setInsul(k)} className="accent-flame" />
                    {INSUL_LABEL[k]}
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-2xl bg-ink text-paper p-6 flex flex-col items-center justify-center text-center">
          <div className="text-sm text-paper/60">Tavsiya etilgan quvvat</div>
          <div className="font-mono font-bold text-5xl text-flame my-2">{power}</div>
          <div className="text-sm text-paper/70">kWt</div>
          <div className="mt-4 text-sm">
            <b className="text-paper">{rec.name}</b>
          </div>
          <Link href={`/gaz-jihozlari/${rec.cat}`} className="btn-flame mt-4">
            Mos jihozlarni ko'rish →
          </Link>
        </div>
      </div>

      <p className="text-xs text-ink-600 mt-4">
        * Hisob taxminiy. Aniq loyihalash uchun mutaxassisimiz bilan bog'laning — issiqlik yo'qotishlari,
        deraza maydoni va mintaqa iqlimi hisobga olinadi.
      </p>
    </div>
  );
}
