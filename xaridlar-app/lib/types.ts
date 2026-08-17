// ─────────────────────────────────────────────────────────────
//  Ma'lumotlar modeli (TypeScript)
//  Data-access qatlami (lib/data.ts) shu tiplarga tayanadi.
//  Keyinchalik PostgreSQL + Prisma'ga ko'chirishda shu tiplar
//  Prisma modellariga moslashtiriladi.
// ─────────────────────────────────────────────────────────────

export type CategoryGroup = "gaz-jihozlari" | "umumiy";

export interface Category {
  slug: string;
  name: string;
  group: CategoryGroup;
  parent?: string; // gaz-jihozlari toifalari uchun ("gaz-jihozlari")
  description: string;
  icon?: string; // emoji yoki ikonka nomi
}

export interface Spec {
  label: string;
  value: string;
}

export interface GasInfo {
  type: "tabiiy" | "suyultirilgan" | "tabiiy/suyultirilgan";
  power?: string; // kWt
  certificate?: string; // sertifikat raqami
  installNote?: string; // o'rnatish bo'yicha eslatma
}

export interface Product {
  id: string;
  slug: string;
  name: string;
  category: string; // Category.slug
  price: number;
  oldPrice?: number;
  image: string; // emoji-placeholder yoki rasm yo'li
  short: string;
  description: string;
  specs: Spec[];
  gas?: GasInfo; // faqat gaz jihozlari uchun
  stock: number;
  rating: number;
  reviews: number;
  featured?: boolean;
}

// ─── Buyurtma (Order) ───────────────────────────────────────
export type OrderStatus =
  | "qabul_qilindi"
  | "tasdiqlandi"
  | "tayyorlanmoqda"
  | "jonatildi"
  | "yetkazildi"
  | "bekor";

export const ORDER_FLOW: OrderStatus[] = [
  "qabul_qilindi",
  "tasdiqlandi",
  "tayyorlanmoqda",
  "jonatildi",
  "yetkazildi",
];

export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  qabul_qilindi: "Qabul qilindi",
  tasdiqlandi: "Tasdiqlandi",
  tayyorlanmoqda: "Tayyorlanmoqda",
  jonatildi: "Jo'natildi",
  yetkazildi: "Yetkazildi",
  bekor: "Bekor qilindi",
};

export type DeliveryMethod = "kuryer" | "filialdan";
export type PaymentMethod = "naqd" | "click" | "payme" | "karta";

export interface OrderItem {
  productId: string;
  slug: string;
  name: string;
  price: number;
  qty: number;
}

export interface Order {
  id: string; // noyob buyurtma raqami, masalan SG-2600-0007
  createdAt: string; // ISO
  status: OrderStatus;
  customer: { name: string; phone: string; address?: string };
  delivery: { method: DeliveryMethod; note?: string };
  payment: {
    method: PaymentMethod;
    /** Backend to'lovni tasdiqlaganmi (Click/Payme webhook) */
    paid?: boolean;
    /** Onlayn to'lov uchun checkout havolasi (click/payme) */
    url?: string;
  };
  installService: boolean;
  items: OrderItem[];
  total: number;
}

// ─── Savat (client-side) ────────────────────────────────────
export interface CartLine {
  productId: string;
  slug: string;
  name: string;
  price: number;
  image: string;
  qty: number;
}
