"use client";

import Link from "next/link";
import { useCart } from "@/context/CartContext";
import { formatSom } from "@/lib/format";

export default function SavatPage() {
  const { lines, total, setQty, remove, ready } = useCart();

  if (ready && lines.length === 0) {
    return (
      <div className="container-x py-20 text-center">
        <div className="text-5xl">🛒</div>
        <h1 className="font-display font-bold text-2xl mt-3">Savatingiz bo'sh</h1>
        <p className="text-ink-600 mt-1">Katalogdan gaz jihozlarini tanlab qo'shing.</p>
        <Link href="/katalog" className="btn-flame mt-5">Katalogga o'tish</Link>
      </div>
    );
  }

  return (
    <div className="container-x py-10">
      <h1 className="font-display font-bold text-3xl mb-6">Savat</h1>
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Mahsulotlar */}
        <div className="lg:col-span-2 space-y-3">
          {lines.map((l) => (
            <div key={l.productId} className="card p-4 flex items-center gap-4">
              <div className="w-16 h-16 rounded-xl bg-paper-dark flex items-center justify-center text-3xl shrink-0">
                {l.image}
              </div>
              <div className="flex-1 min-w-0">
                <Link href={`/mahsulot/${l.slug}`} className="font-semibold hover:text-flame line-clamp-1">{l.name}</Link>
                <div className="font-mono text-sm text-ink-600">{formatSom(l.price)}</div>
              </div>
              <div className="flex items-center rounded-xl border border-ink-100 overflow-hidden">
                <button className="w-8 h-8 font-bold hover:bg-paper-dark" onClick={() => setQty(l.productId, l.qty - 1)}>−</button>
                <span className="w-9 text-center font-mono font-bold">{l.qty}</span>
                <button className="w-8 h-8 font-bold hover:bg-paper-dark" onClick={() => setQty(l.productId, l.qty + 1)}>+</button>
              </div>
              <div className="font-mono font-bold w-28 text-right hidden sm:block">{formatSom(l.price * l.qty)}</div>
              <button className="text-ink-600 hover:text-red-600 w-8 h-8" onClick={() => remove(l.productId)} aria-label="O'chirish">🗑</button>
            </div>
          ))}
        </div>

        {/* Xulosa */}
        <div className="card p-5 h-fit sticky top-20">
          <h2 className="font-display font-semibold text-lg mb-3">Buyurtma xulosasi</h2>
          <div className="flex justify-between py-2 border-b border-ink-100 text-sm">
            <span className="text-ink-600">Mahsulotlar</span>
            <span className="font-mono">{lines.reduce((s, l) => s + l.qty, 0)} dona</span>
          </div>
          <div className="flex justify-between py-3 font-bold text-lg">
            <span>Jami</span>
            <span className="font-mono text-flame">{formatSom(total)}</span>
          </div>
          <Link href="/checkout" className="btn-flame w-full mt-2">Rasmiylashtirish →</Link>
          <Link href="/katalog" className="btn-ghost w-full mt-2">Xaridni davom ettirish</Link>
        </div>
      </div>
    </div>
  );
}
