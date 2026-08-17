"""
Katalog mediasi nazorati — xaridlar bo'limining 4 ta katalogi bo'yicha.

    python manage.py media_nazorat            # faqat tekshiradi (hech nima o'zgartirmaydi)
    python manage.py media_nazorat --import   # index.html dagi mediani bazaga ko'chiradi

Tekshiriladigan holatlar:
  1. Yetim fayl      — images/ da bor, lekin na index.html da, na bazada
  2. Singan havola   — bazada/index.html da bor, lekin diskda yo'q
  3. Tartib buzilishi— video massiv oxirida emas
  4. Noto'g'ri bo'lim— bir kalitning mediasi ikki xil bo'limga biriktirilgan
  5. Bog'lanmagan    — bazada bor, lekin index.html da bunday `kalit` yo'q
  6. Bo'lim butunligi— index.html da hamon aynan 4 ta KAT_DATA bo'limi bormi
"""
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.katalog.models import BOLIMLAR, VIDEO_KENGAYTMALARI, KatalogMedia

ILDIZ = settings.BASE_DIR.parent
INDEX = os.path.join(ILDIZ, 'index.html')
RASMLAR = os.path.join(ILDIZ, 'images')

# Bo'lim kalitlari index.html va Django da bir xil
KUTILGAN_BOLIMLAR = set(BOLIMLAR)   # quvur, hisob, ventil, gorelka


def _html_oqish():
    with open(INDEX, encoding='utf-8') as f:
        return f.read()


def _html_mediasi(html):
    """index.html dan {kalit: [yo'llar]} ajratadi.

    Har bir `kalit:'...'` dan keyingi eng yaqin `rasm:[...]` massivini oladi.
    """
    natija = {}
    for m in re.finditer(r"kalit\s*:\s*'([^']+)'", html):
        kalit = m.group(1)
        parcha = html[m.end():m.end() + 4000]
        r = re.search(r"rasm\s*:\s*\[([^\]]*)\]", parcha)
        if r:
            natija[kalit] = re.findall(r"'([^']+)'", r.group(1))
    return natija


def _html_barcha_yollari(html):
    """index.html dagi HAR QANDAY `rasm:[...]` yo'llari — `kalit` bor-yo'qligidan qat'i nazar.

    Katalogdagi ba'zi mahsulotlarning `kalit` maydoni yo'q (masalan quvurlar),
    ular admin panelga bog'lanmaydi, lekin fayllari baribir ishlatilgan hisoblanadi.
    """
    yollar = set()
    for r in re.finditer(r"rasm\s*:\s*\[([^\]]*)\]", html):
        yollar.update(re.findall(r"'([^']+)'", r.group(1)))
    for r in re.finditer(r"rasm\s*:\s*'([^']+)'", html):
        yollar.add(r.group(1))
    return yollar


def _kalitsiz_mediali_mahsulotlar(html):
    """`rasm` bor, lekin `kalit` yo'q mahsulotlar — admin orqali boshqarib bo'lmaydi."""
    natija = []
    for m in re.finditer(r"\{nom\s*:\s*'([^']+)',([^\n]*)", html):
        satr = m.group(2)
        if 'rasm:' in satr and 'kalit:' not in satr:
            natija.append(m.group(1))
    return natija


def _disk_fayllari():
    yollar = set()
    for papka, _, fayllar in os.walk(RASMLAR):
        for f in fayllar:
            nisbiy = os.path.relpath(os.path.join(papka, f), RASMLAR)
            yollar.add('images/' + nisbiy.replace('\\', '/'))
    return yollar


def _videomi(yol):
    return yol.lower().endswith(VIDEO_KENGAYTMALARI)


