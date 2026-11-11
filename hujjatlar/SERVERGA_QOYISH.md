# SOAR GAZ — serverga qo'yish qo'llanmasi

Bu hujjat loyihani haqiqiy serverga (production) chiqarish tartibini va
majburiy sozlamalarni bayon qiladi.

---

## 1. Muhit o'zgaruvchilari (majburiy)

Serverda quyidagilar **albatta** o'rnatilishi kerak. Ular berilmasa loyiha
dev rejimida ishlaydi va xavfsiz emas.

| O'zgaruvchi | Namuna | Izoh |
|---|---|---|
| `DJANGO_DEBUG` | `0` | **Majburiy.** `1` qolsa xatolar va kod mijozga ko'rinadi |
| `DJANGO_SECRET_KEY` | uzun tasodifiy satr | **Majburiy.** Standart kalit kodda qolgan |
| `DJANGO_HOSTS` | `soargaz.uz,www.soargaz.uz` | Ruxsat etilgan domenlar |
| `DJANGO_CORS` | `https://soargaz.uz` | Frontend domeni (webhook uchun CSRF ham) |
| `ADMIN_TELEFON` | `+998918332249` | Birinchi admin |
| `ADMIN_PAROL` | kuchli parol | Berilmasa admin yaratilmaydi |
| `REDIS_URL` | `redis://127.0.0.1:6379/1` | Umumiy kesh. Berilmasa hisobot keshi o'chiq qoladi (pastga qarang) |
| `SMS_PROVAYDER` | `eskiz` | `konsol` — SMS yuborilmaydi (faqat dev) |
| `ESKIZ_EMAIL` / `ESKIZ_PAROL` | kabinet ma'lumotlari | Eskiz.uz hisobi |
| `ESKIZ_FROM` | `4546` | Tasdiqlangan nick |
| `TOLOV_RETURN_URL` | `https://soargaz.uz/` | **Majburiy.** Mijoz to'lovdan keyin shu manzilga qaytadi |
| `CLICK_SERVICE_ID` | merchant kabinetdan | Click Service ID |
| `CLICK_MERCHANT_ID` | merchant kabinetdan | Click Merchant ID |
| `CLICK_SECRET_KEY` | merchant kabinetdan | Webhook imzosi uchun |
| `PAYME_MERCHANT_ID` | merchant kabinetdan | Payme kassa ID |
| `PAYME_KEY` | merchant kabinetdan | Webhook Basic-auth uchun |

SECRET_KEY yaratish:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## 2. To'lov tizimlari

Kalitlar **kodda saqlanmaydi** — yuqoridagi jadvaldagi muhit
o'zgaruvchilari orqali beriladi.

`TOLOV_RETURN_URL` ga alohida e'tibor bering: u berilmasa
`http://localhost:8001/` qolib ketadi va mijoz to'lovdan keyin
sizning saytingizga qayta olmaydi. `DEBUG=False` da server ishga
tushayotganda bu holat uchun ogohlantirish chiqaradi.

Webhook manzillari (merchant kabinetiga shu manzillar kiritiladi):

```
Click Prepare:  https://soargaz.uz/api/tolovlar/click/prepare/
Click Complete: https://soargaz.uz/api/tolovlar/click/complete/
Payme:          https://soargaz.uz/api/tolovlar/payme/
```

Ikkala webhook ham imzoni va **to'langan summani** tekshiradi.

## 3. Ma'lumotlar bazasi

**Serverda PostgreSQL SHART.** SQLite bir vaqtda bitta yozuvchini qabul qiladi:
60 ta parallel buyurtmada deyarli hammasi `database is locked` (500) berdi.
Sozlamalar `settings.py` da tayyor — faqat muhit o'zgaruvchilarini bering
(`DB_NOMI` berilsa PostgreSQL, berilmasa SQLite — lokal ishlash uchun):

