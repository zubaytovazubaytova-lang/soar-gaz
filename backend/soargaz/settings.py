import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# Productionda muhit o'zgaruvchisidan olinadi (kodda qolmasin)
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY', 'soargaz-django-secret-key-change-in-production-2025')

# Serverga chiqarishda: DJANGO_DEBUG=0
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'

# Serverga chiqarishda: DJANGO_HOSTS=soargaz.uz,www.soargaz.uz
ALLOWED_HOSTS = [h for h in os.environ.get('DJANGO_HOSTS', '*').split(',') if h]

# ──────────────────────────────────────────────────────────────
#  PRODUCTION'DA XAVFLI SOZLAMALARNI RAD ETISH
#
#  Ilgari bu holatlar faqat hujjatda "unutmang" deb yozilgan edi. Endi
#  server DEBUG=0 da xavfli sozlama bilan UMUMAN ISHGA TUSHMAYDI — jimgina
#  ishlab, standart kalit bilan sessiya/JWT soxtalashtirilishiga yo'l
#  qo'ymaydi. Dev rejimida (DEBUG=1) hech narsa o'zgarmaydi.
# ──────────────────────────────────────────────────────────────
if not DEBUG:
    from django.core.exceptions import ImproperlyConfigured
    if SECRET_KEY.startswith('soargaz-django-secret-key') or len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY berilmagan yoki juda qisqa (kamida 50 belgi). "
            "Yaratish: python -c \"import secrets; print(secrets.token_urlsafe(64))\"")
    if '*' in ALLOWED_HOSTS or not ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "DJANGO_HOSTS aniq domenlar bo'lishi shart (masalan "
            "soargaz.uz,www.soargaz.uz) — '*' production'da taqiqlangan.")

INSTALLED_APPS = [
    'soargaz.apps.SoarAdminConfig',      # django.contrib.admin + Rahbariyat bosh sahifasi (soargaz/admin_site.py)
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',   # logout va rotatsiyada tokenni bekor qilish
    'corsheaders',
    'apps.auth_app',
    'apps.aloqa',
    'apps.kadrlar',
    'apps.hujjatlar',
    'apps.buyurtmalar',
    'apps.kabinet',
    'apps.katalog',
    'apps.narxnoma',
    'apps.joylashuv',
    'apps.sms_app',
    'apps.tolovlar',
    'apps.tushum',
    'apps.xaridlar',
]

MIDDLEWARE = [
    # Matnli javoblarni gzip bilan siqadi — eng ko'p foyda beradigan yagona
    # sozlama. index.html 593 KB dan 119 KB ga tushadi (80% kam). Ro'yxatning
    # ENG BOSHIDA turishi shart: javob tanasini o'qiydigan boshqa
    # middleware'lar undan keyin ishlashi kerak.
    # Nega standart GZipMiddleware emasligi — soargaz/middleware.py ga qarang.
    'soargaz.middleware.MatnGZipMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # Mijoz ilovasi `Accept-Language: ru` yuboradi — javobdagi choice
    # yorliqlari (`xizmat_nomi`, `holat_nomi`, `turi_nomi`) shu tilda
    # qaytadi. CommonMiddleware'dan OLDIN turishi shart.
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # CSP, Permissions-Policy va h.k. — soargaz/middleware.py
    'soargaz.middleware.XavfsizlikSarlavhalariMiddleware',
]

