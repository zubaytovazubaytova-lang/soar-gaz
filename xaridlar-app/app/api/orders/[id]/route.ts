import { NextResponse } from "next/server";
import { getOrder, updateOrderStatus } from "@/lib/orders-store";
import { BackendError } from "@/lib/backend";
import { ORDER_STATUS_LABEL, type OrderStatus } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function backendXatosi(e: unknown) {
  if (e instanceof BackendError) {
    return NextResponse.json({ error: e.message }, { status: e.status });
  }
  return NextResponse.json({ error: "Kutilmagan xatolik" }, { status: 500 });
}

// GET /api/orders/[id] — bitta buyurtma holati
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  try {
    const order = await getOrder(params.id);
    if (!order) return NextResponse.json({ error: "Topilmadi" }, { status: 404 });
    return NextResponse.json(order);
  } catch (e) {
    return backendXatosi(e);
  }
}

// PATCH /api/orders/[id] — holatni yangilash (admin uchun)
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  let body: { status?: OrderStatus };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Noto'g'ri JSON" }, { status: 400 });
  }
  const status = body.status;
  if (!status || !(status in ORDER_STATUS_LABEL)) {
    return NextResponse.json({ error: "Noto'g'ri holat" }, { status: 400 });
  }
  try {
    const order = await updateOrderStatus(params.id, status);
    if (!order) return NextResponse.json({ error: "Topilmadi" }, { status: 404 });
    return NextResponse.json(order);
  } catch (e) {
    return backendXatosi(e);
  }
}
