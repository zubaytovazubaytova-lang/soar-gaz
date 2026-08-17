"use client";

import { useState } from "react";
import Link from "next/link";
import { formatSom, formatDate } from "@/lib/format";
import { ORDER_STATUS_LABEL, type Order } from "@/lib/types";

export default function BuyurtmalarPage() {
  const [phone, setPhone] = useState("");
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      // Filtrlash backendda bajariladi — brauzerga faqat mos buyurtmalar keladi.
      const res = await fetch(`/api/orders?phone=${encodeURIComponent(phone)}`, { cache: "no-store" });
      setOrders(res.ok ? await res.json() : []);
    } catch {
      setOrders([]);
    }
    setBusy(false);
  }

  return (
    <div className="container-x py-10 max-w-2xl">
      <h1 className="font-display font-bold text-3xl">Buyurtmalarim</h1>
      <p className="text-ink-600 mt-1">Telefon raqamingiz orqali buyurtmalaringizni toping.</p>

      <form onSubmit={search} className="flex gap-2 mt-5">
        <input
          className="flex-1 rounded-xl border border-ink-100 px-4 py-3 outline-none focus:border-flame"
          placeholder="+998 90 000 00 00"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <button className="btn-flame" disabled={busy}>{busy ? "..." : "Qidirish"}</button>
      </form>

      {orders !== null && (
        <div className="mt-6 space-y-3">
          {orders.length === 0 && <p className="text-ink-600 text-center py-10">Buyurtma topilmadi.</p>}
          {orders.map((o) => (
            <Link key={o.id} href={`/buyurtma/${o.id}`} className="card p-4 flex items-center justify-between hover:shadow-pop transition-shadow">
              <div>
                <div className="font-mono font-bold">{o.id}</div>
                <div className="text-sm text-ink-600">{formatDate(o.createdAt)} · {o.items.length} mahsulot</div>
              </div>
              <div className="text-right">
                <div className="font-mono font-bold">{formatSom(o.total)}</div>
                <span className="chip bg-flame-100 text-flame-700 mt-1">{ORDER_STATUS_LABEL[o.status]}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
