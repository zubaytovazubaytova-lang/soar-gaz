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

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'apps.auth_app',
    'apps.buyurtmalar',
    'apps.kabinet',
    'apps.katalog',
    'apps.sms_app',
    'apps.tolovlar',
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
]

ROOT_URLCONF = 'soargaz.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

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
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    # Mijozdan SMS kod FAQAT BIR MARTA so'raladi. Sessiya ilova o'chirilmaguncha
    # (localStorage tozalanmaguncha) davom etishi kerak, shuning uchun refresh
    # muddati bir yil va har ishlatilganda yangilanadi (ROTATE). Ya'ni ilovadan
    # yiliga bir marta foydalansa ham, kod qaytadan so'ralmaydi.
    'REFRESH_TOKEN_LIFETIME': timedelta(days=365),
    'ROTATE_REFRESH_TOKENS': True,
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

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

OTP_EXPIRE_MINUTES = 5

# ──────────────────────────────────────────────────────────────
#  OTP CHEKLOVLARI (brute-force va SMS pulini yoqishdan himoya)
# ──────────────────────────────────────────────────────────────
OTP_QAYTA_SONIYA = 60        # Bitta raqamga kod so'rashlar orasidagi eng kam vaqt
OTP_SOATLIK_LIMIT = 5        # Bir raqamga soatiga necha marta kod yuborish mumkin
OTP_URINISH_LIMIT = 5        # Noto'g'ri kod kiritish urinishlari (keyin blok)
OTP_BLOK_DAQIQA = 15         # Limitdan oshgach necha daqiqa kutiladi

# Boshqaruv paneli (rol='admin') kirishi — eng yuqori huquqli nuqta, shuning
# uchun cheklov qattiqroq: bu blok o'zi ochilmaydi. Hisob 'nofaol' bo'lib
# qoladi va uni faqat tizim egasi Django admin panelidan qayta faollashtiradi
# (holat -> faol) hamda yangi parol beradi.
ADMIN_URINISH_LIMIT = 4

# Boshqaruv paneli sessiyasi. Mijoz tokeni bir yil yashaydi (SIMPLE_JWT),
# admin uchun esa qisqa: ochiq qolgan kompyuter yoki o'g'irlangan token
# uzoq muddat ishlab turmasligi kerak. Panel ham shu vaqtdan keyin
# foydalanuvchini avtomatik chiqaradi.
ADMIN_SESSIYA_DAQIQA = 30

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
