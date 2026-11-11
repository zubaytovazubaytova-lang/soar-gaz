# SOAR GAZ — arxitektura xaritasi (dasturchi uchun)

Bu hujjat kodni o'qishni boshlash uchun **yo'l xaritasi**. U kod va sozlamalarni
ko'zdan kechirib tuzilgan; to'liq xavfsizlik audit emas. Serverga qo'yish
tafsilotlari — `SERVERGA_QOYISH.md`, nginx — `nginx-xavfsiz.conf`.

## 1. Umumiy ko'rinish

Loyiha **uchta qismdan** iborat va bitta domen ostida ishlaydi:

```
                      brauzer
                         |
                       nginx
          +--------------+----------------+
          |                               |
   /xaridlar/*                     hamma qolgan yo'llar
          |                               |
  Next.js 14 (:3000)              Django + DRF (gunicorn :8001)
  xaridlar do'koni                 - HTML sahifalarni ham o'zi beradi
          |                        - /api/*  REST
          |  server-to-server      - /admin/ Django admin
          +---- /api/xaridlar/ --->- /images, /assets, /vendor ...
                                          |
                                       SQLite (db.sqlite3)
                                       Redis (ixtiyoriy kesh)
```

| Qism | Papka | Texnologiya |
|---|---|---|
| Marketing sayti + 3 ta panel (SPA emas, oddiy HTML+JS) | loyiha ildizi: `index.html`, `kabinet.html`, `xodimlar.html`, `admin.html`, `sw.js` | HTML, Tailwind (build: `npm run css`), vanilla JS |
| Backend | `backend/` | Django 4.2, DRF 3.15, SimpleJWT, SQLite |
| Xaridlar (onlayn do'kon) | `xaridlar-app/` | Next.js 14 (App Router), React 18, TypeScript, Tailwind |

## 2. Frontend (ildizdagi HTML sahifalar)

Bular **Django orqali beriladi** (`backend/soargaz/urls.py` — `_sahifa()` funksiyasi),
alohida statik hosting yo'q.

| URL | Fayl | Kim uchun |
|---|---|---|
| `/` | `index.html` (~700 KB, ichida ma'lumot ro'yxatlari va JS) | ommaviy sayt, mahsulot katalogi |
| `/kabinet/` | `kabinet.html` | mijoz kabineti (OTP bilan kirish) |
| `/xodimlar/` | `xodimlar.html` | xodim portali (lavozimga qarab 4 tur: dala / servis / call center / kadrlar) |
| `/boshqaruv/` | `admin.html` | rahbariyat/direktor paneli (parol + SMS 2FA) |
| `/kvitansiya/<token>/`, `/shartnoma/<token>/` | Django shablonlari (`apps/hujjatlar`) | mijozga SMS bilan boradigan hujjat |

Eslatmalar:
- `/boshqaruv/` (maxsus panel) va `/admin/` (Django admin) — **ikki xil narsa**.
- `sw.js` — PWA service worker; faqat o'zgarmas resurslarni keshlaydi, API/sahifani emas.
  Versiya o'zgaruvchisi `VERSIYA` (hozir `soargaz-v5`).
- Rasmlar `images/` da; brauzer WebP qo'llasa, `rasm_bilan_webp` view `.webp` nusxani beradi
  (`npm run rasm` yaratadi).
- Sahifa skriptlari tashqi fayllarda: `scripts/<sahifa>-asosiy.js`. Hodisa handlerlari HTML'da
  `onclick="..."` emas, `data-h-click="h12"` belgisi bo'lib turadi; ular `scripts/<sahifa>-hodisalar.js`
  da, ishga tushirgichi `scripts/hodisa-boshqaruvchi.js` (qoidalar o'sha fayl boshida yozilgan).
  Shu sababli CSP `script-src` da `'unsafe-inline'` yo'q. **Yangi tugma qo'shsangiz** `onclick` YOZMANG:
  elementga `data-h-click="c:funksiyaNomi" data-a-click="${SG_A([id])}"` (JS shablonida) yoki
  `addEventListener` ishlating. `backend/soargaz/tests_csp.py` inline handler qaytib kirsa xato beradi.

## 3. Backend (`backend/`)

Loyiha moduli: `soargaz/` (settings, urls, middleware, `admin_site.py` — rahbariyat bosh sahifasi).
Ilovalar `backend/apps/` da; hajmi (test bo'lmagan `.py` qatorlari, taxminan):

| Ilova | Vazifasi | Hajm |
|---|---|---|
| `auth_app` | **Maxsus foydalanuvchi modeli** `Foydalanuvchi` (+ proksi `Xodim`, `Mijoz`), OTP, JWT, admin 2FA, rollar/kabinet turlari, audit jurnali, ko'rish huquqlari (`korish.py`), rahbariyat, IP throttle | ~3300 (eng katta, 23 migratsiya) |
| `buyurtmalar` | Servis buyurtmalari (`Buyurtma`, foto, xizmat), qo'ng'iroq so'rovlari, statistika | ~2400 |
| `hujjatlar` | Kvitansiya, shartnoma, hisoblagich, topshiriq (ish buyrug'i), hujjat loyihalari | ~2400 |
| `xaridlar` | Onlayn do'kon buyurtmalari (`Xarid`, `XaridQatori`, `Promokod`), summa hisobi (`hisob.py`), to'lov (`tolov.py`) | ~1300 |
| `kabinet` | Mijoz kabineti: obyekt, uskuna, hisoblagich, murojaat, bildirishnoma, sharh | ~1200 |
| `narxnoma` | Narxnoma (prays-list) va qatorlari | ~800 |
| `tushum` | Tushum (kirim) hisobi | ~850 |
| `katalog` | Narxlar, hujjat/sertifikat, media | ~750 |
| `kadrlar` | Kunlik hisobot, xodim hujjatlari, davomat | ~730 |
| `tolovlar` | Click/Payme to'lov so'rovlari, mahsulot so'rovi, metrologiya arizasi | ~650 |
| `joylashuv` | Smena, GPS nuqtalar, rozilik | ~470 |
| `sms_app` | SMS yuborish (Eskiz yoki konsol), jurnal | ~320 |
| `aloqa` | Aloqa formasi xabarlari | ~210 |

API tuzilishi: `/api/<ilova>/...` (ro'yxat `soargaz/urls.py` oxirida; ildiz `/api/` endpointlar
indeksini beradi).

### Autentifikatsiya va huquqlar
- Mijoz: telefon + **SMS OTP** (bir marta; keyin JWT sessiya).
- Xodim/admin: telefon + parol; boshqaruv panelida qo'shimcha **SMS 2FA** (`DJANGO_ADMIN_2FA`).
- Token: SimpleJWT. Muddatlar ataylab uzun (access 7 kun, refresh 365 kun), **blacklist yo'q** —
  ma'lum zaif nuqta (`SERVERGA_QOYISH.md` §9 "Qolgan ishlar").
- Himoya: telefon bo'yicha blok (4 urinish), IP bo'yicha throttle (`throttles.py`), audit jurnali.
- Huquq tekshiruvi view darajasida (`@permission_classes`, rol tekshiruvlari, `korish.py`).
  **Tekshirish tavsiya etiladi:** har bir endpointda rol va "o'z ma'lumoti" tekshiruvi (IDOR).

### Tashqi integratsiyalar
| Xizmat | Sozlama | Izoh |
|---|---|---|
| Eskiz SMS | `SMS_PROVAYDER`, `ESKIZ_*` | standart `konsol` — SMS haqiqatda ketmaydi |
| Click / Payme | `CLICK_*`, `PAYME_*` | to'lov webhooklari `tolovlar`/`xaridlar` da |
| Nominatim geokod | `GEOKOD_URL` | manzil -> koordinata |
| Redis | `REDIS_URL` | ixtiyoriy; yo'q bo'lsa LocMemCache, statistika keshi o'chiq |

### Muhit o'zgaruvchilari
Hammasi `settings.py` da `os.environ` orqali; to'liq ro'yxat va majburiylari —
`SERVERGA_QOYISH.md` §1. `DJANGO_DEBUG=0` bo'lganda zaif `SECRET_KEY` yoki `*` hosts bilan
server ishga tushmaydi. **Standart `DEBUG=1`** ekanini yodda tuting.

## 4. Xaridlar do'koni (`xaridlar-app/`)

- Next.js App Router. Mahsulot va toifalar — **statik JSON** (`data/products.json`,
  `categories.json`), `lib/data.ts` orqali o'qiladi (kelajakda DB ga ko'chirishga tayyor qatlam).
- Savat — `context/CartContext.tsx` (brauzerda).
- Buyurtmalar — **Django'da saqlanadi**: `lib/orders-store.ts` -> `lib/backend.ts` ->
  `POST /api/xaridlar/`. Summani backend o'zi hisoblaydi (klient `total` yubormaydi).
- Next.js API route'lari (`app/api/orders/*`) — brauzer va Django orasidagi proksi qatlam;
  faqat buyurtma yaratish (POST) va holatni ko'rish (GET, niqoblangan) bor. Admin tokeni ishlatilmaydi:
  ro'yxat va holat o'zgartirish ochiq marshrutlarda bo'lmasligi shart.
- Production'da `NEXT_BASE_PATH=/xaridlar` bilan build qilinadi.
- Eslatma: katalog ikki joyda yashaydi — `index.html` ichidagi ro'yxatlar/`katalog` ilovasi va
  `xaridlar-app/data/*.json`. Ular orasida avtomatik sinxronlash yo'q.

## 5. Ma'lumotlar bazasi
SQLite (`backend/db.sqlite3`, ZIP ga **kiritilmagan**). Production uchun PostgreSQL ga o'tish
rejalashtirilgan, lekin hali qilinmagan. Migratsiyalar `apps/*/migrations/` da; eng uzun zanjir
`auth_app` (0001–0023). Sinov: `python manage.py test` (35 ta test fayli).

## 6. Ishga tushirish (lokal)

```
# Backend
cd backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser      # yoki create_admin.py
python manage.py runserver 8001

# Sayt CSS (ildizda)
npm install && npm run css

# Do'kon
cd xaridlar-app
npm install && npm run dev            # http://localhost:3000, BACKEND_URL=http://localhost:8001
```

## 7. Tekshirishda e'tibor berilsin (taklif)

1. **Huquqlar:** `auth_app` va `kabinet`/`buyurtmalar`/`hujjatlar` view'larida rol va egalik tekshiruvi.
2. **Token siyosati:** uzun muddatli JWT + blacklist yo'qligi.
3. **To'lov webhooklari** (Click/Payme): imzo tekshiruvi, takroriy chaqiruvga chidamlilik (idempotentlik).
4. **SQLite** bir vaqtda yozish va gunicorn ko'p worker bilan; PostgreSQL ga o'tish.
5. **Katta HTML fayllar** (`index.html`, `admin.html`, `xodimlar.html`) — modullashtirish, CSP.
6. **Katalog manbalarining ikkilanishi** (`index.html` va `xaridlar-app/data`).
7. **Test qamrovi:** testlar bor, lekin `xaridlar-app` da test yo'q; CI sozlanmagan.
8. **Git holati:** ko'p o'zgarishlar hali commit qilinmagan (ZIP shu ishchi holatni aks ettiradi).
