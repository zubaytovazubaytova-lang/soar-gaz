"use client";

import Link from "next/link";
import { useState } from "react";
import { useCart } from "@/context/CartContext";

const NAV = [
  { href: "/katalog", label: "Katalog" },
  { href: "/gaz-jihozlari", label: "Gaz jihozlari" },
  { href: "/gaz-jihozlari/konsultatsiya", label: "Kalkulyator" },
  { href: "/profil/buyurtmalar", label: "Buyurtmalarim" },
];

export function Header() {
  const { count } = useCart();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 bg-ink text-paper">
      <div className="container-x h-16 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 font-display font-bold text-lg">
          <span className="w-9 h-9 rounded-lg bg-flame flex items-center justify-center text-white">🔥</span>
          SOAR<span className="text-flame">GAZ</span>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="px-3 py-2 rounded-lg text-sm text-paper/80 hover:text-paper hover:bg-white/5 transition-colors"
            >
              {n.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link href="/savat" className="relative btn bg-flame text-white hover:bg-flame-600 px-4 py-2 text-sm">
            🛒 Savat
            {count > 0 && (
              <span className="absolute -top-2 -right-2 bg-white text-ink text-xs font-bold rounded-full min-w-5 h-5 px-1 flex items-center justify-center">
                {count}
              </span>
            )}
          </Link>
          <button
            className="md:hidden btn border border-white/20 px-3 py-2"
            onClick={() => setOpen((o) => !o)}
            aria-label="Menyu"
          >
            ☰
          </button>
        </div>
      </div>

      {open && (
        <nav className="md:hidden border-t border-white/10 px-4 py-2 flex flex-col">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              onClick={() => setOpen(false)}
              className="py-2.5 text-sm text-paper/80 hover:text-paper"
            >
              {n.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
