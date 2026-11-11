"""Loyihaga xos middleware'lar."""
from django.middleware.gzip import GZipMiddleware

# Faqat shu turlar siqiladi. Qolgani (rasm, video, shrift, arxiv) allaqachon
# siqilgan — ularni gzip qilish hajmni kamaytirmaydi, aksincha zarar keltiradi.
SIQILADIGAN = (
    'text/',
    'application/javascript',
    'application/json',
    'application/manifest+json',
    'application/xml',
    'image/svg+xml',
)


class MatnGZipMiddleware(GZipMiddleware):
    """Gzip'ni faqat matnli javoblarga qo'llaydi.

    Django'ning standart GZipMiddleware'i OQIMLI javoblarda (FileResponse —
    bu loyihada barcha sahifalar va statik fayllar shunday beriladi) "siqilgani
    kattaroq bo'lsa, tashla" tekshiruvini o'tkazib yuboradi va `Content-Length`
    sarlavhasini o'chiradi. Natijada:

      * .mp4 / .woff2 / .png bekorga qayta siqiladi (672 KB video -> 670 KB,
        ya'ni foyda deyarli nol, protsessor esa har so'rovda sarflanadi);
      * Content-Length yo'qolgani uchun brauzer videoni oldinga sura olmaydi
        (Range so'rovlari ishlamay qoladi);
      * 206 (qisman) javob siqilsa, umuman buziladi.

    Shuning uchun turini tekshirib, faqat matnga ruxsat beramiz.
    """

    def process_response(self, request, response):
        # Qisman javob (Range) hech qachon siqilmasin
        if response.status_code == 206:
            return response

        tur = response.headers.get('Content-Type', '').split(';')[0].strip()
        if not tur.startswith(SIQILADIGAN):
            return response

        return super().process_response(request, response)


# ──────────────────────────────────────────────────────────────
#  XAVFSIZLIK SARLAVHALARI
# ──────────────────────────────────────────────────────────────
import os  # noqa: E402
import secrets  # noqa: E402

from django.conf import settings  # noqa: E402

# Sayt to'liq lokal: Tailwind, shrift, Font Awesome, Leaflet — hammasi o'z
# domenidan. Tashqi manbalar faqat ikkita:
#   * OpenStreetMap — kuryer xaritasi plitkalari (img-src)
#   * Click / Payme — to'lov sahifasiga o'tish (form-action)
# script-src da 'unsafe-inline' YO'Q: sahifalardagi skriptlar tashqi fayllarda
# (scripts/*.js), hodisa handlerlari esa onclick="..." emas, `data-h-*` belgisi
# + scripts/hodisa-boshqaruvchi.js orqali ishlaydi. Django shablonlaridagi
# (admin, kvitansiya, xarita) inline <script> lar har so'rovga yangi `nonce`
# oladi:  <script nonce="{{ request.csp_nonce }}">.
# style-src da 'unsafe-inline' qoldi: ~1000 ta style="..." bor, XSS xavfi esa
# asosan skriptlardan keladi.
# CSP quyidagilarni to'sadi: begona/inline skript, <object>/<embed>, <base>
# orqali havolalarni o'g'irlash, saytni boshqa saytga <iframe> qilish,
# ma'lumotni begona domenga yuborish (connect-src).
CSP_MANBALAR = {
    'default-src': "'self'",
    'script-src': "'self'",          # + 'nonce-...' (har so'rovda, _csp_qiymati)
    'style-src': "'self' 'unsafe-inline'",
    'img-src': "'self' data: blob: https://*.tile.openstreetmap.org",
    'font-src': "'self' data:",
    'connect-src': "'self'",
    'media-src': "'self' blob:",
    'frame-src': "'self' blob:",
    'worker-src': "'self'",
    'manifest-src': "'self'",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self' https://my.click.uz https://checkout.paycom.uz",
    'frame-ancestors': "'none'",
}


def _csp_qiymati(nonce=''):
    manbalar = dict(CSP_MANBALAR)
    if nonce:
        manbalar['script-src'] += f" 'nonce-{nonce}'"
    qismlar = [f'{nom} {qiymat}' for nom, qiymat in manbalar.items()]
    if not settings.DEBUG:
        # http:// resurslarni avtomatik https:// ga o'tkazadi (aralash kontent yo'q)
        qismlar.append('upgrade-insecure-requests')
    return '; '.join(qismlar)


class XavfsizlikSarlavhalariMiddleware:
    """Har javobga qo'shimcha himoya sarlavhalarini qo'yadi.

    `DJANGO_CSP=report-only` — CSP ni faqat kuzatish rejimida yuboradi
    (bloklamaydi). Yangi funksiya qo'shilganda nimadir to'silib qolsa,
    avval shu rejimda brauzer konsolidan ko'rib, so'ng to'g'rilash mumkin.
    `DJANGO_CSP=0` — butunlay o'chiradi (faqat favqulodda holat uchun).

    Django admin (/admin/) o'z CSP si bilan ham ishlaydi: u faqat o'z
    skriptlarini yuklaydi, 'unsafe-inline' uni buzmaydi.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        rejim = os.environ.get('DJANGO_CSP', '1').lower()
        self.csp_yoqilgan = rejim != '0'
        self.csp_sarlavha = ('Content-Security-Policy-Report-Only'
                             if rejim == 'report-only'
                             else 'Content-Security-Policy')

    def __call__(self, request):
        # Shablonlar `{{ request.csp_nonce }}` orqali oladi
        request.csp_nonce = secrets.token_urlsafe(16)
        javob = self.get_response(request)

        if self.csp_yoqilgan:
            javob.setdefault(self.csp_sarlavha, _csp_qiymati(request.csp_nonce))

        # Brauzer imkoniyatlari: geolokatsiya faqat o'z saytimizda (kuryer
        # kuzatuvi va manzil aniqlash uchun kerak); kamera/mikrofon/to'lov API
        # va boshqalar butunlay yopiq.
        javob.setdefault(
            'Permissions-Policy',
            'geolocation=(self), camera=(), microphone=(), payment=(), '
            'usb=(), serial=(), bluetooth=(), accelerometer=(), gyroscope=()')
        # Boshqa saytlar bizning resurslarimizni o'z sahifasiga tortib ololmasin
        javob.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        javob.setdefault('X-Permitted-Cross-Domain-Policies', 'none')

        # API javoblari (profil, buyurtma, to'lov) oraliq keshlarda
        # (proksi, brauzer "orqaga" tugmasi) saqlanib qolmasin.
        if request.path.startswith('/api/'):
            javob.setdefault('Cache-Control', 'no-store')
        return javob
