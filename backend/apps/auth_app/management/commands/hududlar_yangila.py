"""Frontend fayllaridagi hudud ro'yxatlarini yagona manbadan qayta yaratadi.

Manba — apps/auth_app/hududlar.py. Bu buyruq uni index.html, kabinet.html va
admin.html ichidagi belgilangan bloklarga yozadi, shunda ro'yxat bir joyda
o'zgartirilsa, hamma yerda yangilanadi.

    python manage.py hududlar_yangila          # yozadi
    python manage.py hududlar_yangila --tekshir  # faqat tekshiradi, yozmaydi

Bloklar HTML/JS izohlari bilan chegaralangan:
    <!-- HUDUD:BOSH -->  ...  <!-- HUDUD:OXIR -->
    // HUDUD:BOSH        ...  // HUDUD:OXIR
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.auth_app.hududlar import HUDUDLAR_XARITASI, barcha_hududlar

ILDIZ = Path(settings.BASE_DIR).parent

HTML_BOSH, HTML_OXIR = '<!-- HUDUD:BOSH -->', '<!-- HUDUD:OXIR -->'
JS_BOSH, JS_OXIR = '// HUDUD:BOSH', '// HUDUD:OXIR'


def _qochir(matn):
    return matn.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def html_optgroup(chekinish):
    """Viloyatlar bo'yicha guruhlangan <optgroup> bloki."""
    b = ' ' * chekinish
    qismlar = []
    for viloyat, tumanlar in HUDUDLAR_XARITASI:
        ichi = ''.join(f'<option>{_qochir(t)}</option>' for t in tumanlar)
        qismlar.append(f'{b}<optgroup label="{_qochir(viloyat)}">{ichi}</optgroup>')
    return '\n'.join(qismlar)


def js_massiv():
    """kabinet.html uchun [viloyat, [tumanlar]] ko'rinishidagi massiv."""
    satrlar = []
    for viloyat, tumanlar in HUDUDLAR_XARITASI:
        nomlar = ', '.join(_js_satr(t) for t in tumanlar)
        satrlar.append(f'  [{_js_satr(viloyat)}, [{nomlar}]],')
    return 'const HUDUDLAR = [\n' + '\n'.join(satrlar) + '\n];'


def _js_satr(matn):
    return '"' + matn.replace('\\', '\\\\').replace('"', '\\"') + '"'


class Command(BaseCommand):
    help = "Frontend fayllaridagi hudud ro'yxatlarini yangilaydi"

    def add_arguments(self, parser):
        parser.add_argument('--tekshir', action='store_true',
                            help='Fayllarga yozmasdan, faqat farqni ko\'rsatadi')

    def handle(self, *args, **sozlama):
        tekshir = sozlama['tekshir']
        vazifalar = [
            ('index.html', HTML_BOSH, HTML_OXIR, lambda: html_optgroup(16)),
            ('admin.html', HTML_BOSH, HTML_OXIR, lambda: html_optgroup(18)),
            ('kabinet.html', JS_BOSH, JS_OXIR, js_massiv),
        ]

        self.stdout.write(f'Manba: {len(HUDUDLAR_XARITASI)} viloyat, '
                          f'{len(barcha_hududlar())} tuman/shahar\n')

        for nom, bosh, oxir, yasa in vazifalar:
            yol = ILDIZ / nom
            if not yol.exists():
                self.stderr.write(self.style.ERROR(f'{nom}: fayl topilmadi'))
                continue

            matn = yol.read_text(encoding='utf-8')
            naqsh = re.compile(
                re.escape(bosh) + r'.*?' + re.escape(oxir), re.S)
            topildi = naqsh.findall(matn)
            if not topildi:
                self.stderr.write(self.style.WARNING(
                    f'{nom}: {bosh} ... {oxir} bloki topilmadi — o\'tkazib yuborildi'))
                continue

            yangi_matn = naqsh.sub(
                lambda m: f'{bosh}\n{yasa()}\n{" " * _chekinish(m.group(0))}{oxir}',
                matn)

            if yangi_matn == matn:
                self.stdout.write(f'{nom}: {len(topildi)} ta blok — o\'zgarish yo\'q')
                continue

            if tekshir:
                self.stdout.write(self.style.WARNING(
                    f'{nom}: {len(topildi)} ta blok yangilanishi kerak'))
            else:
                yol.write_text(yangi_matn, encoding='utf-8')
                self.stdout.write(self.style.SUCCESS(
                    f'{nom}: {len(topildi)} ta blok yangilandi'))


def _chekinish(blok):
    """Blok oxiridagi belgining chekinishini saqlaymiz."""
    oxirgi = blok.rsplit('\n', 1)[-1]
    return len(oxirgi) - len(oxirgi.lstrip())
