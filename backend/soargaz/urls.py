from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import (JsonResponse, FileResponse, Http404,
                         HttpResponse, HttpResponseNotModified)
from django.utils.http import http_date
from django.views.static import serve
import os
import re

ILDIZ = settings.BASE_DIR.parent


def _sahifa(fayl_nomi, content_type='text/html; charset=utf-8'):
    """Loyiha ildizidagi faylni shartli keshlash bilan beradi.

    Ilgari bu yerda `no-store` turardi — ya'ni index.html (600 KB dan ortiq)
    HAR ochilishda to'liq qaytadan yuklanardi. Mobil internetda bu eng qimmat
    joy edi. Endi Last-Modified yuboriladi: brauzer faylni keshlaydi va har
    safar faqat "o'zgardimi?" deb so'raydi. O'zgarmagan bo'lsa 304 (bo'sh
    javob) qaytadi — trafik nolga teng, lekin foydalanuvchi baribir eng
    yangi versiyani ko'radi.
    """
    def view(request):
        yol = os.path.join(ILDIZ, fayl_nomi)
        try:
            stat = os.stat(yol)
        except OSError:
            raise Http404(fayl_nomi)

        # Brauzerdagi nusxa hali ham dolzarbmi?
        ims = request.META.get('HTTP_IF_MODIFIED_SINCE')
        if ims and ims == http_date(stat.st_mtime):
            javob = HttpResponseNotModified()
            javob['Cache-Control'] = 'no-cache'
            return javob

        resp = FileResponse(open(yol, 'rb'), content_type=content_type)
        # `no-cache` = keshla, lekin ishlatishdan oldin serverdan so'ra.
        # (`no-store` dan farqi: bu keshlashni TAQIQLAMAYDI, faqat tekshirtiradi.)
        resp['Cache-Control'] = 'no-cache'
        resp['Last-Modified'] = http_date(stat.st_mtime)
        return resp
    return view


asosiy_sahifa = _sahifa('index.html')