| O'zgaruvchi | Izoh |
|---|---|
| `DB_NOMI`, `DB_FOYDALANUVCHI`, `DB_PAROL` | majburiy (uchalasi ham) |
| `DB_HOST`, `DB_PORT` | ixtiyoriy, standart `localhost` / `5432` |

`pip install -r requirements.txt` (`psycopg2-binary` kiradi), keyin
`python manage.py migrate`. `DJANGO_DEBUG=0` bo'lib `DB_NOMI` berilmasa
ishga tushganda ogohlantirish chiqadi.

**JWT blacklist.** `python manage.py migrate` `token_blacklist` jadvallarini
ham yaratadi. Muddati o'tgan yozuvlarni haftada bir marta tozalang (cron):
`python manage.py flushexpiredtokens`.

**Narxlar.** Buyurtma narxi serverda `backend/apps/xaridlar/data/products.json` dan
olinadi (`apps/xaridlar/mahsulotlar.py`). Fayl boshqa joyda bo'lsa:
`XARID_MAHSULOTLAR_FAYL=/to'liq/yo'l/products.json`.

## 3.1. Kesh (Redis)

Admin paneldagi statistika hisobotlari (`/api/buyurtmalar/statistika/`,
`/api/xaridlar/statistika/`) butun jadvalni skanerlaydi, shuning uchun
javob 5 daqiqaga keshlanadi.

Kesh **faqat `REDIS_URL` berilganda** yoqiladi. Sababi: Redis'siz Django
`LocMemCache` ishlatadi, u esa har gunicorn worker'ida **alohida** —
u holda bitta admin yangi raqamni, boshqasi eski raqamni ko'rib qolardi.
Shu xatoni oldini olish uchun `REDIS_URL` bo'lmasa keshlash o'chiriladi
va hisobot har safar qaytadan hisoblanadi (sekinroq, lekin har doim aniq).

```bash
sudo apt install redis-server
pip install redis                 # requirements.txt da bor
export REDIS_URL=redis://127.0.0.1:6379/1
```

Kesh muddatini o'zgartirish: `STATISTIKA_KESH_SONIYA=600` (standart 300).
`DEBUG=False` va `REDIS_URL` yo'q bo'lsa server ishga tushishda
ogohlantirish chiqaradi.

Redis'ni tashqi tarmoqqa ochmang — `redis.conf` da `bind 127.0.0.1`.

## 4. Server (nginx + gunicorn)

`runserver` — dev vositasi, productionda ishlatilmaydi.

```bash
pip install gunicorn
gunicorn soargaz.wsgi:application --bind 127.0.0.1:8001 --workers 3
```

nginx namunasi:

