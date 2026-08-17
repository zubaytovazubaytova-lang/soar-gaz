"use client";

import { useState } from "react";
import type { Product } from "@/lib/types";
import { useCart } from "@/context/CartContext";

export function AddToCartButton({
  product,
  qty = 1,
  full = false,
}: {
  product: Product;
  qty?: number;
  full?: boolean;
}) {
  const { add } = useCart();
  const [done, setDone] = useState(false);

  return (
    <button
      onClick={() => {
        add(product, qty);
        setDone(true);
        setTimeout(() => setDone(false), 1600);
      }}
      className={`btn-flame ${full ? "w-full" : ""} ${done ? "!bg-steel" : ""}`}
    >
      {done ? "✓ Qo'shildi" : "🛒 Savatga qo'shish"}
    </button>
  );
}
