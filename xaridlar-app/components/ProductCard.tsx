import Link from "next/link";
import type { Product } from "@/lib/types";
import { formatSom } from "@/lib/format";
import { AddToCartButton } from "./AddToCartButton";

export function ProductCard({ product }: { product: Product }) {
  return (
    <div className="card overflow-hidden flex flex-col">
      <Link
        href={`/mahsulot/${product.slug}`}
        className="relative flex items-center justify-center h-40 bg-paper-dark text-6xl"
      >
        <span>{product.image}</span>
        {product.gas && (
          <span className="absolute top-2 left-2 chip bg-steel-100 text-steel-700">
            Gaz sertifikati
          </span>
        )}
        {product.oldPrice && (
          <span className="absolute top-2 right-2 chip bg-flame-100 text-flame-700">
            Chegirma
          </span>
        )}
      </Link>
      <div className="p-4 flex flex-col flex-1">
        <Link href={`/mahsulot/${product.slug}`}>
          <h3 className="font-display font-semibold leading-snug hover:text-flame">{product.name}</h3>
        </Link>
        <p className="text-sm text-ink-600 mt-1 flex-1 line-clamp-2">{product.short}</p>
        <div className="flex items-end justify-between mt-3 mb-3">
          <div>
            <div className="font-mono font-bold text-lg">{formatSom(product.price)}</div>
            {product.oldPrice && (
              <div className="font-mono text-xs text-ink-600 line-through">
                {formatSom(product.oldPrice)}
              </div>
            )}
          </div>
          <div className="text-xs text-ink-600">
            {product.stock > 0 ? `Sotuvda: ${product.stock}` : "Tugagan"}
          </div>
        </div>
        <AddToCartButton product={product} full />
      </div>
    </div>
  );
}
