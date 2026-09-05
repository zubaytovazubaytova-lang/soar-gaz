"""Bloklangan boshqaruv (admin) hisobini qayta faollashtiradi.

Boshqaruv paneliga ADMIN_URINISH_LIMIT marta noto'g'ri parol kiritilsa,
hisob 'nofaol' bo'ladi va O'ZI OCHILMAYDI (apps.auth_app.views.admin_login).
Bu ataylab shunday: vaqt o'tgach avtomatik ochilsa, parolni cheksiz
taxmin qilish yo'li ochilib qolardi — hujumchi shunchaki kutib turardi.

Shu sababli ochish HAR DOIM qo'lda va faqat serverga kira oladigan
odam tomonidan bajariladi. Ikki yo'l bor:

  1. Django admin paneli — /admin/auth_app/foydalanuvchi/ (tizim egasi).
  2. Shu buyruq — server konsoli orqali, brauzersiz:

        python manage.py admin_ochish                     # bloklanganlar ro'yxati
        python manage.py admin_ochish +998912466346       # hisobni ochadi
        python manage.py admin_ochish +998912466346 --parol   # + yangi parol

Yangi parol FAQAT so'rov orqali (getpass) kiritiladi — buyruq qatoriga
yozilsa, u shell tarixida va `ps` chiqishida qolib ketardi.
"""
from getpass import getpass

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from apps.auth_app.models import Foydalanuvchi, audit_yoz


def urinish_kaliti(telefon):
    # Kalit admin_login dagi bilan bir xil bo'lishi SHART — aks holda
    # hisoblagich tozalanmay qoladi va hisob birinchi xatoda qayta bloklanadi.
    return f'admin:urinish:{telefon}'


class Command(BaseCommand):
    help = "Bloklangan boshqaruv hisobini qayta faollashtiradi"

    def add_arguments(self, parser):
        parser.add_argument('telefon', nargs='?',
                            help="Ochiladigan hisob telefoni. Ko'rsatilmasa — "
                                 "bloklangan hisoblar ro'yxati chiqadi.")
        parser.add_argument('--parol', action='store_true',
                            help='Hisobga yangi parol ham o\'rnatiladi (so\'rov orqali)')

    def handle(self, *args, **sozlamalar):
        telefon = (sozlamalar.get('telefon') or '').replace(' ', '')
        if not telefon:
            return self._royxat()

        user = Foydalanuvchi.objects.filter(telefon=telefon, rol='admin').first()
        if user is None:
            raise CommandError(
                f"{telefon} — bunday admin hisobi yo'q. "
                f"Ro'yxatni ko'rish: python manage.py admin_ochish")

        edi = user.holat
        user.holat = 'faol'
        maydonlar = ['holat']

        if sozlamalar['parol']:
            parol = getpass('Yangi parol: ')
            if len(parol) < 8:
                raise CommandError("Parol kamida 8 belgidan iborat bo'lishi kerak")
            if parol != getpass('Yana bir marta: '):
                raise CommandError('Parollar mos kelmadi')
            user.set_password(parol)
            maydonlar.append('password')

        user.save(update_fields=maydonlar)
        cache.delete(urinish_kaliti(telefon))

        audit_yoz(None, 'admin_ochildi',
                  f'{telefon} — hisob konsol orqali qayta faollashtirildi'
                  + (', yangi parol berildi' if sozlamalar['parol'] else ''),
                  user=user)

        if edi == 'faol':
            self.stdout.write(self.style.WARNING(
                f'{telefon} allaqachon faol edi — urinishlar hisoblagichi tozalandi.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{telefon} ({user.ism or "ismsiz"}) qayta faollashtirildi.'))
        if sozlamalar['parol']:
            self.stdout.write('Yangi parol o\'rnatildi.')

    def _royxat(self):
        bloklangan = Foydalanuvchi.objects.filter(rol='admin', holat='nofaol')
        if not bloklangan:
            self.stdout.write('Bloklangan admin hisobi yo\'q.')
        else:
            self.stdout.write('Bloklangan admin hisoblari:')
            for u in bloklangan:
                urinish = cache.get(urinish_kaliti(u.telefon), 0)
                self.stdout.write(f'  {u.telefon}  {u.ism or "—"}  '
                                  f'({urinish} ta noto\'g\'ri urinish)')
            self.stdout.write('\nOchish: python manage.py admin_ochish <telefon>')

        # Hali bloklanmagan, lekin chetiga kelib qolganlarni ham ko'rsatamiz —
        # egasi muammoni blokdan OLDIN sezishi uchun.
        chegara = settings.ADMIN_URINISH_LIMIT
        ogoh = []
        for u in Foydalanuvchi.objects.filter(rol='admin', holat='faol'):
            urinish = cache.get(urinish_kaliti(u.telefon), 0)
            if urinish:
                ogoh.append((u, urinish))
        if ogoh:
            self.stdout.write('\nXato urinishlari bor faol hisoblar:')
            for u, urinish in ogoh:
                self.stdout.write(f'  {u.telefon}  {urinish}/{chegara}')
