import io
from datetime import datetime

from django.core import signing
from django.http import FileResponse, HttpResponse, HttpResponseForbidden, HttpResponseGone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import KatalogHujjat, KatalogMedia, KatalogNarx

# Imzolangan havola necha soniya amal qiladi (5 daqiqa)
HAVOLA_MUDDATI = 300
IMZO_TUZI = 'katalog-hujjat'


# ──────────────────────────────────────────────────────────────
#  GET /api/katalog/narxlar/  — index.html katalogi uchun narxlar (ochiq)
#  Javob: {"gorelka-bloki-emmeti-650": {"narx": 850000, "matn": "850 000 so'm",
#                                       "birlik": "to'plam"}, ...}
# ──────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def narxlar(request):
    natija = {}
    for n in KatalogNarx.objects.filter(faol=True):
        natija[n.kalit] = {
            'narx': n.narx,
            'matn': n.narx_matni(),
            'birlik': n.birlik,
            'kategoriya': n.kategoriya,
        }
    return Response(natija)


# ──────────────────────────────────────────────────────────────
#  GET /api/katalog/hujjatlar/<kalit>/  — mahsulot hujjatlari ro'yxati
#
#  Fayl manzili o'rniga har safar YANGI imzolangan havola beriladi.
#  Havola 5 daqiqadan keyin ishlamay qoladi, shuning uchun uni
#  boshqalarga uzatish yoki xatcho'pga saqlash foydasiz.
# ──────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def hujjatlar(request, kalit):
    royxat = []
    for h in KatalogHujjat.objects.filter(kalit=kalit, faol=True):
        token = signing.dumps({'id': h.id}, salt=IMZO_TUZI)
        royxat.append({
            'tur': h.tur,
            'nom': h.nom,
            'rasm': h.rasmmi,
            'havola': f'/api/katalog/hujjat/{token}/',
            'muddat': HAVOLA_MUDDATI,
        })
    return Response(royxat)


# ──────────────────────────────────────────────────────────────
#  GET /api/katalog/media/  — admin panelda yuklangan rasm va videolar
#
#  Javob: {"ugop-16-gorelka": {"bolim": "gorelka",
#                              "rasm": ["images/jihozlar/ugop-16-1.jpg",
#                                       "images/jihozlar/ugop-16-video.mp4"]}, ...}
#
#  Tartib: avval rasmlar (tartib raqami bo'yicha), video har doim oxirida —
#  index.html dagi grid kartasi massivning birinchi elementini oladi.
# ──────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def media(request):
    guruhlar = {}
    for m in KatalogMedia.objects.filter(faol=True):
        guruhlar.setdefault(m.kalit, []).append(m)

    natija = {}
    for kalit, ro in guruhlar.items():
        ro.sort(key=lambda m: m.tartib_kaliti())
        natija[kalit] = {
            'bolim': ro[0].bolim,
            'rasm': [m.yol for m in ro],
        }
    return Response(natija)


def _mijoz_ip(request):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return ip.split(',')[0].strip() if ip else request.META.get('REMOTE_ADDR', '—')


def _suv_belgili_rasm(hujjat, izoh):
    """Rasmga qiya takrorlanuvchi suv belgisini singdiradi (Pillow)."""
    from PIL import Image, ImageDraw, ImageFont

    hujjat.fayl.open('rb')
    try:
        asl = Image.open(hujjat.fayl).convert('RGBA')
    finally:
        hujjat.fayl.close()

    qatlam = Image.new('RGBA', asl.size, (255, 255, 255, 0))
    chizgich = ImageDraw.Draw(qatlam)

    olcham = max(16, asl.width // 38)
    try:
        shrift = ImageFont.truetype('arialbd.ttf', olcham)
    except OSError:
        shrift = ImageFont.load_default()

    matn = f"SOAR GAZ · faqat ko'rish uchun · {izoh}"
    qadam_y = olcham * 5
    qadam_x = olcham * 26

    y = -asl.height
    while y < asl.height * 2:
        x = -asl.width
        while x < asl.width * 2:
            chizgich.text((x, y), matn, font=shrift, fill=(31, 72, 135, 46))
            x += qadam_x
        y += qadam_y

    qatlam = qatlam.rotate(30, resample=Image.BICUBIC, center=(asl.width // 2, asl.height // 2))
    natija = Image.alpha_composite(asl, qatlam).convert('RGB')

    bufer = io.BytesIO()
    natija.save(bufer, format='JPEG', quality=82)
    bufer.seek(0)
    return bufer


# ──────────────────────────────────────────────────────────────
#  GET /api/katalog/hujjat/<token>/  — hujjatni ko'rsatish
#
#  • token imzolangan va 5 daqiqalik — eskirsa 410 qaytadi
#  • rasm bo'lsa, serverda suv belgisi singdiriladi (sana + IP)
#  • javob keshlanmaydi, «inline» — brauzer uni yuklab olmaydi
# ──────────────────────────────────────────────────────────────
def hujjat_ochish(request, token):
    try:
        malumot = signing.loads(token, salt=IMZO_TUZI, max_age=HAVOLA_MUDDATI)
    except signing.SignatureExpired:
        return HttpResponseGone("Havola muddati tugagan. Sahifani yangilang.")
    except signing.BadSignature:
        return HttpResponseForbidden("Havola yaroqsiz.")

    try:
        hujjat = KatalogHujjat.objects.get(id=malumot['id'], faol=True)
    except KatalogHujjat.DoesNotExist:
        return HttpResponseForbidden("Hujjat topilmadi.")

    izoh = f"{datetime.now():%d.%m.%Y %H:%M} · {_mijoz_ip(request)}"

    if hujjat.rasmmi:
        javob = HttpResponse(_suv_belgili_rasm(hujjat, izoh).read(), content_type='image/jpeg')
    else:
        javob = FileResponse(hujjat.fayl.open('rb'), content_type='application/pdf')

    javob['Content-Disposition'] = 'inline'
    javob['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
    javob['Pragma'] = 'no-cache'
    javob['X-Robots-Tag'] = 'noindex, nofollow, noarchive, noimageindex'
    return javob