class Command(BaseCommand):
    help = "Katalog rasm/videolarini 4 bo'lim bo'yicha tekshiradi va tartibga soladi"

    def add_arguments(self, parser):
        parser.add_argument(
            '--import', action='store_true', dest='import_qil',
            help="index.html dagi mediani KatalogMedia jadvaliga ko'chiradi (takrorlamaydi)")

    def handle(self, *args, **opts):
        html = _html_oqish()
        html_media = _html_mediasi(html)
        diskda = _disk_fayllari()
        bazada = list(KatalogMedia.objects.all())

        if opts['import_qil']:
            self._import(html, html_media)
            bazada = list(KatalogMedia.objects.all())

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== KATALOG MEDIA NAZORATI ===\n'))
        muammo = 0

        # 6. Bo'lim butunligi
        bolimlar = set(re.findall(r'^    (\w+): \{$', html, re.M))
        topilgan = bolimlar & KUTILGAN_BOLIMLAR
        if topilgan != KUTILGAN_BOLIMLAR:
            muammo += 1
            self.stdout.write(self.style.ERROR(
                f"[BO'LIM] KAT_DATA da 4 bo'lim to'liq emas. "
                f"Yo'q: {sorted(KUTILGAN_BOLIMLAR - topilgan)}"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"[BO'LIM] 4 bo'lim joyida: {', '.join(sorted(KUTILGAN_BOLIMLAR))}"))

        # Barcha havolalar (index.html — kalitli va kalitsiz — hamda baza)
        havolalar = _html_barcha_yollari(html) | {m.yol for m in bazada}

        # Admin panelga bog'lanmaydigan mahsulotlar (kalit yo'q)
        for nom in _kalitsiz_mediali_mahsulotlar(html):
            self.stdout.write(self.style.NOTICE(
                f'[KALITSIZ] «{nom}» — rasmi bor, lekin `kalit` yo\'q, '
                f'admin panel orqali boshqarib bo\'lmaydi'))

        # 1. Yetim fayllar
        for y in sorted(diskda - havolalar):
            muammo += 1
            self.stdout.write(self.style.WARNING(f'[YETIM] {y} — hech qayerda ishlatilmagan'))

        # 2. Singan havolalar
        for y in sorted(havolalar - diskda):
            muammo += 1
            self.stdout.write(self.style.ERROR(f'[SINGAN] {y} — diskda yo\'q'))

        # 3. Tartib buzilishi (index.html)
        for kalit, yollar in sorted(html_media.items()):
            turlar = [_videomi(y) for y in yollar]
            if True in turlar and False in turlar[turlar.index(True):]:
                muammo += 1
                self.stdout.write(self.style.WARNING(
                    f'[TARTIB] index.html «{kalit}» — video massiv oxirida emas'))

        # 3b. Tartib buzilishi (baza)
        guruh = {}
        for m in bazada:
            guruh.setdefault(m.kalit, []).append(m)
        for kalit, ro in sorted(guruh.items()):
            saralangan = sorted(ro, key=lambda m: m.tartib_kaliti())
            if [m.id for m in saralangan] != [m.id for m in sorted(ro, key=lambda m: (m.tartib, m.id))]:
                self.stdout.write(self.style.NOTICE(
                    f'[TARTIB] baza «{kalit}» — video tartib raqami bo\'yicha oldinda, '
                    f'lekin sayt uni oxiriga suradi (xato emas, shunchaki eslatma)'))

        # 4. Noto'g'ri bo'lim
        for kalit, ro in sorted(guruh.items()):
            bolimlar_ = {m.bolim for m in ro}
            if len(bolimlar_) > 1:
                muammo += 1
                self.stdout.write(self.style.ERROR(
                    f'[BO\'LIM] «{kalit}» mediasi bir nechta bo\'limga biriktirilgan: '
                    f'{sorted(bolimlar_)}'))

        # 5a. Manbalar farqi — index.html da bor, lekin bazada yo'q.
        #     Bu jimgina yo'qotish: sayt `rasm` massivini API javobiga
        #     BUTUNLAY almashtiradi, shuning uchun bazada yo'q fayl
        #     index.html da tursa ham saytda ko'rinmaydi.
        for kalit, yollar in sorted(html_media.items()):
            if kalit not in guruh:
                continue                       # 5-band buni alohida aytadi
            bazada_bor = {m.yol for m in guruh[kalit]}
            for y in yollar:
                if y not in bazada_bor:
                    muammo += 1
                    self.stdout.write(self.style.ERROR(
                        f'[BAZADA YO\'Q] «{kalit}» → {y} — index.html da bor, '
                        f'lekin admin bazasida yo\'q. Sayt uni KO\'RSATMAYDI '
                        f'(--import bilan tiklang).'))
            # Teskarisi: bazada bor, index.html da yo'q — bu normal holat
            # (admin orqali yuklangan yangi media), shuning uchun ogohlantirmaymiz.

        # 5. Bog'lanmagan kalitlar
        for kalit in sorted(set(guruh) - set(html_media)):
            muammo += 1
            self.stdout.write(self.style.WARNING(
                f'[KALIT] «{kalit}» bazada bor, lekin index.html da bunday kalit yo\'q'))

        # Yakun
        self.stdout.write('')
        self.stdout.write(f'Disk: {len(diskda)} fayl · index.html: {len(html_media)} mahsulot '
                          f'· baza: {len(bazada)} yozuv')
        if muammo:
            self.stdout.write(self.style.ERROR(f'Muammo topildi: {muammo} ta\n'))
        else:
            self.stdout.write(self.style.SUCCESS('Muammo topilmadi.\n'))

    # ── index.html → baza ────────────────────────────────────
    def _import(self, html, html_media):
        """Har bir mahsulotning `rasm` yo'llarini KatalogMedia ga yozadi."""
        qoshildi = otkazildi = 0

        # Har bir kalit qaysi KAT_DATA bo'limida turganini aniqlaymiz.
        # M_* o'zgaruvchilari KAT_DATA dan yuqorida — ular uchun bo'lim
        # o'zgaruvchi nomi ro'yxatga qo'shilgan joydan topiladi.
        kalit_bolim = {}
        for html_bolim in KUTILGAN_BOLIMLAR:
            m = re.search(rf'^    {html_bolim}: \{{$', html, re.M)
            if not m:
                continue
            keyingi = re.search(r'^    \w+: \{$', html[m.end():], re.M)
            blok = html[m.end():m.end() + (keyingi.start() if keyingi else 20000)]
            for k in re.findall(r"kalit\s*:\s*'([^']+)'", blok):
                kalit_bolim.setdefault(k, html_bolim)
            # M_* havolalari (ulashilgan mahsulotlar)
            for var in re.findall(r'^\s*(M_\w+),\s*$', blok, re.M):
                v = re.search(rf"const {var} = \{{.*?kalit\s*:\s*'([^']+)'", html, re.S)
                if v:
                    kalit_bolim.setdefault(v.group(1), html_bolim)

        for kalit, yollar in html_media.items():
            html_bolim = kalit_bolim.get(kalit)
            if not html_bolim:
                self.stdout.write(self.style.WARNING(
                    f'[IMPORT] «{kalit}» qaysi bo\'limda ekani aniqlanmadi — o\'tkazildi'))
                continue
            bolim = html_bolim   # kalitlar bir xil

            for i, yol in enumerate(yollar):
                fayl_nomi = yol[len('images/'):]
                if KatalogMedia.objects.filter(fayl=fayl_nomi).exists():
                    otkazildi += 1
                    continue
                KatalogMedia.objects.create(
                    kalit=kalit, bolim=bolim, fayl=fayl_nomi,
                    tartib=(i + 1) * 10, faol=True)
                qoshildi += 1

        self.stdout.write(self.style.SUCCESS(
            f'[IMPORT] {qoshildi} ta yozuv qo\'shildi, {otkazildi} ta allaqachon bor edi.'))
