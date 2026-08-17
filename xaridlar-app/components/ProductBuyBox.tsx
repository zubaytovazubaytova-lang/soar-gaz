"use client";

import { useState } from "react";
import Link from "next/link";
import type { Product } from "@/lib/types";
import { useCart } from "@/context/CartContext";
import { formatSom } from "@/lib/format";

export function ProductBuyBox({ product }: { product: Product }) {
  const { add } = useCart();
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);

  return (
    <div className="card p-5">
      <div className="font-mono font-bold text-3xl">{formatSom(product.price)}</div>
      {product.oldPrice && (
        <div className="font-mono text-ink-600 line-through">{formatSom(product.oldPrice)}</div>
      )}
      <div className="text-sm mt-1 text-ink-600">
        {product.stock > 0 ? (
          <span className="text-steel-600 font-semibold">Sotuvda mavjud ({product.stock})</span>
        ) : (
          <span className="text-red-600">Vaqtincha tugagan</span>
        )}
      </div>

      <div className="flex items-center gap-3 mt-4">
        <span className="text-sm text-ink-600">Miqdor:</span>
        <div className="flex items-center rounded-xl border border-ink-100 overflow-hidden">
          <button className="w-9 h-9 font-bold hover:bg-paper-dark" onClick={() => setQty((q) => Math.max(1, q - 1))}>−</button>
          <input
            className="w-12 text-center font-mono font-bold outline-none"
            value={qty}
            onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
          />
          <button className="w-9 h-9 font-bold hover:bg-paper-dark" onClick={() => setQty((q) => q + 1)}>+</button>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        <button
          className={`btn-flame w-full ${added ? "!bg-steel" : ""}`}
          onClick={() => {
            add(product, qty);
            setAdded(true);
            setTimeout(() => setAdded(false), 1600);
          }}
        >
          {added ? "✓ Savatga qo'shildi" : "🛒 Savatga qo'shish"}
        </button>
        <Link href="/savat" className="btn-ghost w-full">Savatni ochish</Link>
      </div>
    </div>
  );
}
