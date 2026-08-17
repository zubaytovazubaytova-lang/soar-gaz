// ─────────────────────────────────────────────────────────────
//  Data-access qatlami (mahsulot / toifa)
//  Hozircha JSON fayllardan o'qiydi. PostgreSQL + Prisma'ga
//  ko'chirishda faqat shu fayl ichidagi funksiyalar o'zgaradi —
//  chaqiruvchi kod (sahifalar) o'zgarishsiz qoladi.
// ─────────────────────────────────────────────────────────────
import categoriesJson from "@/data/categories.json";
import productsJson from "@/data/products.json";
import type { Category, Product } from "./types";

const categories = categoriesJson as Category[];
const products = productsJson as Product[];

export function getCategories(group?: Category["group"]): Category[] {
  return group ? categories.filter((c) => c.group === group) : categories;
}

export function getGasCategories(): Category[] {
  return categories.filter((c) => c.parent === "gaz-jihozlari");
}

export function getCategoryBySlug(slug: string): Category | undefined {
  return categories.find((c) => c.slug === slug);
}

export function getProducts(): Product[] {
  return products;
}

export function getProductsByCategory(slug: string): Product[] {
  return products.filter((p) => p.category === slug);
}

export function getProductBySlug(slug: string): Product | undefined {
  return products.find((p) => p.slug === slug);
}

export function getProductById(id: string): Product | undefined {
  return products.find((p) => p.id === id);
}

export function getFeatured(limit = 4): Product[] {
  const feat = products.filter((p) => p.featured);
  return (feat.length ? feat : products).slice(0, limit);
}

export function getRelated(product: Product, limit = 4): Product[] {
  return products
    .filter((p) => p.category === product.category && p.id !== product.id)
    .slice(0, limit);
}

export function searchProducts(q: string): Product[] {
  const s = q.trim().toLowerCase();
  if (!s) return [];
  return products.filter(
    (p) =>
      p.name.toLowerCase().includes(s) ||
      p.short.toLowerCase().includes(s) ||
      p.category.toLowerCase().includes(s)
  );
}