```nginx
server {
    listen 443 ssl;
    server_name soargaz.uz;

    ssl_certificate     /etc/letsencrypt/live/soargaz.uz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/soargaz.uz/privkey.pem;

    client_max_body_size 32M;       # xodim hujjati 30 MB gacha

    # MUHIM: mijoz hujjatlari to'g'ridan-to'g'ri berilmasin —
    # ular faqat /api/kabinet/hujjat/<token>/ orqali beriladi
    location /media/kabinet_hujjatlar/ { deny all; return 404; }
    location /media/hujjatlar_maxfiy/  { deny all; return 404; }

    location /media/  { alias /srv/soargaz/backend/media/; }
    location /static/ { alias /srv/soargaz/backend/static/; }

    # Uslub, shrift va kutubxonalar — deploy paytidagina o'zgaradi.
    # Django orqali o'tkazmasdan to'g'ridan-to'g'ri beramiz.
    location /assets/ {
        alias /srv/soargaz/assets/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    location /vendor/ {
        alias /srv/soargaz/vendor/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Service worker HECH QACHON keshlanmasin — aks holda eski versiya
    # brauzerda qotib qoladi va sayt yangilanmay qo'yadi.
    location = /sw.js {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # Xaridlar do'koni (Next.js). index.html dagi havola nisbiy
    # `/xaridlar/` — shu yerda ilovaga uzatiladi.
    # Ilova NEXT_BASE_PATH=/xaridlar bilan build qilingan bo'lishi shart.
    location /xaridlar/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Xaridlar do'konini ishga tushirish

Do'kon alohida Node jarayoni. Django bilan yonma-yon turadi:

```bash
cd /srv/soargaz/xaridlar-app
npm ci
NEXT_BASE_PATH=/xaridlar BACKEND_URL=http://127.0.0.1:8001 npm run build
NEXT_BASE_PATH=/xaridlar BACKEND_URL=http://127.0.0.1:8001 npm start
```

`NEXT_BASE_PATH` siz build qilinsa, do'konning CSS/JS fayllari `/xaridlar/`
ostida topilmaydi va sahifa uslubsiz ochiladi.

`DEBUG=False` bo'lganda HTTPS majburlash, HSTS, xavfsiz cookie va
clickjacking himoyasi avtomatik yoqiladi — lekin **avval TLS sertifikati
o'rnatilgan bo'lishi shart**, aks holda sayt ochilmay qoladi.

Static fayllarni yig'ish:

```bash
python manage.py collectstatic --noinput
```

## 5. Ishga tushirish tartibi

```bash
# 1) Frontend resurslarini yig'ish (loyiha ildizida)
npm ci
npm run build            # Tailwind CSS + rasmlarning WebP nusxalari

