import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getCategories, getCategoryBySlug, getProductsByCategory } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";

export function generateStaticParams() {
  return getCategories("umumiy").map((c) => ({ category: c.slug }));
}

export function generateMetadata({ params }: { params: { category: string } }): Metadata {
  const c = getCategoryBySlug(params.category);
  return { title: c ? `${c.name} — SOAR GAZ` : "Toifa topilmadi" };
}

export default function CategoryPage({ params }: { params: { category: string } }) {
  const cat = getCategoryBySlug(params.category);
  if (!cat) notFound();
  const products = getProductsByCategory(cat.slug);

  return (
    <div className="container-x py-10">
      <nav className="text-sm text-ink-600 mb-3">
        <Link href="/katalog" className="hover:text-flame">Katalog</Link> / {cat.name}
      </nav>
      <h1 className="font-display font-bold text-3xl">{cat.name}</h1>
      <p className="text-ink-600 mt-1 max-w-2xl">{cat.description}</p>

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
