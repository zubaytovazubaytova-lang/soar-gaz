"""Davomat: avtomatik (smena) va Kadrlar mutaxassisi qo'lda qo'ygan «keldi / kelmadi» belgisi."""
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.auth_app.models import Foydalanuvchi
from apps.joylashuv.models import Smena
from apps.kadrlar.models import DavomatBelgisi
from apps.kadrlar.tests import KUN, klient

DAVOMAT = '/api/kadrlar/davomat/'


class Asos(TestCase):
    def setUp(self):
        cache.clear()
        mk = Foydalanuvchi.objects.create
        self.kadr = mk(telefon='+998900000701', ism='Ruxsora', rol='xodim', holat='faol',
                       lavozim="Kadrlar bo'yicha mutaxassis")
        self.usta = mk(telefon='+998900000702', ism='Aziz', rol='xodim', holat='faol', lavozim='Montaj ustasi')
        self.usta2 = mk(telefon='+998900000703', ism='Vali', rol='xodim', holat='faol', lavozim='Metrolog')
        self.nofaol = mk(telefon='+998900000704', ism='Eski', rol='xodim', holat='nofaol', lavozim='Montaj ustasi')
        self.mijoz = mk(telefon='+998900000705', ism='Karim', rol='mijoz')
        self.admin = mk(telefon='+998900000706', ism='Ega', rol='admin', is_staff=True, is_superuser=True)

    def belgila(self, user=None, **d):
        return klient(user or self.kadr).post(DAVOMAT, d, format='json')

    def qator(self, xodim, **q):
        j = klient(self.kadr).get(KUN, q).json()
        return next(x for x in j['xodimlar'] if x['id'] == xodim.id), j['xulosa']


class BelgilashTestlari(Asos):
    def test_keldi_belgilash_smenasiz(self):
        """Smena ochmaydigan (ofis) xodim: Kadrlar «keldi» desa, davomatga tushadi."""
        q, x = self.qator(self.usta)
        self.assertEqual((q['holat'], x['keldi'], x['kelmadi']), ('kelmadi', 0, 2))
        r = self.belgila(xodim_id=self.usta.id, holat='keldi')
        self.assertEqual(r.status_code, 200, r.content)
        q, x = self.qator(self.usta)
        self.assertEqual((q['holat'], q['avto_holat'], q['qolda']['holat']), ('keldi', 'kelmadi', 'keldi'))
        self.assertEqual((x['keldi'], x['kelmadi'], x['qolda']), (1, 1, 1))
        self.assertEqual(q['qolda']['belgilagan'], 'Ruxsora')

    def test_kelmadi_sabab_bilan(self):
        r = self.belgila(xodim_id=self.usta.id, holat='kelmadi', sabab='kasal', izoh='Shifokor ko\'rigi')
        self.assertEqual(r.status_code, 200)
        q, _x = self.qator(self.usta)
        self.assertEqual((q['holat'], q['qolda']['sabab'], q['qolda']['sabab_nomi'], q['qolda']['izoh']),
                         ('kelmadi', 'kasal', 'Kasal', "Shifokor ko'rigi"))

    def test_sabab_berilmasa_sababsiz(self):
        self.belgila(xodim_id=self.usta.id, holat='kelmadi')
        self.assertEqual(DavomatBelgisi.objects.get().sabab, 'sababsiz')

    def test_kelmadi_smenali_xodimni_ham_kelmadi_qiladi(self):
        """Qo'lda belgi avtomatikdan ustun; ziddiyat bo'lsa 'qarama' belgisi chiqadi."""
        Smena.objects.create(xodim=self.usta)
        q, _x = self.qator(self.usta)
        self.assertEqual(q['holat'], 'ishda')
        self.belgila(xodim_id=self.usta.id, holat='kelmadi', sabab='ruxsat')
        q, x = self.qator(self.usta)
        self.assertEqual((q['holat'], q['avto_holat'], q['qarama']), ('kelmadi', 'ishda', True))
        self.assertEqual(x['ishda'], 0)

    def test_keldi_smena_ochiq_bolsa_ishda_qoladi(self):
        Smena.objects.create(xodim=self.usta)
        self.belgila(xodim_id=self.usta.id, holat='keldi')
        q, x = self.qator(self.usta)
        self.assertEqual((q['holat'], x['ishda']), ('ishda', 1))

    def test_qayta_belgilash_va_bitta_yozuv(self):
        self.belgila(xodim_id=self.usta.id, holat='kelmadi', sabab='kasal')
        self.belgila(xodim_id=self.usta.id, holat='keldi')
        self.assertEqual(DavomatBelgisi.objects.count(), 1)
        b = DavomatBelgisi.objects.get()
        self.assertEqual((b.holat, b.sabab), ('keldi', ''))

    def test_tozalash_avtomatikka_qaytaradi(self):
        self.belgila(xodim_id=self.usta.id, holat='keldi')
        self.assertEqual(self.belgila(xodim_id=self.usta.id, holat='tozala').status_code, 200)
        q, _x = self.qator(self.usta)
        self.assertEqual((q['holat'], q['qolda']), ('kelmadi', None))
        self.assertEqual(DavomatBelgisi.objects.count(), 0)

    def test_otgan_kunga_belgilash(self):
        kecha = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.belgila(xodim_id=self.usta.id, holat='keldi', sana=kecha)
        q, _x = self.qator(self.usta, sana=kecha)
        self.assertEqual(q['holat'], 'keldi')
        q, _x = self.qator(self.usta)                              # bugun ta'sirlanmaydi
        self.assertEqual(q['holat'], 'kelmadi')

    def test_notogri_kiritish(self):
        for d in ({'xodim_id': self.usta.id, 'holat': 'xato'},
                  {'xodim_id': self.usta.id, 'holat': 'kelmadi', 'sabab': 'qalbaki'},
                  {'xodim_id': self.usta.id, 'holat': 'keldi', 'sana': 'kecha'},
                  {'xodim_id': self.usta.id, 'holat': 'keldi', 'sana': (timezone.localdate() + timedelta(days=1)).isoformat()}):
            self.assertEqual(self.belgila(**d).status_code, 400, d)
        for d in ({'holat': 'keldi'}, {'xodim_id': 99999, 'holat': 'keldi'}, {'xodim_id': self.nofaol.id, 'holat': 'keldi'},
                  {'xodim_id': self.kadr.id, 'holat': 'keldi'}, {'xodim_id': self.mijoz.id, 'holat': 'keldi'}):
            self.assertEqual(self.belgila(**d).status_code, 404, d)
        self.assertEqual(DavomatBelgisi.objects.count(), 0)

    def test_faqat_kadrlar_belgilaydi(self):
        for u in (self.usta, self.mijoz, self.admin):
            self.assertEqual(self.belgila(u, xodim_id=self.usta2.id, holat='keldi').status_code, 403)
        self.assertEqual(klient().post(DAVOMAT, {}, format='json').status_code, 401)
        self.assertEqual(DavomatBelgisi.objects.count(), 0)
        # Administrator ko'radi (faqat o'qish), lekin belgilay olmaydi
        j = klient(self.admin).get(KUN).json()
        self.assertEqual(j['xulosa']['jami'], 2)

    def test_nofaol_kadr_belgilay_olmaydi(self):
        self.kadr.holat = 'nofaol'
        self.kadr.save()
        self.assertEqual(self.belgila(xodim_id=self.usta.id, holat='keldi').status_code, 403)
