import Link from "next/link";
import { getGasCategories, getFeatured, getCategories } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";

const STEPS = [
  { n: 1, t: "Tanlang", d: "Katalogdan mos jihozni tanlang" },
  { n: 2, t: "Savatga", d: "Savatga qo'shib, buyurtma bering" },
  { n: 3, t: "Yetkazamiz", d: "Kuryer yoki filialdan olib keting" },
  { n: 4, t: "O'rnatamiz", d: "Sertifikatlangan usta o'rnatadi" },
];

const TRUST = [
  { icon: "📜", t: "Sertifikatlangan", d: "Barcha gaz jihozlari standartga mos" },
  { icon: "🛡️", t: "Rasmiy kafolat", d: "2 yilgacha zavod kafolati" },
  { icon: "🚚", t: "Tez yetkazish", d: "Buxoro bo'ylab 24 soatda" },
  { icon: "🧰", t: "O'rnatish xizmati", d: "Malakali gaz ustalari" },
];

export default function HomePage() {
  const gasCats = getGasCategories();
  const featured = getFeatured(4);
  const otherCats = getCategories("umumiy");

  return (
    <>
      {/* HERO */}
      <section className="bg-ink text-paper">
        <div className="container-x py-16 lg:py-24 grid lg:grid-cols-2 gap-10 items-center">
          <div>
            <span className="chip bg-white/10 text-paper mb-4">🔥 Gaz jihozlari savdosi</span>
            <h1 className="font-display font-bold text-4xl lg:text-5xl leading-tight">
              Ishonchli gaz jihozlari <span className="text-flame">bir joyda</span>
            </h1>
            <p className="mt-4 text-paper/70 max-w-md">
              Gaz plitalari, qozonlar, konvektorlar va armatura — sertifikatlangan,
              kafolatli va professional o'rnatish bilan.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/gaz-jihozlari" className="btn-flame">Gaz jihozlarini ko'rish</Link>
              <Link href="/gaz-jihozlari/konsultatsiya" className="btn-ghost !bg-transparent !text-paper !border-white/30">
                Quvvat kalkulyatori
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {gasCats.map((c) => (
              <Link
                key={c.slug}
                href={`/gaz-jihozlari/${c.slug}`}
                className="rounded-2xl bg-white/5 border border-white/10 p-5 hover:border-flame transition-colors"
              >
                <div className="text-3xl">{c.icon}</div>
                <div className="font-display font-semibold mt-2">{c.name}</div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* TRUST */}
      <section className="container-x -mt-8">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {TRUST.map((t) => (
            <div key={t.t} className="card p-4 flex items-start gap-3">
              <span className="text-2xl">{t.icon}</span>
              <div>
                <div className="font-semibold">{t.t}</div>
                <div className="text-sm text-ink-600">{t.d}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* GAZ TOIFALARI */}
      <section className="container-x py-14">
        <SectionHead title="Gaz jihozlari toifalari" href="/gaz-jihozlari" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
          {gasCats.map((c) => (
            <Link key={c.slug} href={`/gaz-jihozlari/${c.slug}`} className="card p-5 hover:shadow-pop transition-shadow">
              <div className="text-4xl">{c.icon}</div>
              <div className="font-display font-semibold mt-3">{c.name}</div>
              <p className="text-sm text-ink-600 mt-1 line-clamp-2">{c.description}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* MASHHUR MAHSULOTLAR */}
      <section className="container-x py-4">
        <SectionHead title="Mashhur mahsulotlar" href="/katalog" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
          {featured.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </section>

      {/* XARID JARAYONI */}
      <section className="container-x py-14">
        <h2 className="font-display font-bold text-2xl text-center">Xarid jarayoni</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-8">
          {STEPS.map((s) => (
            <div key={s.n} className="card p-5 text-center">
              <div className="w-10 h-10 rounded-full bg-flame text-white font-bold flex items-center justify-center mx-auto">
                {s.n}
              </div>
              <div className="font-display font-semibold mt-3">{s.t}</div>
              <p className="text-sm text-ink-600 mt-1">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* BOSHQA TOIFALAR */}
      <section className="container-x pb-16">
        <SectionHead title="Boshqa toifalar" href="/katalog" />
        <div className="grid sm:grid-cols-3 gap-4 mt-6">
          {otherCats.map((c) => (
            <Link key={c.slug} href={`/katalog/${c.slug}`} className="card p-5 flex items-center gap-3 hover:shadow-pop transition-shadow">
              <span className="text-3xl">{c.icon}</span>
              <div>
                <div className="font-display font-semibold">{c.name}</div>
                <p className="text-sm text-ink-600 line-clamp-1">{c.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

function SectionHead({ title, href }: { title: string; href: string }) {
  return (
    <div className="flex items-end justify-between">
      <h2 className="font-display font-bold text-2xl">{title}</h2>
      <Link href={href} className="text-sm text-flame font-semibold hover:underline">
        Barchasi →
      </Link>
    </div>
  );
}
