import Link from "next/link";
import type { Metadata } from "next";
import { getCategories, getGasCategories, getProducts } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";

export const metadata: Metadata = {
  title: "Katalog — SOAR GAZ",
  description: "Barcha gaz jihozlari va armatura toifalari.",
};

export default function KatalogPage() {
  const gasCats = getGasCategories();
  const umumiy = getCategories("umumiy");
  const all = getProducts();

  return (
    <div className="container-x py-10">
      <h1 className="font-display font-bold text-3xl">Katalog</h1>
      <p className="text-ink-600 mt-1">Barcha bo'limlar va mahsulotlar</p>

      <h2 className="font-display font-semibold text-xl mt-8 mb-3">Gaz jihozlari</h2>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {gasCats.map((c) => (
          <Link key={c.slug} href={`/gaz-jihozlari/${c.slug}`} className="card p-5 hover:shadow-pop transition-shadow">
            <div className="text-3xl">{c.icon}</div>
            <div className="font-display font-semibold mt-2">{c.name}</div>
            <p className="text-sm text-ink-600 mt-1 line-clamp-2">{c.description}</p>
          </Link>
        ))}
      </div>

      <h2 className="font-display font-semibold text-xl mt-10 mb-3">Umumiy toifalar</h2>
      <div className="grid sm:grid-cols-3 gap-4">
        {umumiy.map((c) => (
          <Link key={c.slug} href={`/katalog/${c.slug}`} className="card p-5 flex items-center gap-3 hover:shadow-pop transition-shadow">
            <span className="text-3xl">{c.icon}</span>
            <div>
              <div className="font-display font-semibold">{c.name}</div>
              <p className="text-sm text-ink-600 line-clamp-1">{c.description}</p>
            </div>
          </Link>
        ))}
      </div>

      <h2 className="font-display font-semibold text-xl mt-10 mb-3">Barcha mahsulotlar</h2>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {all.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}
      </div>
    </div>
  );
}
