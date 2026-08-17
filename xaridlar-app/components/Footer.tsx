import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-ink-950 text-paper/70 mt-16">
      <div className="container-x py-10 grid gap-8 sm:grid-cols-3">
        <div>
          <div className="font-display font-bold text-paper text-lg mb-2">
            SOAR<span className="text-flame">GAZ</span>
          </div>
          <p className="text-sm">
            Sertifikatlangan gaz jihozlari, kafolat va professional o'rnatish xizmati.
          </p>
        </div>
        <div className="text-sm">
          <div className="text-paper font-semibold mb-2">Bo'limlar</div>
          <ul className="space-y-1.5">
            <li><Link href="/katalog" className="hover:text-flame">Katalog</Link></li>
            <li><Link href="/gaz-jihozlari" className="hover:text-flame">Gaz jihozlari</Link></li>
            <li><Link href="/gaz-jihozlari/xizmatlar" className="hover:text-flame">Xizmatlar</Link></li>
            <li><Link href="/gaz-jihozlari/xavfsizlik" className="hover:text-flame">Xavfsizlik</Link></li>
            <li><Link href="/gaz-jihozlari/optom" className="hover:text-flame">Optom / B2B</Link></li>
          </ul>
        </div>
        <div className="text-sm">
          <div className="text-paper font-semibold mb-2">Aloqa</div>
          <p>+998 71 234 56 78</p>
          <p>info@soargaz.uz</p>
          <p className="mt-2">Buxoro shahri, Mustaqillik ko'chasi, 14-uy</p>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="container-x py-4 text-xs flex flex-wrap justify-between gap-2">
          <span>© {new Date().getFullYear()} SOAR GAZ. Barcha huquqlar himoyalangan.</span>
          <span className="font-mono">Litsenziya: № GZ-2024-0521</span>
        </div>
      </div>
    </footer>
  );
}
