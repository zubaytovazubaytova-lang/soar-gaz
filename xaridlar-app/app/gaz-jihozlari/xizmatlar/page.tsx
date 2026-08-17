import type { Metadata } from "next";

export const metadata: Metadata = { title: "Xizmatlar — Gaz jihozlari | SOAR GAZ" };

const SERVICES = [
  { icon: "🔧", t: "O'rnatish xizmati", d: "Sertifikatlangan gaz ustalari tomonidan xavfsiz o'rnatish. Ulash, sozlash va sinovdan o'tkazish kiritilgan.", price: "250 000 so'mdan" },
  { icon: "🛠️", t: "Texnik xizmat ko'rsatish", d: "Yillik profilaktika, forsunkalarni tozalash, germetiklik tekshiruvi va sozlash.", price: "150 000 so'mdan" },
  { icon: "📜", t: "Kafolat xizmati", d: "Zavod kafolati doirasida bepul ta'mirlash va ehtiyot qismlarni almashtirish.", price: "Bepul (kafolat muddatida)" },
  { icon: "♻️", t: "Trade-in (eski jihozni almashtirish)", d: "Eski gaz plitasi yoki kotelingizni topshiring — yangi jihoz narxidan chegirma oling.", price: "300 000 so'mgacha chegirma" },
];

export default function XizmatlarPage() {
  return (
    <div className="container-x py-10">
      <h1 className="font-display font-bold text-3xl">Xizmatlar</h1>
      <p className="text-ink-600 mt-1 max-w-2xl">
        Jihozni sotib olishdan tortib o'rnatish va keyingi texnik xizmatgacha — to'liq qamrov.
      </p>
      <div className="grid sm:grid-cols-2 gap-4 mt-8">
        {SERVICES.map((s) => (
          <div key={s.t} className="card p-6">
            <div className="text-3xl">{s.icon}</div>
            <h2 className="font-display font-semibold text-lg mt-3">{s.t}</h2>
            <p className="text-ink-600 mt-1">{s.d}</p>
            <div className="spec-tag mt-4 inline-flex"><span className="text-ink-600">Narx</span><span className="font-semibold">{s.price}</span></div>
          </div>
        ))}
      </div>
    </div>
  );
}
