import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container-x py-24 text-center">
      <div className="text-6xl">🔍</div>
      <h1 className="font-display font-bold text-3xl mt-4">Sahifa topilmadi</h1>
      <p className="text-ink-600 mt-2">So'ralgan sahifa yoki mahsulot mavjud emas.</p>
      <Link href="/" className="btn-flame mt-6">Bosh sahifaga</Link>
    </div>
  );
}
