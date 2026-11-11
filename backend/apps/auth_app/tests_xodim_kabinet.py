"""Xodim kabineti: «Sertifikatlarim» va «Ish haqi» — faqat o'zinikini o'qiydi,
holat (muddati) to'g'ri hisoblanadi, ish haqi oyiga bitta."""
from datetime import date, timedelta

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auth_app.models import Foydalanuvchi, IshHaqi, Sertifikat

SERT = '/api/auth/xodim/sertifikatlar/'
ISH_HAQI = '/api/auth/xodim/ish-haqi/'


def klient(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return c


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.aziz = mk(telefon='+998900000201', ism='Aziz', rol='xodim', holat='faol')
        self.vali = mk(telefon='+998900000202', ism='Vali', rol='xodim', holat='faol')
        self.mijoz = mk(telefon='+998900000203', ism='Karim', rol='mijoz')
        self.bugun = timezone.localdate()


class SertifikatTestlari(Asos):
    def test_faqat_oziniki(self):
        Sertifikat.objects.create(xodim=self.aziz, nomi='Payvandlash')
        Sertifikat.objects.create(xodim=self.vali, nomi='Boshqaning sertifikati')
        j = klient(self.aziz).get(SERT).json()
        self.assertEqual([s['nomi'] for s in j], ['Payvandlash'])

    def test_holatlar(self):
        mk = lambda nomi, kun: Sertifikat.objects.create(
            xodim=self.aziz, nomi=nomi,
            amal_qiladi=None if kun is None else self.bugun + timedelta(days=kun))
        mk('muddatsiz', None)
        mk('amalda', 400)
        mk('yaqin', 30)
        mk('chegara', 90)
        mk('bugun', 0)
        mk('tugagan', -1)
        holat = {s['nomi']: s['holat'] for s in klient(self.aziz).get(SERT).json()}
        self.assertEqual(holat, {'muddatsiz': 'muddatsiz', 'amalda': 'amalda', 'yaqin': 'yaqin',
                                 'chegara': 'yaqin', 'bugun': 'yaqin', 'tugagan': 'tugagan'})

    def test_mijoz_va_mehmon_kira_olmaydi(self):
        self.assertEqual(klient(self.mijoz).get(SERT).status_code, 403)
        self.assertEqual(klient().get(SERT).status_code, 401)

    def test_yozib_bolmaydi(self):
        self.assertEqual(klient(self.aziz).post(SERT, {'nomi': 'x'}).status_code, 405)


class IshHaqiTestlari(Asos):
    def test_faqat_oziniki_va_jami(self):
        IshHaqi.objects.create(xodim=self.aziz, oy=date(2026, 7, 15), asosiy=4_000_000, bonus=3_450_000)
        IshHaqi.objects.create(xodim=self.vali, oy=date(2026, 7, 1), asosiy=9_000_000, bonus=1)
        j = klient(self.aziz).get(ISH_HAQI).json()
        self.assertEqual(len(j), 1)
        self.assertEqual((j[0]['asosiy'], j[0]['bonus'], j[0]['jami']), (4_000_000, 3_450_000, 7_450_000))
        self.assertEqual(j[0]['oy'], '2026-07-01')       # oyning 1-sanasiga keltirilgan

    def test_oyiga_bitta(self):
        IshHaqi.objects.create(xodim=self.aziz, oy=date(2026, 7, 1))
        with self.assertRaises(IntegrityError), transaction.atomic():
            IshHaqi.objects.create(xodim=self.aziz, oy=date(2026, 7, 20))

    def test_yangisi_birinchi_va_12_oy(self):
        for oy in range(1, 13):
            IshHaqi.objects.create(xodim=self.aziz, oy=date(2025, oy, 1))
        IshHaqi.objects.create(xodim=self.aziz, oy=date(2026, 1, 1))
        j = klient(self.aziz).get(ISH_HAQI).json()
        self.assertEqual(len(j), 12)
        self.assertEqual(j[0]['oy'], '2026-01-01')

    def test_mijoz_va_mehmon_kira_olmaydi(self):
        self.assertEqual(klient(self.mijoz).get(ISH_HAQI).status_code, 403)
        self.assertEqual(klient().get(ISH_HAQI).status_code, 401)

    def test_yozib_bolmaydi(self):
        self.assertEqual(klient(self.aziz).post(ISH_HAQI, {'asosiy': 1}).status_code, 405)


class AdminTestlari(Asos):
    """Xodim sahifasidagi inline'lar: ish haqi faqat tizim egasiga ko'rinadi."""

    def _ochish(self, user):
        from django.urls import reverse
        c = self.client
        c.force_login(user)
        return c.get(reverse('admin:auth_app_xodim_change', args=[self.aziz.pk]))

    def test_ega_ikkalasini_koradi(self):
        ega = Foydalanuvchi.objects.create(telefon='+998900000204', ism='Ega', rol='admin',
                                           is_staff=True, is_superuser=True)
        r = self._ochish(ega)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ish_haqlari')
        self.assertContains(r, 'sertifikatlar')

    def test_direktor_ish_haqini_kormaydi(self):
        from django.contrib.auth.models import Permission
        d = Foydalanuvchi.objects.create(telefon='+998900000205', ism='Direktor', rol='admin',
                                         is_staff=True)
        d.user_permissions.set(Permission.objects.filter(
            content_type__app_label='auth_app',
            codename__in=['view_xodim', 'change_xodim', 'view_sertifikat', 'change_sertifikat',
                          'view_ishhaqi', 'change_ishhaqi']))
        r = self._ochish(d)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'sertifikatlar')
        self.assertNotContains(r, 'ish_haqlari')
