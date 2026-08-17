import { ORDER_FLOW, ORDER_STATUS_LABEL, type OrderStatus } from "@/lib/types";

export function StatusStepper({ status }: { status: OrderStatus }) {
  if (status === "bekor") {
    return (
      <div className="rounded-xl bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm font-semibold">
        Buyurtma bekor qilindi
      </div>
    );
  }
  const currentIdx = ORDER_FLOW.indexOf(status);

  return (
    <ol className="flex items-center">
      {ORDER_FLOW.map((s, i) => {
        const done = i <= currentIdx;
        const isLast = i === ORDER_FLOW.length - 1;
        return (
          <li key={s} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center text-center">
              <span
                className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold border-2 ${
                  done
                    ? "bg-flame border-flame text-white"
                    : "bg-white border-ink-100 text-ink-600"
                }`}
              >
                {done ? "✓" : i + 1}
              </span>
              <span className={`mt-1.5 text-[11px] w-20 ${done ? "text-ink font-semibold" : "text-ink-600"}`}>
                {ORDER_STATUS_LABEL[s]}
              </span>
            </div>
            {!isLast && (
              <div className={`h-0.5 flex-1 mx-1 -mt-6 ${i < currentIdx ? "bg-flame" : "bg-ink-100"}`} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