ROOT_URLCONF = 'soargaz.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # soargaz/templates: Django admin shablonlarini (admin/base_site.html) shu yerda o'zgartiramiz
        'DIRS': [BASE_DIR / 'soargaz' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'soargaz.wsgi.application'

# ──────────────────────────────────────────────────────────────
#  MA'LUMOTLAR BAZASI
#
#  DB_NOMI berilsa — PostgreSQL (serverda SHART). Berilmasa — SQLite (faqat
#  o'z kompyuteringizda). SQLite bir vaqtda bitta yozuvchini qabul qiladi:
#  60 ta parallel buyurtmada deyarli hammasi "database is locked" (500) berdi.
#    Serverda: DB_NOMI, DB_FOYDALANUVCHI, DB_PAROL  (+ ixtiyoriy DB_HOST, DB_PORT)
# ──────────────────────────────────────────────────────────────
if os.environ.get('DB_NOMI'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['DB_NOMI'],
            'USER': os.environ['DB_FOYDALANUVCHI'],
            'PASSWORD': os.environ['DB_PAROL'],
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            # Har so'rovda yangi ulanish ochmaslik uchun
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    if not DEBUG:
        import warnings
        warnings.warn(
            "DB_NOMI berilmagan — SQLite ishlatilmoqda. Jonli serverda PostgreSQL "
            "kerak (SQLite ko'p yozuvda qulflanadi).", RuntimeWarning)

AUTH_USER_MODEL = 'auth_app.Foydalanuvchi'

# ──────────────────────────────────────────────────────────────
#  KESH
#
#  REDIS_URL berilsa — umumiy (barcha gunicorn worker'lari uchun bitta)
#  kesh ishlatiladi. Berilmasa LocMemCache qoladi: u har workerda ALOHIDA
#  bo'lgani uchun hisobot keshlash uchun yaramaydi — bir mijoz eski,
#  boshqasi yangi raqamni ko'rib qolishi mumkin.
#
#  Shu sababli hisobot keshi REDIS_URL ga bog'langan (pastda) — OTP
#  cheklovlari esa LocMemCache'da ham ishlayveradi (ular bir workerda
#  ham foydali himoya beradi).
#    Serverda: REDIS_URL=redis://127.0.0.1:6379/1
# ──────────────────────────────────────────────────────────────
REDIS_URL = os.environ.get('REDIS_URL', '')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': 'soargaz',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'soargaz-locmem',
        }
    }

# Hisobot/statistika javoblari necha soniya keshlanadi.
# 0 — keshlash o'chirilgan. Umumiy kesh bo'lmasa avtomatik 0 bo'ladi.
STATISTIKA_KESH_SONIYA = int(os.environ.get('STATISTIKA_KESH_SONIYA', '300')) if REDIS_URL else 0

if not DEBUG and not REDIS_URL:
    import warnings
    warnings.warn(
        "REDIS_URL berilmagan — hisobot keshi o'chirilgan holda ishlaydi. "
        "Ko'p worker'li serverda REDIS_URL o'rnating.", RuntimeWarning)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # Oddiy JWT + egasining «ko'rish» tokenlari (faqat o'qish): apps/auth_app/korish.py
        'apps.auth_app.korish.KorishJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # IP bo'yicha cheklovlar (apps/auth_app/throttles.py) mijoz IP sini
    # `X-Forwarded-For` dan oladi. nginx orqasida aynan 1 ta proksi bor —
    # shu raqam bo'lmasa hujumchi sarlavhani soxtalashtirib cheklovdan
    # o'tib ketadi. Proksisiz (dev) ishlaganda 0: faqat REMOTE_ADDR.
    # Boshqa tuzilma (masalan Cloudflare + nginx) bo'lsa: DJANGO_PROXIES=2
    'NUM_PROXIES': int(os.environ.get('DJANGO_PROXIES', '0' if DEBUG else '1')),
}

