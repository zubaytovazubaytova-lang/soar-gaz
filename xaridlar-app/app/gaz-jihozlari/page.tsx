import Link from "next/link";
import type { Metadata } from "next";
import { getGasCategories, getProductsByCategory } from "@/lib/data";

export const metadata: Metadata = {
  title: "Gaz jihozlari — SOAR GAZ",
  description: "Gaz plitalari, qozonlar, konvektorlar, ballonlar va armatura. O'rnatish va kafolat.",
};

const SUB = [
  { href: "/gaz-jihozlari/xizmatlar", icon: "🧰", t: "Xizmatlar", d: "O'rnatish, texnik xizmat, trade-in" },
  { href: "/gaz-jihozlari/xavfsizlik", icon: "🛡️", t: "Xavfsizlik va nazorat", d: "Standartlar va foydalanish qoidalari" },
  { href: "/gaz-jihozlari/konsultatsiya", icon: "🧮", t: "Konsultatsiya", d: "Quvvat kalkulyatori bilan tavsiya" },
  { href: "/gaz-jihozlari/optom", icon: "🏭", t: "Optom / B2B", d: "Do'kon va ustaxonalar uchun" },
];

export default function GazJihozlariPage() {
  const cats = getGasCategories();

  return (
    <div className="container-x py-10">
      <span className="chip bg-steel-100 text-steel-700">Gaz jihozlari bo'limi</span>
      <h1 className="font-display font-bold text-3xl mt-3">Gaz jihozlari</h1>
      <p className="text-ink-600 mt-1 max-w-2xl">
        Tabiiy va suyultirilgan gaz uchun sertifikatlangan jihozlar. Har bir mahsulot
        gaz turi, quvvati va sertifikat raqami bilan ko'rsatilgan.
      </p>

      {/* Toifalar */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-8">
        {cats.map((c) => (
          <Link key={c.slug} href={`/gaz-jihozlari/${c.slug}`} className="card p-5 hover:shadow-pop transition-shadow">
            <div className="text-4xl">{c.icon}</div>
            <div className="font-display font-semibold mt-3">{c.name}</div>
            <p className="text-sm text-ink-600 mt-1 line-clamp-2">{c.description}</p>
            <div className="text-xs text-steel-600 mt-2 font-semibold">
              {getProductsByCategory(c.slug).length} ta mahsulot →
            </div>
          </Link>
        ))}
      </div>

      {/* Bo'limlar */}
      <h2 className="font-display font-semibold text-xl mt-10 mb-3">Bo'limlar</h2>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {SUB.map((s) => (
          <Link key={s.href} href={s.href} className="card p-5 hover:shadow-pop transition-shadow">
            <div className="text-3xl">{s.icon}</div>
            <div className="font-display font-semibold mt-2">{s.t}</div>
            <p className="text-sm text-ink-600 mt-1">{s.d}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
