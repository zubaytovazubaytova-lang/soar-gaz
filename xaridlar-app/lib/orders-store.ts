// ─────────────────────────────────────────────────────────────
//  Buyurtmalar qatlami (server-side)
//  Ma'lumot manbai — Django backend (`/api/xaridlar/`).
//  Buyurtma raqami, summa va holat backendda hisoblanadi/saqlanadi.
//  DIQQAT: faqat server tomonda (API route / server component) ishlatiladi.
// ─────────────────────────────────────────────────────────────
import { backendCall, BackendError } from "./backend";
import type { Order, OrderStatus } from "./types";

/** Backend `Order` shaklida javob qaytaradi — qo'shimcha o'girish shart emas. */
export async function createOrder(
  data: Omit<Order, "id" | "createdAt" | "status">
): Promise<Order> {
  return backendCall<Order>("/api/xaridlar/", {
    method: "POST",
    body: {
      customer: data.customer,
      delivery: data.delivery,
      payment: { method: data.payment.method },
      installService: data.installService,
      items: data.items,
      // `total` ataylab yuborilmaydi — summani backend o'zi hisoblaydi
    },
  });
}

export async function getOrder(id: string): Promise<Order | undefined> {
  try {
    return await backendCall<Order>(`/api/xaridlar/${encodeURIComponent(id)}/`);
  } catch (e) {
    if (e instanceof BackendError && e.status === 404) return undefined;
    throw e;
  }
}

/**
 * Telefon bo'yicha buyurtmalar.
 *
 * DIQQAT: backend bu so'rovga endi token talab qiladi — ilgari u ochiq edi va
 * raqamni bilgan har kim begona buyurtmalarni ko'ra olardi. Bu yerdan
 * server-to-server chaqiruv `BACKEND_ADMIN_TOKEN` bilan ketadi, ya'ni
 * "kimning raqami" ekanini TEKSHIRISH SHU QATLAMNING zimmasida:
 * chaqiruvchi telefonni foydalanuvchi sessiyasidan olishi kerak, so'rov
 * parametridan emas.
 */
export async function getOrdersByPhone(phone: string): Promise<Order[]> {
  const clean = phone.replace(/\D/g, "");
  if (!clean) return [];
  return backendCall<Order[]>(
    `/api/xaridlar/?telefon=${encodeURIComponent(clean)}`,
    { auth: true }
  );
}

/** Admin: to'liq ro'yxat. `BACKEND_ADMIN_TOKEN` sozlanmagan bo'lsa backend 403 qaytaradi. */
export async function listOrders(): Promise<Order[]> {
  return backendCall<Order[]>("/api/xaridlar/", { auth: true });
}

/** Admin: holatni o'zgartirish. */
export async function updateOrderStatus(
  id: string,
  status: OrderStatus
): Promise<Order | undefined> {
  try {
    return await backendCall<Order>(`/api/xaridlar/${encodeURIComponent(id)}/`, {
      method: "PATCH",
      body: { status },
      auth: true,
    });
  } catch (e) {
    if (e instanceof BackendError && e.status === 404) return undefined;
    throw e;
  }
}
