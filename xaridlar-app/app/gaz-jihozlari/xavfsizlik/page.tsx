import type { Metadata } from "next";

export const metadata: Metadata = { title: "Xavfsizlik va nazorat — SOAR GAZ" };

const STANDARDS = [
  { code: "O'z DSt 3339", d: "Maishiy gaz jihozlariga qo'yiladigan umumiy xavfsizlik talablari" },
  { code: "GOST 10798", d: "Maishiy gaz plitalari uchun texnik shartlar" },
  { code: "GOST 20548", d: "Suvni isitish gaz kotellari — xavfsizlik va sinov" },
  { code: "O'z DSt 1204", d: "Suyultirilgan gaz ballonlari — ishlab chiqarish va sinov" },
];

const RULES = [
  "Gaz jihozlarini faqat sertifikatlangan usta o'rnatishi kerak.",
  "Xonada doimiy shamollatish (ventilyatsiya) ta'minlangan bo'lsin.",
  "Gaz hidi sezilsa — kranni yoping, olovdan saqlaning, deraza oching va 104 ga qo'ng'iroq qiling.",
  "Ballonni isitish manbalaridan kamida 1 metr uzoqlikda saqlang.",
  "Har yili jihozning germetikligini va tortishuvni tekshirtiring.",
  "Uxlashdan oldin va uydan chiqishdan avval gaz kranini yoping.",
  "Gaz signalizatori (datchigi) o'rnatish tavsiya etiladi.",
];

export default function XavfsizlikPage() {
  return (
    <div className="container-x py-10">
      <span className="chip bg-steel-100 text-steel-700">Xavfsizlik va nazorat</span>
      <h1 className="font-display font-bold text-3xl mt-3">Sertifikat standartlari va qoidalar</h1>

      <h2 className="font-display font-semibold text-xl mt-8 mb-3">Sertifikat standartlari</h2>
      <div className="grid sm:grid-cols-2 gap-3">
        {STANDARDS.map((s) => (
          <div key={s.code} className="spec-tag">
            <span className="font-semibold text-steel-700">{s.code}</span>
            <span className="text-ink-600 text-right">{s.d}</span>
          </div>
        ))}
      </div>

      <h2 className="font-display font-semibold text-xl mt-10 mb-3">Xavfsiz foydalanish qoidalari</h2>
      <ol className="space-y-2">
        {RULES.map((r, i) => (
          <li key={i} className="card p-4 flex items-start gap-3">
            <span className="w-7 h-7 rounded-full bg-flame text-white font-bold text-sm flex items-center justify-center shrink-0">{i + 1}</span>
            <span>{r}</span>
          </li>
        ))}
      </ol>

      <div className="card p-5 mt-8 border-l-4 border-red-500 bg-red-50">
        <b>Favqulodda holat:</b> gaz avariyasi xizmati — <span className="font-mono font-bold">104</span>
      </div>
    </div>
  );
}
