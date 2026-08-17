import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getGasCategories, getCategoryBySlug, getProductsByCategory } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";

export function generateStaticParams() {
  return getGasCategories().map((c) => ({ category: c.slug }));
}

export function generateMetadata({ params }: { params: { category: string } }): Metadata {
  const c = getCategoryBySlug(params.category);
  return { title: c ? `${c.name} — SOAR GAZ` : "Toifa topilmadi", description: c?.description };
}

export default function GasCategoryPage({ params }: { params: { category: string } }) {
  const cat = getCategoryBySlug(params.category);
  if (!cat || cat.parent !== "gaz-jihozlari") notFound();
  const products = getProductsByCategory(cat.slug);

  return (
    <div className="container-x py-10">
      <nav className="text-sm text-ink-600 mb-3">
        <Link href="/gaz-jihozlari" className="hover:text-flame">Gaz jihozlari</Link> / {cat.name}
      </nav>
      <div className="flex items-center gap-3">
        <span className="text-4xl">{cat.icon}</span>
        <div>
          <h1 className="font-display font-bold text-3xl">{cat.name}</h1>
          <p className="text-ink-600">{cat.description}</p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-8">
        {products.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}
      </div>
      {products.length === 0 && (
        <p className="text-ink-600 py-16 text-center">Bu toifada hozircha mahsulot yo'q.</p>
      )}
    </div>
  );
}
