// ─────────────────────────────────────────────────────────────
//  Django backend bilan aloqa (faqat server tomonda ishlatiladi)
//  Backend: c:\Users\user\Desktop\soar-gaz\backend  (Django + DRF)
//  Manzil `BACKEND_URL` muhit o'zgaruvchisidan olinadi.
// ─────────────────────────────────────────────────────────────

export const BACKEND_URL = (
  process.env.BACKEND_URL || "http://localhost:8001"
).replace(/\/$/, "");

/** Admin endpointlar uchun JWT (ixtiyoriy — faqat server .env da turadi). */
const ADMIN_TOKEN = process.env.BACKEND_ADMIN_TOKEN || "";

export class BackendError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "BackendError";
  }
}

interface CallOptions {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  /** Admin huquqi talab qilinadigan endpointlar uchun */
  auth?: boolean;
}

export async function backendCall<T>(
  path: string,
  { method = "GET", body, auth = false }: CallOptions = {}
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth && ADMIN_TOKEN) headers.Authorization = `Bearer ${ADMIN_TOKEN}`;

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new BackendError("Backend bilan aloqa yo'q", 503);
  }

  if (res.status === 204) return undefined as T;

  const matn = await res.text();
  let data: unknown = undefined;
  try {
    data = matn ? JSON.parse(matn) : undefined;
  } catch {
    /* JSON emas — quyida xato sifatida qaytadi */
  }

  if (!res.ok) {
    const detail =
      (data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : "") || `Backend xatosi (${res.status})`;
    throw new BackendError(detail, res.status);
  }

  return data as T;
}
