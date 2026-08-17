import { NextResponse } from "next/server";
import { createOrder, listOrders, getOrdersByPhone } from "@/lib/orders-store";
import { BackendError } from "@/lib/backend";
import type { Order } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Django backend xatosini mijozga tushunarli javobga aylantiradi
function backendXatosi(e: unknown) {
  if (e instanceof BackendError) {
    return NextResponse.json({ error: e.message }, { status: e.status });
  }
  return NextResponse.json({ error: "Kutilmagan xatolik" }, { status: 500 });
}

// GET /api/orders?phone=... — telefon bo'yicha buyurtmalar (/profil ishlatadi)
// GET /api/orders            — to'liq ro'yxat (faqat admin token bilan)
export async function GET(req: Request) {
  const phone = new URL(req.url).searchParams.get("phone");
  try {
    return NextResponse.json(phone ? await getOrdersByPhone(phone) : await listOrders());
  } catch (e) {
    return backendXatosi(e);
  }
}

// POST /api/orders — yangi buyurtma yaratish (backend `/api/xaridlar/` ga uzatiladi)
export async function POST(req: Request) {
  let body: Partial<Order>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Noto'g'ri JSON" }, { status: 400 });
  }

  const { customer, delivery, payment, items } = body;
  if (!customer?.name || !customer?.phone) {
    return NextResponse.json({ error: "Ism va telefon majburiy" }, { status: 400 });
  }
  if (!items || !Array.isArray(items) || items.length === 0) {
    return NextResponse.json({ error: "Savat bo'sh" }, { status: 400 });
  }

  try {
    const order = await createOrder({
      customer,
      delivery: delivery ?? { method: "kuryer" },
      payment: payment ?? { method: "naqd" },
      installService: Boolean(body.installService),
      items,
      total: 0, // backend qayta hisoblaydi
    });
    return NextResponse.json(order, { status: 201 });
  } catch (e) {
    return backendXatosi(e);
  }
}