SIMPLE_JWT = {
    # Access token QISQA: o'g'irlansa ham 30 daqiqadan keyin foydasiz.
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.environ.get('JWT_ACCESS_DAQIQA', '30'))),
    # Mijozdan SMS kod FAQAT BIR MARTA so'raladi: sessiya refresh token bilan jimgina
    # yangilanadi. Refresh brauzerda `httpOnly` cookie'da turadi (JavaScript uni
    # o'qiy olmaydi, XSS o'g'irlay olmaydi) va har ishlatilganda yangilanadi (ROTATE),
    # ya'ni faol mijoz uchun muddat har safar 90 kunga uzayadi. Xodimlar uchun
    # alohida, qisqaroq muddat (auth_app.views.XODIM_REFRESH_KUN).
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.environ.get('JWT_REFRESH_KUN', '90'))),
    'ROTATE_REFRESH_TOKENS': True,
    # Rotatsiyadan keyin ESKI refresh token yaroqsiz bo'ladi. Aks holda rotatsiya
    # hech narsani himoya qilmaydi: o'g'irlangan token uzoq ishlayveradi.
    # (Muddati o'tgan yozuvlarni tozalash: `manage.py flushexpiredtokens`, haftada 1 marta.)
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
# Productionda faqat o'z domenlaringiz:  DJANGO_CORS=https://soargaz.uz
CORS_ALLOWED_ORIGINS = [o for o in os.environ.get('DJANGO_CORS', '').split(',') if o]

# ──────────────────────────────────────────────────────────────
#  XAVFSIZ TRANZAKSIYA (HTTPS / SSL)
#
#  Karta ma'lumotlari hech qachon bu serverga kelmaydi — mijoz Click yoki
#  Payme checkout sahifasiga o'tadi va 3-D Secure (bank OTP) tasdiqlashini
#  o'sha yerda o'taydi. Ya'ni 3D-Secure provayder tomonidan ta'minlanadi,
#  PCI DSS talablari ham ularning zimmasida.
#
#  Bizning vazifamiz — saytning o'zi HTTPS orqali ishlashi va cookie'lar
#  himoyalanishi. Quyidagilar DEBUG=False bo'lganda avtomatik yoqiladi.
#  DIQQAT: SECURE_SSL_REDIRECT yoqilishidan oldin serverda haqiqiy TLS
#  sertifikati (masalan Let's Encrypt) o'rnatilgan bo'lishi shart.
# ──────────────────────────────────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = True          # http → https
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # nginx orqasida
    SESSION_COOKIE_SECURE = True        # cookie faqat HTTPS orqali
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False        # JS o'qishi kerak bo'lsa
    SECURE_HSTS_SECONDS = 31536000      # 1 yil
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'            # clickjacking
    # Webhook manzillari (Click/Payme shu domenga so'rov yuboradi)
    CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get('DJANGO_CORS', '').split(',') if o]

