"""Do'kon mahsulotlarining YAGONA ishonchli manbai (server tomonda).

Narx, nom va rasm HECH QACHON mijoz (brauzer) yuborgan qiymatdan olinmaydi:
mijozdan faqat `productId` va `qty` qabul qilinadi, qolganini shu modul
katalogdan topadi. Aks holda F12 orqali narxni 1 so'mga o'zgartirib buyurtma
berish mumkin bo'lardi.

Ikki manba bor:
  * do'kon katalogi — `apps/xaridlar/data/products.json`, mijoz `productId` yuboradi;
  * marketing sayti (index.html) katalogi — narx admin panelda `KatalogNarx` da,
    mijoz mahsulot `kalit` ini yuboradi. Narxi yo'q mahsulot «So'rovnoma» (narx 0):
    jami summaga qo'shilmaydi, xodim mijoz bilan kelishadi.
Keyinroq `Mahsulot` modeliga o'tilsa, faqat `_yukla()` o'zgaradi —
chaqiruvchi kod (views, hisob) o'zgarishsiz qoladi.

Serverda fayl yo'li boshqa joyda bo'lsa:  XARID_MAHSULOTLAR_FAYL=/yo'l/products.json
"""
import hashlib
import json
import os
import re
import threading

from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext as _

_qulf = threading.Lock()
_kesh = {'mtime': None, 'yol': None, 'mahsulotlar': {}}


def _fayl_yoli():
    yol = getattr(settings, 'XARID_MAHSULOTLAR_FAYL', '') or ''
    if yol:
        return str(yol)
    return str(settings.BASE_DIR / 'apps' / 'xaridlar' / 'data' / 'products.json')


def _yukla():
    """{productId: mahsulot} lug'ati. Fayl o'zgarsa avtomatik qayta o'qiladi."""
    yol = _fayl_yoli()
    try:
        mtime = os.path.getmtime(yol)
    except OSError:
        return {}
    with _qulf:
        if _kesh['yol'] != yol or _kesh['mtime'] != mtime:
            with open(yol, encoding='utf-8') as f:
                royxat = json.load(f)
            _kesh['mahsulotlar'] = {str(p['id']): p for p in royxat}
            _kesh['mtime'] = mtime
            _kesh['yol'] = yol
        return _kesh['mahsulotlar']


def mahsulot_topish(product_id):
    return _yukla().get(str(product_id))


# index.html katalogidagi bo'limlar, narxi hozircha YOPIQ (frontend `KAT_NARX_TEZ_ORADA`
# bilan bir xil bo'lishi kerak): ularda admin narx kiritgan bo'lsa ham hisobga olinmaydi.
KATALOG_NARX_YOPIQ = ('gorelka',)

_IKONA = re.compile(r'^fa-[a-z0-9-]{1,40}$')


def _katalog_qatori(kalit, nom, rasm):
    """Marketing katalogidagi mahsulot: narx FAQAT bazadagi `KatalogNarx` dan olinadi."""
    from apps.katalog.models import KatalogNarx   # sikl bo'lmasligi uchun shu yerda

    narx_qatori = KatalogNarx.objects.filter(kalit=kalit, faol=True).first() if kalit else None
    narx = 0
    if narx_qatori and not narx_qatori.sorovnoma and narx_qatori.kategoriya not in KATALOG_NARX_YOPIQ:
        narx = int(narx_qatori.narx)
    nomi = (narx_qatori.nomi if narx_qatori else nom) or ''
    slug = kalit or slugify(nomi)[:150] or 'mahsulot'
    # Kalitsiz (faqat so'rovnoma) mahsulotlar nomi bo'yicha ajratiladi
    belgi = kalit or hashlib.md5(nomi.encode('utf-8')).hexdigest()[:16]
    return {
        'productId': ('kat:' + belgi)[:60],
        'slug': slug[:160],
        'name': nomi[:200],
        'price': narx,
        'image': rasm if _IKONA.match(rasm or '') else '',
    }


def qatorlarni_aniqla(items):
    """Mijoz savatini serverdagi haqiqiy narx/nom bilan almashtiradi.

    items — [{'productId': str | 'kalit': str, 'name': str, 'qty': int}, ...]
    (narx va boshqa maydonlar e'tiborsiz). `productId` — do'kon mahsuloti; u bo'lmasa
    marketing katalogi (`kalit`). Qaytadi: (qatorlar, xato_matni). Har bir qator
    hisobla() va XaridQatori kutgan shaklda: productId, slug, name, price, qty, image.
    Bir mahsulot ikki marta kelsa miqdorlar qo'shiladi.
    """
    katalog = _yukla()

    birlashgan = {}
    for q in items or []:
        pid = str(q.get('productId') or '')
        try:
            qty = int(q.get('qty', 0))
        except (TypeError, ValueError):
            return [], _("Savat ma'lumoti noto'g'ri")
        if qty < 1:
            return [], _("Savat ma'lumoti noto'g'ri")

        if pid:
            p = katalog.get(pid)
            if not p:
                return [], _("Savatdagi mahsulot topilmadi")
            qator = {
                'productId': pid, 'slug': p['slug'], 'name': p['name'],
                'price': int(p['price']), 'image': p.get('image', '') or '',
            }
        else:
            nom = str(q.get('name') or '').strip()
            kalit = str(q.get('kalit') or '').strip()
            if not nom and not kalit:
                return [], _("Savatdagi mahsulot topilmadi")
            qator = _katalog_qatori(kalit, nom, str(q.get('image') or ''))

        kalit_id = qator['productId']
        if kalit_id in birlashgan:
            birlashgan[kalit_id]['qty'] += qty
        else:
            birlashgan[kalit_id] = dict(qator, qty=qty)

    qatorlar = list(birlashgan.values())
    if not qatorlar:
        return [], _("Savat bo'sh")
    for r in qatorlar:
        if r['qty'] > 999:
            return [], _("Savat ma'lumoti noto'g'ri")
    return qatorlar, ''
