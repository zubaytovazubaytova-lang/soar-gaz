# SOAR GAZ — Xaridlar (gaz jihozlari e-commerce)

Next.js 14 (App Router) + TypeScript + Tailwind CSS asosidagi gaz jihozlari savdo
platformasi. Frontend va backend (API Routes) bitta loyihada.

## Texnologiya steki
- **Next.js 14** (App Router), **TypeScript**
- **Tailwind CSS** — dizayn tokenlari `tailwind.config.ts` da (ink / flame / steel / paper)
- **Backend**: **Django + DRF** (`../backend`, `apps/xaridlar`) — buyurtmalar,
  SMS xabarnoma va Click/Payme to'lovi shu yerda. Next.js API Routes (`app/api/*`)
  faqat proksi/validatsiya qatlami.
- **Ma'lumotlar**:
  - `lib/data.ts` — mahsulot / toifa, statik JSON (`data/*.json`), SSG uchun
  - `lib/orders-store.ts` — buyurtmalar, **Django `/api/xaridlar/`** ga murojaat
  - `lib/backend.ts` — backend HTTP klienti (`BACKEND_URL`, `BackendError`)
- **Savat**: client-side, `localStorage` + React Context (`context/CartContext.tsx`)

## O'rnatish va ishga tushirish
Avval backend (buyurtmalar shusiz ishlamaydi):
```bash
cd backend
start.bat            # http://localhost:8001
```
So'ng frontend:
```bash
cd xaridlar-app
npm install
npm run dev
# http://localhost:3000
```
Production build:
```bash
npm run build && npm start
```

### Muhit o'zgaruvchilari (`.env.local`)
| O'zgaruvchi | Vazifa | Standart |
|-------------|--------|----------|
| `BACKEND_URL` | Django backend manzili | `http://localhost:8001` |
| `BACKEND_ADMIN_TOKEN` | Admin endpointlar uchun JWT (`POST /api/auth/admin/login/` dan olinadi) | — |

## Sahifalar (SEO-friendly URL)
| URL | Vazifa |
|-----|--------|
| `/` | Bosh sahifa: hero, toifalar, mashhur mahsulotlar, xarid bosqichlari, ishonch belgilari |
| `/katalog` | Barcha bo'limlar va mahsulotlar |
| `/katalog/[category]` | Umumiy toifa mahsulotlari |
| `/mahsulot/[slug]` | Mahsulot: rasm, narx, texnik jadval, gaz sertifikati, savatga qo'shish, o'xshashlar |
| `/gaz-jihozlari` | Gaz jihozlari bo'limi (alohida arxitektura) |
| `/gaz-jihozlari/[category]` | Gaz plitalari / qozonlar / konvektorlar / ballonlar |
| `/gaz-jihozlari/xizmatlar` | O'rnatish, texnik xizmat, kafolat, trade-in |
| `/gaz-jihozlari/xavfsizlik` | Sertifikat standartlari va xavfsizlik qoidalari |
| `/gaz-jihozlari/konsultatsiya` | Interaktiv quvvat (kWt) kalkulyatori |
| `/gaz-jihozlari/optom` | B2B so'rov formasi |
| `/savat` | Savat: miqdor, umumiy summa |
| `/checkout` | Aloqa, yetkazish, o'rnatish, to'lov usuli, xulosa |
| `/buyurtma/[id]` | Buyurtma holati (progress-bar) |
| `/profil/buyurtmalar` | Telefon bo'yicha buyurtmalarni qidirish |

## API
Next.js route'lari so'rovni Django backendga uzatadi (`lib/orders-store.ts` orqali):