def _yopiq_sahifa(fayl_nomi):
    """Boshqaruv/xodim sahifalari — qidiruv tizimlaridan yopiq.

    `X-Robots-Tag` sarlavhasi HTML ichidagi <meta> dan ishonchliroq: u
    faylni o'zgartirishni talab qilmaydi va robot HTML ni umuman
    o'qimasdan turib ham ko'radi. DIQQAT: bu yashirish, himoya emas —
    haqiqiy himoya login va rol tekshiruvi.
    """
    ichki = _sahifa(fayl_nomi)

    def view(request):
        javob = ichki(request)
        javob['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        # Panel sahifasi oraliq keshlarda (proxy) saqlanib qolmasin
        javob['Cache-Control'] = 'no-cache, private'
        return javob
    return view


def robots_txt(request):
    """Qidiruv robotlariga: ichki bo'limlarni indekslamang."""
    matn = (
        "User-agent: *\n"
        "Disallow: /boshqaruv/\n"
        "Disallow: /admin.html\n"
        "Disallow: /admin/\n"
        "Disallow: /xodimlar/\n"
        "Disallow: /xodimlar.html\n"
        "Disallow: /kabinet/\n"
        "Disallow: /api/\n"
        "Allow: /\n"
    )
    return HttpResponse(matn, content_type='text/plain; charset=utf-8')


def statik_fayl(request, path, papka):
    """assets/ va vendor/ — o'zgarmas resurslar, uzoq muddat keshlanadi.

    Tailwind CSS, Inter shrifti, Font Awesome, Leaflet. Bular faqat
    deploy paytida o'zgaradi, shuning uchun bir yil keshlanadi — mijoz
    ikkinchi marta kirganda ularni umuman yuklab olmaydi.
    Fayl yangilangach nomiga versiya qo'shish kerak (masalan tailwind.css?v=2).
    """
    javob = serve(request, path, document_root=os.path.join(ILDIZ, papka))
    javob['Cache-Control'] = 'public, max-age=31536000, immutable'
    return javob


def sayt_fayli(request, path, papka):
    """scripts/ va video/ — sayt bilan birga o'zgaradigan fayllar.

    `statik_fayl` dan farqi — kesh muddati qisqa. Bu fayllar nomida versiya
    yo'q (`scripts/hero-carousel.js`), shuning uchun bir yillik kesh berilsa
    o'zgarish mijozga umuman yetib bormasdi.
    """
    javob = serve(request, path, document_root=os.path.join(ILDIZ, papka))
    javob['Cache-Control'] = 'public, max-age=3600'
    return javob


def rasm_bilan_webp(request, path):
    """Mahsulot rasmlarini beradi; brauzer qo'llasa — WebP nusxasini.

    HTML da rasm nomlari `.jpg`/`.png` bo'lib qolaveradi (ular index.html
    ichidagi JS ma'lumot ro'yxatlarida yozilgan). Bu yerda esa brauzer
    `Accept: image/webp` deb aytsa va yonida `.webp` nusxa turgan bo'lsa —
    o'shani beramiz. Natijada mobil qurilma ~2 barobar kam trafik yuklaydi,
    eski brauzerlar esa aslini oladi.  WebP fayllar `npm run rasm` bilan
    yaratiladi.

    `Vary: Accept` — kesh bir foydalanuvchiga berilgan WebP ni WebP
    qo'llamaydigan boshqasiga bermasligi uchun shart.
    """
    tanlangan = path
    if path.lower().endswith(('.jpg', '.jpeg', '.png')):
        if 'image/webp' in request.META.get('HTTP_ACCEPT', ''):
            nomzod = re.sub(r'\.(jpe?g|png)$', '.webp', path, flags=re.I)
            if os.path.exists(os.path.join(ILDIZ, nomzod)):
                tanlangan = nomzod

    javob = serve(request, tanlangan, document_root=ILDIZ)
    if tanlangan.endswith('.webp'):
        # Windows'da .webp mime turi ro'yxatdan o'tmagan bo'lishi mumkin —
        # u holda Django `application/octet-stream` qaytaradi va brauzer
        # rasmni ko'rsatish o'rniga yuklab olishga urinadi.
        javob['Content-Type'] = 'image/webp'
    javob['Vary'] = 'Accept'
    # Mahsulot rasmlari kamdan-kam o'zgaradi
    javob['Cache-Control'] = 'public, max-age=2592000'
    return javob


LOYIHA_RASMLARI = {'logo', 'logo_icon'}


def loyiha_rasmi(request, nomi):
    if nomi not in LOYIHA_RASMLARI:
        raise Http404
    rasm_yoli = os.path.join(ILDIZ, f'{nomi}.png')
    resp = FileResponse(open(rasm_yoli, 'rb'), content_type='image/png')
    resp['Cache-Control'] = 'public, max-age=604800'
    return resp


def api_root(request):
    return JsonResponse({
        'status': 'ok',
        'loyiha': 'SOAR GAZ Backend',
        'endpointlar': {
            'admin_login':     '/api/auth/admin/login/',
            'otp_yuborish':    '/api/auth/otp/yuborish/',
            'otp_tasdiqlash':  '/api/auth/otp/tasdiqlash/',
            'token_yangilash': '/api/auth/token/yangilash/',
            'profil':          '/api/auth/profil/',
            'xodimlar':        '/api/auth/xodimlar/',
            'buyurtmalar':     '/api/buyurtmalar/',
            'kabinet_obzor':   '/api/kabinet/obzor/',
            'kabinet_obyekt':  '/api/kabinet/obyektlar/',
            'kabinet_hisoblagich': '/api/kabinet/hisoblagichlar/',
            'katalog_narxlar': '/api/katalog/narxlar/',
            'katalog_media':   '/api/katalog/media/',
            'statistika':      '/api/buyurtmalar/statistika/',
            'sms':             '/api/sms/',
            'tolov_sorov':     '/api/tolovlar/sorov/',
            'tolovlar':        '/api/tolovlar/',
            'xaridlar':        '/api/xaridlar/',
            'xarid_statistika': '/api/xaridlar/statistika/',
        },
        'admin_panel': '/admin/',
    })


urlpatterns = [
    path('', asosiy_sahifa),
    # Mijoz kabineti va xodimlar portali — alohida sahifalar
    path('kabinet/', _sahifa('kabinet.html')),
    path('kabinet.html', _sahifa('kabinet.html')),
    path('xodimlar/', _sahifa('xodimlar.html')),
    path('xodimlar.html', _sahifa('xodimlar.html')),
    # Admin boshqaruv paneli. Diqqat: '/admin/' Django'ning o'z paneli —
    # shuning uchun bu sahifa '/boshqaruv/' manzilida turadi.
    path('boshqaruv/', _yopiq_sahifa('admin.html')),
    path('admin.html', _yopiq_sahifa('admin.html')),
    path('robots.txt', robots_txt),
    # PWA — telefon ekraniga qo'shish va offline rejim.
    # sw.js AYNAN ildizdan berilishi shart: service worker faqat o'zi
    # turgan katalog va undan pastdagi manzillarni boshqara oladi.
    path('manifest.webmanifest', _sahifa('manifest.webmanifest',
                                         'application/manifest+json')),
    path('sw.js', _sahifa('sw.js', 'application/javascript; charset=utf-8')),
    path('offline.html', _sahifa('offline.html')),
    path('<str:nomi>.png', loyiha_rasmi),
    path('api/', api_root),
    path('admin/', admin.site.urls),
    # Lokal uslub/shrift/kutubxona fayllari (ilgari tashqi CDN'lardan olinardi)
    re_path(r'^assets/(?P<path>.+)$', statik_fayl, {'papka': 'assets'}),
    re_path(r'^vendor/(?P<path>.+)$', statik_fayl, {'papka': 'vendor'}),
    # Sayt skriptlari va hero videosi (index.html yonidagi scripts/ va video/)
    re_path(r'^scripts/(?P<path>.+)$', sayt_fayli, {'papka': 'scripts'}),
    re_path(r'^video/(?P<path>.+)$', sayt_fayli, {'papka': 'video'}),
    # index.html yonidagi mahsulot rasmlari va videolari (loyiha ildizidagi images/).
    # Diqqat: sertifikat/pasport fayllari bu yerda EMAS — ular hujjatlar_maxfiy/ da
    # turadi va faqat /api/katalog/hujjat/<token>/ orqali beriladi.
    re_path(r'^(?P<path>images/.+)$', rasm_bilan_webp),
    path('api/auth/', include('apps.auth_app.urls')),
    path('api/buyurtmalar/', include('apps.buyurtmalar.urls')),
    path('api/kabinet/', include('apps.kabinet.urls')),
    path('api/katalog/', include('apps.katalog.urls')),
    path('api/sms/', include('apps.sms_app.urls')),
    path('api/tolovlar/', include('apps.tolovlar.urls')),
    path('api/xaridlar/', include('apps.xaridlar.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
