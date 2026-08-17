"use client";

import { useState } from "react";

export default function OptomPage() {
  const [sent, setSent] = useState(false);
  const [form, setForm] = useState({ company: "", name: "", phone: "", need: "", volume: "" });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // Demo: hozircha faqat mahalliy tasdiq. Productionda POST /api/b2b-leads.
    setSent(true);
  }

  if (sent) {
    return (
      <div className="container-x py-16 max-w-lg text-center">
        <div className="text-5xl">✅</div>
        <h1 className="font-display font-bold text-2xl mt-3">So'rovingiz qabul qilindi!</h1>
        <p className="text-ink-600 mt-2">
          Optom bo'limimiz 24 soat ichida siz bilan bog'lanib, maxsus narxlar va shartlarni taklif qiladi.
        </p>
      </div>
    );
  }

  return (
    <div className="container-x py-10 max-w-2xl">
      <span className="chip bg-steel-100 text-steel-700">Optom / B2B</span>
      <h1 className="font-display font-bold text-3xl mt-3">Ustaxona va do'konlar uchun</h1>
      <p className="text-ink-600 mt-1">
        Doimiy hamkorlar uchun optom narxlar, kechiktirilgan to'lov va yetkazib berish. So'rov qoldiring.
      </p>

      <form onSubmit={submit} className="card p-6 mt-6 grid sm:grid-cols-2 gap-4">
        <Field label="Kompaniya / do'kon" value={form.company} onChange={(v) => setForm({ ...form, company: v })} required />
        <Field label="Mas'ul shaxs" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required />
        <Field label="Telefon" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} required placeholder="+998 90 000 00 00" />
        <Field label="Taxminiy oylik hajm" value={form.volume} onChange={(v) => setForm({ ...form, volume: v })} placeholder="masalan: 20-50 dona" />
        <div className="sm:col-span-2">
          <label className="text-sm font-semibold block mb-1.5">Qanday jihozlar kerak?</label>
          <textarea
            className="w-full rounded-xl border border-ink-100 px-4 py-3 outline-none focus:border-steel"
            rows={3}
            value={form.need}
            onChange={(e) => setForm({ ...form, need: e.target.value })}
            placeholder="Gaz plitalari, kotellar, ballonlar..."
          />
        </div>
        <button type="submit" className="btn-flame sm:col-span-2">So'rov yuborish</button>
      </form>
    </div>
  );
}

function Field({
  label, value, onChange, required, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; required?: boolean; placeholder?: string;
}) {
  return (
    <div>
      <label className="text-sm font-semibold block mb-1.5">{label}{required && " *"}</label>
      <input
        className="w-full rounded-xl border border-ink-100 px-4 py-3 outline-none focus:border-steel"
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
