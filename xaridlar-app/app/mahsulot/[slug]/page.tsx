import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getProductBySlug, getProducts, getRelated, getCategoryBySlug } from "@/lib/data";
import { SpecTable } from "@/components/SpecTable";
import { ProductBuyBox } from "@/components/ProductBuyBox";
import { ProductCard } from "@/components/ProductCard";

export function generateStaticParams() {
  return getProducts().map((p) => ({ slug: p.slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const p = getProductBySlug(params.slug);
  return {
    title: p ? `${p.name} — SOAR GAZ` : "Mahsulot topilmadi",
    description: p?.short,
  };
}

export default function ProductPage({ params }: { params: { slug: string } }) {
  const product = getProductBySlug(params.slug);
  if (!product) notFound();
  const cat = getCategoryBySlug(product.category);
  const related = getRelated(product, 4);
  const catHref = cat?.parent === "gaz-jihozlari" ? `/gaz-jihozlari/${cat.slug}` : `/katalog/${cat?.slug}`;

  return (
    <div className="container-x py-10">
      <nav className="text-sm text-ink-600 mb-4">
        <Link href="/katalog" className="hover:text-flame">Katalog</Link>
        {cat && <> / <Link href={catHref} className="hover:text-flame">{cat.name}</Link></>}
        {" "}/ <span className="text-ink">{product.name}</span>
      </nav>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Rasm */}
        <div className="card h-80 flex items-center justify-center text-[8rem] bg-paper-dark">
          {product.image}
        </div>

        {/* Xarid bloki */}
        <div>
          <h1 className="font-display font-bold text-3xl">{product.name}</h1>
          <div className="flex items-center gap-2 mt-2 text-sm">
            <span className="chip bg-flame-100 text-flame-700">★ {product.rating}</span>
            <span className="text-ink-600">{product.reviews} sharh</span>
          </div>
          <p className="text-ink-600 mt-3">{product.short}</p>
          <div className="mt-5">
            <ProductBuyBox product={product} />
          </div>
        </div>
      </div>

      {/* Tavsif */}
      <section className="mt-10 grid lg:grid-cols-2 gap-8">
        <div>
          <h2 className="font-display font-semibold text-xl mb-3">Tavsif</h2>
          <p className="text-ink-700 leading-relaxed">{product.description}</p>
        </div>
        <div>
          <h2 className="font-display font-semibold text-xl mb-3">Texnik xususiyatlar</h2>
          <SpecTable specs={product.specs} />
        </div>
      </section>

      {/* Gaz sertifikati bloki */}
      {product.gas && (
        <section className="mt-8">
          <div className="card p-5 border-l-4 border-steel">
            <h2 className="font-display font-semibold text-xl mb-3 flex items-center gap-2">
              🛡️ Gaz jihozi ma'lumoti
            </h2>
            <div className="grid sm:grid-cols-3 gap-2">
              <div className="spec-tag"><span className="text-ink-600">Gaz turi</span><span className="font-semibold">{product.gas.type}</span></div>
              {product.gas.power && (
                <div className="spec-tag"><span className="text-ink-600">Quvvat</span><span className="font-semibold">{product.gas.power}</span></div>
              )}
              {product.gas.certificate && (
                <div className="spec-tag"><span className="text-ink-600">Sertifikat</span><span className="font-semibold">{product.gas.certificate}</span></div>
              )}
            </div>
            {product.gas.installNote && (
              <p className="text-sm text-ink-600 mt-3">
                <b>O'rnatish eslatmasi:</b> {product.gas.installNote}
              </p>
            )}
          </div>
        </section>
      )}

      {/* O'xshash mahsulotlar */}
      {related.length > 0 && (
        <section className="mt-12">
          <h2 className="font-display font-semibold text-xl mb-4">O'xshash mahsulotlar</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {related.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