# 2) Backend
cd backend
python manage.py migrate            # --run-syncdb EMAS
python create_admin.py              # ADMIN_PAROL o'rnatilgan holda
python manage.py collectstatic --noinput
gunicorn soargaz.wsgi:application --bind 127.0.0.1:8001 --workers 3
```

**`npm run build` ni o'tkazib yubormang.** U ikki narsani qiladi:

- `assets/tailwind.css` ni generatsiya qiladi — bu fayl bo'lmasa sayt
  butunlay uslubsiz ochiladi (ilgari Tailwind brauzerda CDN orqali
  ishlardi, endi build vaqtida tayyorlanadi);
- `images/` ichidagi rasmlarning `.webp` nusxalarini yaratadi — ular
  bo'lmasa sayt ishlaydi, lekin mobil mijoz ikki barobar ko'p trafik
  sarflaydi.

`index.html` dagi ranglarni yoki Tailwind sinflarini o'zgartirgandan
keyin `npm run css` ni qayta ishga tushirish shart.

## 6. Rejalashtirilgan vazifa (cron)

Hisoblagich tekshiruvi eslatmalari kuniga bir marta yuboriladi:

```cron
0 9 * * * cd /srv/soargaz/backend && venv/bin/python manage.py tekshiruv_eslatma
```

Windows serverda — Task Scheduler orqali shu buyruq.

## 7. Zaxira nusxa

```cron
0 2 * * * sqlite3 /srv/soargaz/backend/db.sqlite3 ".backup /srv/zaxira/db-$(date +\%F).sqlite3"
```

`media/` papkasini ham zaxiralang — hujjatlar va mahsulot rasmlari o'sha yerda.

## 8. Chiqishdan oldingi tekshiruv ro'yxati

- [ ] `DJANGO_DEBUG=0`, yangi `DJANGO_SECRET_KEY`
- [ ] `DJANGO_HOSTS` aniq domenlar (`*` emas)
- [ ] Admin paroli almashtirilgan, kodda yo'q
- [ ] SMS provayder ulangan va sinovdan o'tgan (kabinetga kirib ko'ring)
- [ ] Click/Payme kalitlari, webhook manzillari merchant kabinetida
- [ ] TLS sertifikat, `https://` ochiladi
- [ ] nginx `/media/kabinet_hujjatlar/` ni bloklaydi
- [ ] `python manage.py check --deploy` ogohlantirishlari ko'rib chiqilgan
- [ ] Zaxira nusxa va cron ishlayapti
- [ ] `REDIS_URL` o'rnatilgan (ko'p worker'da hisobot keshi uchun shart)
- [ ] nginx sozlamasi `nginx-xavfsiz.conf` dan olingan (HTTP→HTTPS, so'rov cheklovi, maxfiy fayllar yopiq)
- [ ] `DJANGO_PROXIES=1` (nginx orqasida; proksisiz ishlasa `0`) — aks holda IP cheklovi aylanib o'tiladi
- [ ] `db.sqlite3` va `.env` ruxsati faqat gunicorn foydalanuvchisiga (`chmod 600`), gunicorn root'dan EMAS
- [ ] https://securityheaders.com orqali sarlavhalar tekshirilgan

## 9. Xavfsizlik (2026-10 da kuchaytirilgan)

### Server o'zi rad etadigan xavfli sozlamalar
`DJANGO_DEBUG=0` bo'lganda quyidagilardan birortasi bo'lsa, server **ishga
tushmaydi** (`ImproperlyConfigured`) — jimgina xavfli ishlab ketmaydi:

- `DJANGO_SECRET_KEY` berilmagan yoki 50 belgidan qisqa (standart kalit kodda ma'lum);
- `DJANGO_HOSTS` bo'sh yoki `*`.

### IP bo'yicha cheklov (`apps/auth_app/throttles.py`)
Telefon raqam bo'yicha cheklovlar (OTP, admin bloki) bitta raqamni himoya
qiladi. Minglab turli raqamni sinash (SMS to'ldirish, parol taxmini) ni
IP cheklovlari to'sadi:

| Endpoint | Chegara (bir IP dan) |
|---|---|
| admin / xodim login | 10 / daqiqa |
| OTP so'rash | 30 / soat |
| OTP tekshirish | 15 / daqiqa |
| ro'yxatdan o'tish | 20 / soat |

IP `X-Forwarded-For` dan olinadi, shuning uchun **`DJANGO_PROXIES`
to'g'ri bo'lishi shart**: nginx orqasida `1` (standart), to'g'ridan-to'g'ri
`0`. Cloudflare + nginx bo'lsa `2`. Noto'g'ri qiymat chegarani aylanib
o'tishga imkon beradi.

> Redis'siz `LocMemCache` har gunicorn worker'ida alohida — chegara
> worker soniga ko'paytirib hisoblanadi. `REDIS_URL` berish buni to'g'rilaydi.

### Sarlavhalar (`soargaz/middleware.py`)
Content-Security-Policy, Permissions-Policy, Cross-Origin-Resource-Policy,
API javoblarida `Cache-Control: no-store`. HSTS, X-Frame-Options, cookie
bayroqlari — oldin bor edi (`settings.py`).

CSP `script-src` da `'unsafe-inline'` YO'Q: sahifa skriptlari tashqi fayllarda,
hodisa handlerlari `data-h-*` belgisi orqali ishlaydi (`scripts/hodisa-boshqaruvchi.js`).
Django shablonlaridagi inline `<script>` har so'rovda yangi `nonce` oladi
(`<script nonce="{{ request.csp_nonce }}">`). Faqat `style-src` da `'unsafe-inline'`
qoldi (~1000 ta `style="..."`). CSP tashqi domendan skript yuklashni,
`<object>`, `<base>` o'g'irlashni, saytni boshqa saytga `<iframe>` qilishni
va ma'lumotni begona domenga yuborishni to'sadi.

Yangi funksiya qo'shganda biror narsa bloklansa:
`DJANGO_CSP=report-only` (faqat kuzatadi, bloklamaydi), brauzer konsolida
nima to'silganini ko'ring va `CSP_MANBALAR` ga qo'shing. `DJANGO_CSP=0`
butunlay o'chiradi — faqat favqulodda holat uchun.

### Qolgan ishlar (hali qilinmagan)
- **JWT muddati:** access token 7 kun, refresh 365 kun. Mijoz ilovasi
  sessiyani yil davomida saqlashi uchun ataylab shunday, lekin token
  o'g'irlansa, 7 kun ishlaydi (qaytarib olish — blacklist — yo'q).
  `rest_framework_simplejwt.token_blacklist` ni yoqish va access
  muddatini 1 kunga tushirish tavsiya etiladi (frontend refresh oqimini
  sinash kerak).
- **Inline skriptlarni tashqi faylga ko'chirib**, CSP dan `'unsafe-inline'`
  ni olib tashlash (nonce bilan).
- **SQLite → PostgreSQL** (3-bo'limga qarang).
- **Tashqi monitoring / fail2ban:** nginx 429/401 jurnalini kuzatish.



## 10. Sessiya xavfsizligi (mijoz va xodim kirishi)

**Tokenlar.** Access token 30 daqiqa (`JWT_ACCESS_DAQIQA`), refresh — mijoz uchun 90 kun
(`JWT_REFRESH_KUN`), xodim uchun 14 kun. Refresh brauzerda **httpOnly cookie**da turadi
(`sg_refresh` — mijoz, `sg_refresh_xodim` — xodim; ikkalasi `Secure` + `SameSite=Lax`, faqat
`/api/auth/` ga yuboriladi), shuning uchun JavaScript (XSS) uni o'qiy olmaydi. Har yangilashda
eskisi bekor qilinadi (`token_blacklist`). Logout — `POST /api/auth/chiqish/`.

- nginx `Cookie` / `Set-Cookie` sarlavhalarini o'tkazishi shart (standart sozlamada o'tadi).
- HTTPS bo'lmasa `Secure` cookie ishlamaydi: avval SSL, keyin `DJANGO_DEBUG=0`.
- Mobil ilova cookie ishlatmaydi: `X-Klient: mobil` sarlavhasi yuboradi va refresh'ni javob
  tanasida oladi (`/api/auth/otp/tasdiqlash/`, `/api/auth/token/yangilash/`).
- Muddati o'tgan blacklist yozuvlari: `manage.py flushexpiredtokens` (haftada bir, cron).

**Maxfiy amallar SMS kod talab qiladi:** email / qo'shimcha telefon o'zgartirish va hisobni
o'chirish (`POST /api/auth/tasdiq-kodi/` kodni egasining O'Z telefoniga yuboradi).

**Buyurtma raqami egalik dalili emas.** `GET /api/xaridlar/<raqam>/` mehmonga ism/telefon/manzil
va kuryer joylashuvini bermaydi (niqoblanadi). To'liq ma'lumot — tizimga kirgan egasi, xodim,
admin yoki telefon oxiri (`X-Telefon-Oxiri` sarlavhasi / `POST .../korish/`). To'lov usulini va
qayta yetkazish manzilini o'zgartirish ham shuni talab qiladi. Taxmin: buyurtma boshiga soatiga 8 ta.

**Next.js do'koni** Django'ga admin tokeni bilan murojaat QILMAYDI (`BACKEND_ADMIN_TOKEN` olib
tashlangan). Serverdagi `.env` dan uni o'chirib tashlang.

**Jonli serverga chiqishdan oldin (lokalda tekshirib bo'lmaydi):**
- [ ] `DJANGO_DEBUG=0`, HTTPS, `manage.py check --deploy` — xatosiz
- [ ] brauzer DevTools → Application → Cookies: `sg_refresh` uchun `HttpOnly` va `Secure` belgilari
- [ ] mijoz bilan kirish → 30+ daqiqadan keyin ham SMS so'ralmaydi (jim yangilanadi)
- [ ] logout'dan keyin eski cookie bilan `/api/auth/token/yangilash/` → 401
- [ ] `Redis` (`REDIS_URL`) va `PostgreSQL` (`DB_NOMI`) yoqilgan