| Metod | Next.js | Django | Vazifa |
|-------|---------|--------|--------|
| POST | `/api/orders` | `POST /api/xaridlar/` | Buyurtma yaratish, noyob raqam (`SG-YYMM-NNNN`) |
| GET | `/api/orders?phone=` | `GET /api/xaridlar/?telefon=` | Telefon bo'yicha qidirish |
| GET | `/api/orders` | `GET /api/xaridlar/` | To'liq ro'yxat (**admin token**) |
| GET | `/api/orders/[id]` | `GET /api/xaridlar/<raqam>/` | Bitta buyurtma (ochiq) |
| PATCH | `/api/orders/[id]` | `PATCH /api/xaridlar/<raqam>/` | Holatni yangilash (**admin token**) |
| — | — | `GET /api/xaridlar/statistika/` | Hisobot (**admin token**) |

### Backend mantiqi (`backend/apps/xaridlar`)
- **Summa server tomonda hisoblanadi** — mijoz yuborgan `total` e'tiborga olinmaydi
  (o'rnatish xizmati narxi: `settings.ORNATISH_NARXI`, frontenddagi `INSTALL_PRICE` bilan mos).
- **SMS**: buyurtma yaratilganda va holat o'zgarganda `apps.sms_app` orqali xabar.
- **Onlayn to'lov**: `click`/`payme` tanlansa `TolovSorovi` yaratiladi va javobda
  `payment.url` qaytadi — checkout shu havolaga yo'naltiradi. Click/Payme webhooki
  to'lovni tasdiqlagach signal (`apps/xaridlar/signals.py`) buyurtmani
  `tolandi=True` + `tasdiqlandi` holatiga o'tkazadi.
- **Django admin**: `/admin/` da buyurtma va uning qatorlari (inline) ko'rinadi.

## Ma'lumotlar modeli
`lib/types.ts` da: `Category`, `Product` (+ ixtiyoriy `gas`), `Order`, `CartLine`.
Buyurtma holatlari: qabul_qilindi → tasdiqlandi → tayyorlanmoqda → jo'natildi → yetkazildi.
Django tomonda: `Xarid` + `XaridQatori` (`backend/apps/xaridlar/models.py`), holat
kodlari `OrderStatus` bilan bir xil, serializer camelCase `Order` shaklida qaytaradi.

## Dizayn
- Ranglar: **ink** `#1B2430` (matn), **flame** `#E8830C` (CTA), **steel** `#3B6E8F`
  (ishonch/xavfsizlik), **paper** `#F7F6F2` (fon)
- Shriftlar: Space Grotesk (sarlavha), Inter (matn), JetBrains Mono (narx/texnik)
- Signature element: texnik spetsifikatsiyalar **"narx yorlig'i"** uslubida
  (dashed border + mono) — `.spec-tag`
- To'liq responsive (mobil menyu, grid moslashuvi)

## Productionga o'tish tavsiyalari
1. **To'lov kalitlari**: `backend/soargaz/settings.py` dagi `CLICK_*` / `PAYME_*`
   bo'sh — merchant kabinetdan olingan kalitlarni qo'ying, aks holda webhook
   "sozlanmagan" javobini qaytaradi. `TOLOV_RETURN_URL` ni ham saytga moslang.
2. **Django settings**: `DEBUG=False`, haqiqiy `SECRET_KEY`, `ALLOWED_HOSTS`,
   `CORS_ALLOW_ALL_ORIGINS` o'rniga aniq domenlar; SQLite → PostgreSQL.
3. **Mijoz autentifikatsiyasi**: hozir buyurtmani raqami yoki telefoni bilan
   kim bo'lsa ham ko'ra oladi. `apps.auth_app` dagi OTP oqimini `/profil` ga ulang.
4. **Admin panel**: Django `/admin/` tayyor. Sayt ichida boshqaruv kerak bo'lsa —
   `/admin` sahifasi `PATCH /api/orders/[id]` dan foydalanadi (`BACKEND_ADMIN_TOKEN`).
5. **Katalog**: mahsulot/toifa hali `data/*.json` da (SSG uchun qulay). Narx va
   qoldiqni operatorlar boshqarishi kerak bo'lsa — Django'ga `Mahsulot` modeli
   qo'shib, `lib/data.ts` ni `lib/backend.ts` orqali o'tkazing.
6. **Rasmlar**: emoji-placeholder o'rniga `next/image` + haqiqiy rasm/CDN.
