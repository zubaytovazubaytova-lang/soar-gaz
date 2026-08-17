"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCart } from "@/context/CartContext";
import { formatSom } from "@/lib/format";
import type { DeliveryMethod, PaymentMethod } from "@/lib/types";

const INSTALL_PRICE = 250000;

export default function CheckoutPage() {
  const { lines, total, clear, ready } = useCart();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [delivery, setDelivery] = useState<DeliveryMethod>("kuryer");
  const [address, setAddress] = useState("");
  const [note, setNote] = useState("");
  const [install, setInstall] = useState(false);
  const [payment, setPayment] = useState<PaymentMethod>("naqd");

  const grand = total + (install ? INSTALL_PRICE : 0);

  if (ready && lines.length === 0) {
    return (
      <div className="container-x py-20 text-center">
        <h1 className="font-display font-bold text-2xl">Savat bo'sh</h1>
        <Link href="/katalog" className="btn-flame mt-4">Katalogga o'tish</Link>
      </div>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!name || !phone) { setErr("Ism va telefon majburiy"); return; }
    if (delivery === "kuryer" && !address) { setErr("Yetkazish uchun manzil kiriting"); return; }
    setBusy(true);
    try {
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer: { name, phone, address: delivery === "kuryer" ? address : undefined },
          delivery: { method: delivery, note },
          payment: { method: payment },
          installService: install,
          items: lines.map((l) => ({ productId: l.productId, slug: l.slug, name: l.name, price: l.price, qty: l.qty })),
          total: grand,
        }),
      });
      const order = await res.json();
      if (!res.ok) throw new Error(order?.error || "server");
      clear();
      // Click/Payme tanlansa — to'g'ridan-to'g'ri to'lov sahifasiga o'tamiz
      if (order.payment?.url) {
        window.location.href = order.payment.url;
        return;
      }
      router.push(`/buyurtma/${order.id}`);
    } catch (e) {
      setErr(e instanceof Error && e.message !== "server"
        ? e.message
        : "Buyurtmani saqlashda xatolik. Qayta urinib ko'ring.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="container-x py-10 grid lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-6">
        <h1 className="font-display font-bold text-3xl">Rasmiylashtirish</h1>

        <Section title="Aloqa ma'lumotlari">
          <div className="grid sm:grid-cols-2 gap-4">
            <Input label="Ism-familiya *" value={name} onChange={setName} />
            <Input label="Telefon *" value={phone} onChange={setPhone} placeholder="+998 90 000 00 00" />
          </div>
        </Section>

        <Section title="Yetkazib berish">
          <div className="grid sm:grid-cols-2 gap-3">
            <Radio checked={delivery === "kuryer"} onChange={() => setDelivery("kuryer")} title="Kuryer" desc="Manzilga yetkazib beramiz" />
            <Radio checked={delivery === "filialdan"} onChange={() => setDelivery("filialdan")} title="Filialdan olish" desc="O'zingiz olib ketasiz" />
          </div>
          {delivery === "kuryer" && (
            <div className="mt-3">
              <Input label="Manzil" value={address} onChange={setAddress} placeholder="Shahar, ko'cha, uy" />
            </div>
          )}
          <div className="mt-3">
            <Input label="Izoh (ixtiyoriy)" value={note} onChange={setNote} placeholder="Mo'ljal, qo'shimcha ma'lumot" />
          </div>
        </Section>

        <Section title="Qo'shimcha xizmat">
          <label className="spec-tag cursor-pointer inline-flex">
            <span className="flex items-center gap-2">
              <input type="checkbox" checked={install} onChange={(e) => setInstall(e.target.checked)} className="accent-flame" />
              O'rnatish xizmati (+{formatSom(INSTALL_PRICE)})
            </span>
          </label>
        </Section>

        <Section title="To'lov usuli">
          <div className="grid sm:grid-cols-2 gap-3">
            <Radio checked={payment === "naqd"} onChange={() => setPayment("naqd")} title="Naqd" desc="Yetkazib berishda" />
            <Radio checked={payment === "click"} onChange={() => setPayment("click")} title="Click" desc="Onlayn to'lov" />
            <Radio checked={payment === "payme"} onChange={() => setPayment("payme")} title="Payme" desc="Onlayn to'lov" />
            <Radio checked={payment === "karta"} onChange={() => setPayment("karta")} title="Bank kartasi" desc="Uzcard / Humo / Visa" />
          </div>
        </Section>
      </div>

      {/* Xulosa */}
      <div className="card p-5 h-fit sticky top-20">
        <h2 className="font-display font-semibold text-lg mb-3">Buyurtma xulosasi</h2>
        <div className="space-y-1.5 text-sm max-h-52 overflow-y-auto">
          {lines.map((l) => (
            <div key={l.productId} className="flex justify-between gap-2">
              <span className="text-ink-600 line-clamp-1">{l.name} × {l.qty}</span>
              <span className="font-mono shrink-0">{formatSom(l.price * l.qty)}</span>
            </div>
          ))}
        </div>
        <div className="border-t border-ink-100 mt-3 pt-3 space-y-1.5 text-sm">
          <Row label="Mahsulotlar" value={formatSom(total)} />
          {install && <Row label="O'rnatish" value={formatSom(INSTALL_PRICE)} />}
        </div>
        <div className="flex justify-between font-bold text-lg mt-2">
          <span>Jami</span>
          <span className="font-mono text-flame">{formatSom(grand)}</span>
        </div>
        {err && <p className="text-red-600 text-sm mt-3">{err}</p>}
        <button type="submit" disabled={busy} className="btn-flame w-full mt-4">
          {busy ? "Yuborilmoqda..." : "Buyurtmani tasdiqlash"}
        </button>
      </div>
    </form>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <h2 className="font-display font-semibold text-lg mb-3">{title}</h2>
      {children}
    </div>
  );
}
function Input({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="text-sm font-semibold block mb-1.5">{label}</label>
      <input className="w-full rounded-xl border border-ink-100 px-4 py-3 outline-none focus:border-flame" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
function Radio({ checked, onChange, title, desc }: { checked: boolean; onChange: () => void; title: string; desc: string }) {
  return (
    <label className={`card p-3 cursor-pointer flex items-start gap-2 ${checked ? "ring-2 ring-flame" : ""}`}>
      <input type="radio" checked={checked} onChange={onChange} className="accent-flame mt-1" />
      <span>
        <span className="font-semibold block">{title}</span>
        <span className="text-xs text-ink-600">{desc}</span>
      </span>
    </label>
  );
}
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-ink-600">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}