LANGUAGE_CODE = 'uz'
# Ilova qo'llaydigan tillar — lib/l10n/*.arb bilan bir xil ro'yxat.
LANGUAGES = [
    ('uz', "O'zbekcha"),
    ('ru', 'Русский'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ──────────────────────────────────────────────────────────────
#  KIRISH MA'LUMOTLARI HAJMI
#  Standart (2.5 MB) saqlanadi — bu yerda aniq yozilishi sababi: kimdir
#  "yuklash ishlamayapti" deb uni ko'tarib yubormasligi kerak. Katta fayl
#  (hujjat, rasm) uchun nginx `client_max_body_size 32M` allaqachon bor;
#  Django xotiraga olmasdan diskka yozadi.
# ──────────────────────────────────────────────────────────────
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440     # JSON/forma tanasi (fayllarsiz)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200         # forma maydonlari soni (DoS)
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440

# ──────────────────────────────────────────────────────────────
#  PAROL TALABLARI (Django admin va xodim/admin parollari uchun).
#  Ilgari ro'yxat bo'sh edi — "1234" ham qabul qilinardi.
# ──────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# CSRF/sessiya cookie'lari boshqa saytdan yuborilgan so'rovlar bilan
# ketmasin (Lax: oddiy havolalar ishlaydi, lekin cross-site POST ketmaydi).
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

OTP_EXPIRE_MINUTES = 5

# ──────────────────────────────────────────────────────────────
#  OTP CHEKLOVLARI (brute-force va SMS pulini yoqishdan himoya)
# ──────────────────────────────────────────────────────────────
OTP_QAYTA_SONIYA = 60        # Bitta raqamga kod so'rashlar orasidagi eng kam vaqt
OTP_SOATLIK_LIMIT = 5        # Bir raqamga soatiga necha marta kod yuborish mumkin
OTP_URINISH_LIMIT = 5        # Noto'g'ri kod kiritish urinishlari (keyin blok)
OTP_BLOK_DAQIQA = 15         # Limitdan oshgach necha daqiqa kutiladi

# ──────────────────────────────────────────────────────────────
#  SINOV (TEST) KODI — faqat ishlab chiqish (DEBUG=1) uchun
#
#  Haqiqiy SMS provayder ulanmagan paytda mijoz hisobini sinash uchun: ro'yxatdagi
#  raqamlarga SMS yuborilmaydi va tasdiqlash kodi doim bir xil bo'ladi.
#  Format: DJANGO_SINOV_MIJOZ="+998900000002:123456,+998900000003:654321"
#  Qo'shimcha raqam kerak bo'lmasa, standart sinov raqami ishlatiladi.
#
#  XAVFSIZLIK: DEBUG=0 (server) da bu ro'yxat HAR DOIM bo'sh. Serverda o'zgaruvchi
#  berilgan bo'lsa, server ishga tushmaydi — tasodifan qolib ketmasin.
# ──────────────────────────────────────────────────────────────
_SINOV_XOM = os.environ.get('DJANGO_SINOV_MIJOZ', '')
if not DEBUG and _SINOV_XOM:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "DJANGO_SINOV_MIJOZ faqat ishlab chiqishda (DJANGO_DEBUG=1) ruxsat etiladi — "
        "serverda uni .env dan olib tashlang.")
SINOV_MIJOZ = {}
if DEBUG:
    SINOV_MIJOZ = {'+998900000002': '123456'}
    for _juft in filter(None, (x.strip() for x in _SINOV_XOM.split(','))):
        _tel, _, _kod = _juft.partition(':')
        if _tel.strip() and _kod.strip().isdigit() and len(_kod.strip()) == 6:
            SINOV_MIJOZ[_tel.strip()] = _kod.strip()

# ──────────────────────────────────────────────────────────────
#  XODIMLAR JOYLASHUVI (faqat smena davomida, xodim roziligi bilan)
# ──────────────────────────────────────────────────────────────
JOYLASHUV_MIN_SONIYA = 15      # Nuqtalar orasidagi eng kam vaqt (server shundan tezini tashlaydi)
JOYLASHUV_ALOQA_SONIYA = 120   # Shuncha vaqt nuqta kelmasa, xodim "aloqada emas" hisoblanadi
JOYLASHUV_SMENA_MAX_SOAT = 16  # Unutilgan smena shuncha soatdan keyin o'zi yopiladi
JOYLASHUV_SAQLASH_KUN = 30     # Nuqtalar shuncha kundan keyin o'chiriladi (joylashuv_tozala)
JOYLASHUV_YAQIN_DAQIQA = 10    # "Eng yaqin xodim": oxirgi nuqtasi shuncha daqiqadan eski bo'lmagan smenadagilar hisobga olinadi
YAQIN_MAX_VAZIFA = 5           # Eng yaqinga avtomatik yuborishda: faol vazifasi shundan ko'p xodimga yuborilmaydi

# Boshqaruv paneli (rol='admin') kirishi — eng yuqori huquqli nuqta, shuning
# uchun cheklov qattiqroq: bu blok o'zi ochilmaydi. Hisob 'nofaol' bo'lib
# qoladi va uni faqat tizim egasi Django admin panelidan qayta faollashtiradi
# (holat -> faol) hamda yangi parol beradi.
ADMIN_URINISH_LIMIT = 4

# «Uning ko'zi bilan ko'rish» tokeni muddati (daqiqa). Yangilanmaydi: tugagach
# egasi boshqaruv panelidan qaytadan ochadi.
KORISH_DAQIQA = 30

# Boshqaruv paneli sessiyasi. Mijoz tokeni bir yil yashaydi (SIMPLE_JWT),
# admin uchun esa qisqa: ochiq qolgan kompyuter yoki o'g'irlangan token
# uzoq muddat ishlab turmasligi kerak. Panel ham shu vaqtdan keyin
# foydalanuvchini avtomatik chiqaradi.
ADMIN_SESSIYA_DAQIQA = 120

# Boshqaruv paneliga ikki bosqichli kirish: parol + telefonga keladigan SMS kod.
# Parol o'g'irlansa ham telefonsiz kirib bo'lmaydi. O'chirish uchun: DJANGO_ADMIN_2FA=0
ADMIN_2FA = os.environ.get('DJANGO_ADMIN_2FA', '1') == '1'
ADMIN_2FA_DAQIQA = 5         # Kod necha daqiqa amal qiladi
ADMIN_2FA_URINISH = 3        # Kodni necha marta xato kiritish mumkin

# ──────────────────────────────────────────────────────────────
#  SMS SHLYUZI
#  Serverda: SMS_PROVAYDER=eskiz, ESKIZ_EMAIL, ESKIZ_PAROL, ESKIZ_FROM
#  Sozlanmasa — kodlar faqat log'ga chiqadi (dev rejim).
# ──────────────────────────────────────────────────────────────
# Mijozga SMS bilan boradigan hujjat havolalari (kvitansiya, shartnoma) shu manzildan boshlanadi.
# Serverda ALBATTA o'z domeningiz: DJANGO_SAYT_MANZIL=https://soargaz.uz
SAYT_MANZIL = os.environ.get('DJANGO_SAYT_MANZIL', 'http://localhost:8001')

SMS_PROVAYDER = os.environ.get('SMS_PROVAYDER', 'konsol')
ESKIZ_EMAIL = os.environ.get('ESKIZ_EMAIL', '')
ESKIZ_PAROL = os.environ.get('ESKIZ_PAROL', '')
ESKIZ_FROM = os.environ.get('ESKIZ_FROM', '4546')

# ──────────────────────────────────────────────────────────────
#  TO'LOV TIZIMLARI (Click / Payme)
#  Kalitlar merchant kabinetdan olinadi va SERVERDA muhit o'zgaruvchisi
#  sifatida beriladi — kodda hech qachon saqlanmaydi (SECRET_KEY kabi).
#  Kalitlar bo'sh bo'lsa — havolalar quriladi, lekin webhook "sozlanmagan" deydi.
# ──────────────────────────────────────────────────────────────
CLICK_SERVICE_ID = os.environ.get('CLICK_SERVICE_ID', '')
CLICK_MERCHANT_ID = os.environ.get('CLICK_MERCHANT_ID', '')
CLICK_SECRET_KEY = os.environ.get('CLICK_SECRET_KEY', '')

PAYME_MERCHANT_ID = os.environ.get('PAYME_MERCHANT_ID', '')
PAYME_KEY = os.environ.get('PAYME_KEY', '')

# To'lovdan keyin foydalanuvchi qaytadigan havola.
# DIQQAT: bu manzil Click/Payme sahifasidan mijozni qaytaradi — production'da
# haqiqiy domen bo'lishi SHART, aks holda mijoz to'lovdan keyin localhost'ga
# tushib qoladi va tasdiqni ko'rmaydi.
#   Serverda: TOLOV_RETURN_URL=https://soargaz.uz/
TOLOV_RETURN_URL = os.environ.get('TOLOV_RETURN_URL', 'http://localhost:8001/')

# Productionda localhost qolib ketishi — jimgina buziladigan xato.
# Server ishga tushayotganda darrov ogohlantiramiz.
if not DEBUG and 'localhost' in TOLOV_RETURN_URL:
    import warnings
    warnings.warn(
        "TOLOV_RETURN_URL hali 'localhost' — mijoz to'lovdan keyin sizning "
        "saytingizga qayta olmaydi. Serverda TOLOV_RETURN_URL o'zgaruvchisini "
        "haqiqiy domenga qo'ying.", RuntimeWarning)

# ──────────────────────────────────────────────────────────────
#  XARIDLAR — narx qoidalari (so'mda).
#  index.html dagi XARID_NARX obyekti bilan bir xil bo'lishi shart.
# ──────────────────────────────────────────────────────────────
ORNATISH_NARXI = 250000            # O'rnatish xizmati
YETKAZISH_NARXI = 30000            # Hududi ko'rsatilmagan buyurtma uchun standart narx
BEPUL_YETKAZISH_CHEGARASI = 1000000  # Shu summadan oshsa yetkazish bepul (0 — o'chirilgan)

# ──────────────────────────────────────────────────────────────
#  Hudud bo'yicha yetkazib berish narxi va muddati
#  narx — so'm, muddat — soatda (mijozga "1 kun ichida" deb ko'rsatiladi)
#  Tumanlar ro'yxati apps.auth_app.models.TUMANLAR bilan mos.
# ──────────────────────────────────────────────────────────────
YETKAZISH_HUDUDLAR = {
    'Buxoro shahri':       {'narx': 20000, 'soat': 4},
    'Kogon shahri':        {'narx': 30000, 'soat': 8},
    'Buxoro tumani':       {'narx': 30000, 'soat': 8},
    'Jondor tumani':       {'narx': 40000, 'soat': 24},
    'Vobkent tumani':      {'narx': 40000, 'soat': 24},
    'Romitan tumani':      {'narx': 40000, 'soat': 24},
    'Shofirkon tumani':    {'narx': 45000, 'soat': 24},
    'Peshku tumani':       {'narx': 45000, 'soat': 24},
    "G'ijduvon tumani":    {'narx': 50000, 'soat': 48},
    'Qorakol tumani':      {'narx': 60000, 'soat': 48},
    'Qorovulbozor tumani': {'narx': 60000, 'soat': 48},
}

# Filialdan olib ketish: manzil va necha soatda tayyor bo'lishi
FILIAL_MANZILI = "Buxoro sh., Alpomish ko'chasi 12"
FILIAL_TAYYOR_SOAT = 3

# Yetkazib berishda muammo: necha marta urinib ko'riladi
YETKAZISH_URINISHLAR = 3

# Uzcard/Humo kartalari qaysi provayder checkouti orqali qabul qilinadi.
# Click ham, Payme ham Uzcard va Humo'ni qo'llab-quvvatlaydi.
KARTA_PROVAYDER = 'click'          # 'click' yoki 'payme'

# Bo'lib to'lash: {oylar soni: ustama foizi}. Ustama 0 bo'lsa — foizsiz.
# Buyurtma operator tomonidan tasdiqlanadi, shartnoma rasmiylashtiriladi.
BOLIB_TOLASH = {3: 0, 6: 10, 12: 20}
BOLIB_ENG_KAM_SUMMA = 1000000      # Shu summadan past buyurtmaga bo'lib to'lash berilmaydi

# Manzil -> xarita koordinatasi (operator arizada manzil yozganda xarita o'zi joyni topadi).
# OpenStreetMap Nominatim: faqat MANZIL matni yuboriladi (mijoz ismi/telefoni yuborilmaydi), natijalar keshlanadi.
GEOKOD_URL = os.environ.get('GEOKOD_URL', 'https://nominatim.openstreetmap.org/search')
GEOKOD_USER_AGENT = os.environ.get('GEOKOD_USER_AGENT', f'SoarGaz/1.0 ({SAYT_MANZIL})')
GEOKOD_STANDART_HUDUD = "Buxoro viloyati"     # tuman/shaharda viloyat ko'rsatilmasa qidiruvga qo'shiladi
GEOKOD_TIMEOUT = 6
