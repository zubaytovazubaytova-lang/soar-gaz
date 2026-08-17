import Link from "next/link";
import { notFound } from "next/navigation";
import { getOrder } from "@/lib/orders-store";
import { StatusStepper } from "@/components/StatusStepper";
import { formatSom, formatDate } from "@/lib/format";
import { ORDER_STATUS_LABEL, type DeliveryMethod, type PaymentMethod } from "@/lib/types";

export const dynamic = "force-dynamic";

const DELIVERY_LABEL: Record<DeliveryMethod, string> = { kuryer: "Kuryer yetkazib beradi", filialdan: "Filialdan olib ketish" };
const PAYMENT_LABEL: Record<PaymentMethod, string> = { naqd: "Naqd", click: "Click", payme: "Payme", karta: "Bank kartasi" };

export default async function OrderPage({ params }: { params: { id: string } }) {
  const order = await getOrder(params.id);
  if (!order) notFound();

  return (
    <div className="container-x py-10 max-w-3xl">
      <Link href="/profil/buyurtmalar" className="text-sm text-ink-600 hover:text-flame">← Buyurtmalarim</Link>

      <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
        <h1 className="font-display font-bold text-3xl">Buyurtma <span className="font-mono">{order.id}</span></h1>
        <span className="chip bg-flame-100 text-flame-700">{ORDER_STATUS_LABEL[order.status]}</span>
      </div>
      <p className="text-ink-600 text-sm mt-1">{formatDate(order.createdAt)}</p>

      {/* Holat progress */}
      <div className="card p-6 mt-6 overflow-x-auto">
        <StatusStepper status={order.status} />
      </div>

      <div className="grid sm:grid-cols-2 gap-4 mt-6">
        <div className="card p-5">
          <h2 className="font-display font-semibold mb-2">Mijoz</h2>
          <p className="text-sm">{order.customer.name}</p>
          <p className="text-sm font-mono">{order.customer.phone}</p>
          {order.customer.address && <p className="text-sm text-ink-600 mt-1">{order.customer.address}</p>}
        </div>
        <div className="card p-5">
          <h2 className="font-display font-semibold mb-2">Yetkazib berish & to'lov</h2>
          <p className="text-sm">{DELIVERY_LABEL[order.delivery.method]}</p>
          {order.delivery.note && <p className="text-sm text-ink-600">Izoh: {order.delivery.note}</p>}
          <p className="text-sm mt-1">
            To'lov: {PAYMENT_LABEL[order.payment.method]}
            {order.payment.paid
              ? <span className="chip bg-green-100 text-green-700 ml-2">To'landi ✓</span>
              : order.payment.method !== "naqd" && <span className="chip bg-ink-100 text-ink-600 ml-2">Kutilmoqda</span>}
          </p>
          {order.installService && <p className="text-sm text-steel-600">+ O'rnatish xizmati</p>}
        </div>
      </div>

      {/* Mahsulotlar */}
      <div className="card p-5 mt-4">
        <h2 className="font-display font-semibold mb-3">Mahsulotlar</h2>
        <div className="space-y-2">
          {order.items.map((it) => (
            <div key={it.productId} className="flex justify-between text-sm border-b border-ink-100 pb-2 last:border-0">
              <Link href={`/mahsulot/${it.slug}`} className="hover:text-flame">{it.name} × {it.qty}</Link>
              <span className="font-mono">{formatSom(it.price * it.qty)}</span>
            </div>
          ))}
        </div>
        <div className="flex justify-between font-bold text-lg mt-3">
          <span>Jami</span>
          <span className="font-mono text-flame">{formatSom(order.total)}</span>
        </div>
      </div>
    </div>
  );
}
