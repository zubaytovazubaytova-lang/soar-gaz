"""Kvitansiya qog'oz shaklida va kvitansiyadagi mijozni avtomatik ro'yxatga olish."""
import re
from unittest import mock

from django.contrib.auth.hashers import is_password_usable
from django.test import Client, SimpleTestCase

from apps.auth_app.models import AuditYozuv, Foydalanuvchi
from apps.tushum.models import Tushum
from .models import Kvitansiya, Sozlama
from .sozlar import summa_sozlar
from .tests import Asos, KV


class SozlarTestlari(SimpleTestCase):
    def test_summa_sozlar(self):
        holatlar = {
            0: 'nol', 1: 'bir', 7: 'yetti', 10: "o'n", 21: 'yigirma bir', 100: 'bir yuz',
            55000: 'ellik besh ming', 150000: 'bir yuz ellik ming', 16250: "o'n olti ming ikki yuz ellik",
            1000: 'bir ming', 1250300: 'bir million ikki yuz ellik ming uch yuz',
            482000: "to'rt yuz sakson ikki ming", 2000000000: 'ikki milliard',
            999999: "to'qqiz yuz to'qson to'qqiz ming to'qqiz yuz to'qson to'qqiz",
        }
        for n, kutilgan in holatlar.items():
            self.assertEqual(summa_sozlar(n), kutilgan, n)

    def test_notogri_qiymat_bosh_qator(self):
        for q in (-5, None, 'abc', 10 ** 12):
            self.assertEqual(summa_sozlar(q), '', q)

    def test_matn_va_son_qiymati_teng(self):
        self.assertEqual(summa_sozlar('55000'), 'ellik besh ming')


class MijozniRoyxatgaOlishTestlari(Asos):
    def kiritish(self, telefon='+998931112233', ism='Yangi Mijoz', manzil='Sergeli 4-mavze', **kw):
        t = self.tushum(buyurtma=kw.pop('buyurtma', False))
        return self.x.post(KV, {'tushum': t.pk, 'mijoz_ism': ism, 'mijoz_telefon': telefon, 'manzil': manzil, **kw},
                           format='json')

    def test_saytdan_royxatdan_otmagan_mijoz_avtomatik_ochiladi(self):
        self.assertFalse(Foydalanuvchi.objects.filter(telefon='+998931112233').exists())
        r = self.kiritish()
        self.assertEqual(r.status_code, 201, r.content)
        m = Foydalanuvchi.objects.get(telefon='+998931112233')
        self.assertEqual((m.rol, m.ism, m.manzil, m.holat), ('mijoz', 'Yangi Mijoz', 'Sergeli 4-mavze', 'faol'))
        self.assertFalse(is_password_usable(m.password))          # parolsiz: kabinetga SMS kod bilan kiradi
        k = Kvitansiya.objects.get()
        self.assertEqual((k.mijoz, k.yangi_mijoz), (m, True))
        self.assertTrue(r.json()['yangi_mijoz'])

    def test_yangi_mijozga_kabinet_haqida_sms(self):
        self.kiritish()
        telefon, matn = self.sms.call_args[0]
        self.assertEqual(telefon, '+998931112233')
        self.assertIn('/kvitansiya/', matn)
        self.assertIn('/kabinet/', matn)

    def test_mavjud_mijozga_hisob_qayta_ochilmaydi_kabinet_havolasiz(self):
        sana = self.mijoz.yaratilgan
        r = self.kiritish(telefon=self.mijoz.telefon, ism='Boshqa Ism', manzil='Boshqa manzil')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Foydalanuvchi.objects.filter(telefon=self.mijoz.telefon).count(), 1)
        k = Kvitansiya.objects.get()
        self.assertEqual((k.mijoz, k.yangi_mijoz), (self.mijoz, False))
        self.assertNotIn('/kabinet/', self.sms.call_args[0][1])
        self.mijoz.refresh_from_db()
        self.assertEqual((self.mijoz.ism, self.mijoz.yaratilgan), ('Karim', sana))   # mavjud ism almashtirilmadi

    def test_mavjud_mijozning_bosh_maydonlari_toldiriladi(self):
        self.assertEqual(self.mijoz.manzil, '')
        self.kiritish(telefon=self.mijoz.telefon, ism='Boshqa Ism', manzil='Yunusobod 7')
        self.mijoz.refresh_from_db()
        self.assertEqual((self.mijoz.ism, self.mijoz.manzil), ('Karim', 'Yunusobod 7'))

    def test_xodim_va_admin_telefoni_mijoz_sifatida_olinmaydi(self):
        for tel in (self.boshqa.telefon, self.admin.telefon):
            r = self.kiritish(telefon=tel)
            self.assertEqual(r.status_code, 409, tel)
            self.assertIn('xodim yoki administrator', r.json()['detail'])
        self.assertFalse(Kvitansiya.objects.exists())
        self.assertEqual(Foydalanuvchi.objects.get(pk=self.boshqa.pk).rol, 'xodim')     # rol o'zgarmadi

    def test_xato_bolsa_mijoz_ham_ochilmaydi(self):
        r = self.kiritish(manzil='')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Foydalanuvchi.objects.filter(telefon='+998931112233').exists())

    def test_bir_mijozga_ikkinchi_kvitansiya_yangi_hisob_ochmaydi(self):
        self.kiritish()
        r = self.kiritish()
        self.assertFalse(r.json()['yangi_mijoz'])
        self.assertEqual(Foydalanuvchi.objects.filter(telefon='+998931112233').count(), 1)
        self.assertEqual(Kvitansiya.objects.count(), 2)

    def test_mijozsiz_buyurtma_shu_mijozga_boglanadi(self):
        self.b.mijoz = None
        self.b.save()
        self.x.post(KV, {'tushum': self.tushum().pk}, format='json')
        self.b.refresh_from_db()
        self.assertEqual(self.b.mijoz.telefon, '+998901234567')

    def test_buyurtmaning_oz_mijozi_almashtirilmaydi(self):
        self.x.post(KV, {'tushum': self.tushum().pk}, format='json')
        self.b.refresh_from_db()
        self.assertEqual(self.b.mijoz, self.mijoz)

    def test_jurnalga_kim_royxatga_olgani_yoziladi(self):
        self.kiritish()
        y = AuditYozuv.objects.get(amal='mijoz_ochildi')
        self.assertEqual(y.kim, self.xodim)
        self.assertIn('+998931112233', y.tafsilot)

    def test_yangi_hisoblar_soni_cheklangan(self):
        with mock.patch('apps.hujjatlar.xizmat.YANGI_MIJOZ_SOATLIK_LIMIT', 2):
            for i in range(2):
                self.assertEqual(self.kiritish(telefon=f'+99893111220{i}').status_code, 201)
            r = self.kiritish(telefon='+998931112209')
            self.assertEqual(r.status_code, 429)
            # mavjud hisobga kvitansiya limitga tushmaydi
            self.assertEqual(self.kiritish(telefon='+998931112200').status_code, 201)

    def test_mijoz_admin_royxatida_korinadi(self):
        self.kiritish()
        royxat = self.a.get('/api/auth/mijozlar/').json()
        self.assertIn('+998931112233', [m['telefon'] for m in royxat])

    def test_shartnoma_tuzilgan_mijoz_ham_royxatga_olinadi(self):
        self.tasdiqla_sozlama()
        from .models import Shartnoma
        r = self.x.post('/api/hujjatlar/shartnoma/', {'buyurtma': self.b.pk, 'mijoz_telefon': '+998939990000',
                                                      'mijoz_ism': 'Shartnoma Mijoz', 'manzil': 'Chilonzor'},
                        format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Shartnoma.objects.get().mijoz.telefon, '+998939990000')


class QogozShaklTestlari(Asos):
    def sahifa(self, aloqa=None, **kw):
        k = self.x.post(KV, {'tushum': self.tushum(**kw).pk, **(aloqa or {})}, format='json').json()
        return k, Client().get(f"/kvitansiya/{k['token']}/").content.decode()

    def test_qogoz_kvitansiyaning_barcha_qismlari(self):
        k, html = self.sahifa()
        for qism in ("Gaz jihozlariga xizmat ko'rsatish kvitansiyasi", "To'lov varaqasi raqami", k['raqam'],
                     '>Kun<', '>Oy<', '>Yil<', "Quyida berilgan xizmat uchun haq", "Iste'molchi FISh (korxona nomi)",
                     'Manzili', 'Kod (shartnoma raqami)', 'Telefon raqami',
                     'Gaz jihoz nomi', "Narxnoma raqami va ko'rsatgichi", 'Soni', '(QQS bilan)',
                     "Umumiy mablag' yig'indisi", 'Jami:', "(so'z bilan)", 'Ish bajaruvchi xodim', "Iste'molchi:",
                     'CALL centre', "Servis xizmat ko'rsatish bo'limi boshlig'i"):
            self.assertIn(qism, html, qism)

    def test_mijoz_telefoni_va_turar_joyi_sana_katakchalarida(self):
        from django.utils import timezone
        k, html = self.sahifa()
        bugun = timezone.localtime()
        self.assertIn(f'<td>{bugun.day:02d}</td><td>{bugun.month:02d}</td><td>{bugun.year}</td>', html)
        self.assertIn('+998901234567', html)
        self.assertIn('Chilonzor 5-mavze, 12-uy', html)
        self.assertIn('Karim Rahimov', html)

    def test_jadval_buyurtma_xizmatlaridan(self):
        k, html = self.sahifa()
        self.assertIn('PG-2x kamparakli maishiy gaz plitasi', html)
        self.assertIn('1 (profilaktika)', html)                    # narxnoma raqami va ko'rsatgichi
        self.assertIn('30 236', html)                              # narxi
        self.assertIn('60 472', html)                              # soni 2 × narx
        q = Kvitansiya.objects.get().qatorlar[0]
        self.assertEqual((q['soni'], q['narx_dan'], q['jami_dan'], q['raqam']), (2, 30236, 60472, '1'))

    def test_summa_son_va_soz_bilan(self):
        k, html = self.sahifa(summa=55000)
        self.assertIn('55 000 so', html)
        self.assertIn("ellik besh ming so'm", html)

    def test_qisman_tolov_buyurtma_summasini_korsatadi(self):
        k, html = self.sahifa(summa=150000)
        self.assertIn("Buyurtmaning umumiy summasi: <b>500 000 so'm</b>", html)

    def test_toliq_tolovda_qismanlik_yozuvi_yoq(self):
        k, html = self.sahifa(summa=500000)
        self.assertNotIn('Buyurtmaning umumiy summasi', html)

    def test_buyurtmasiz_tushum_bitta_qator(self):
        aloqa = {'mijoz_ism': 'Vali', 'mijoz_telefon': '+998937776655', 'manzil': 'Olmazor 2'}
        k, html = self.sahifa(aloqa=aloqa, buyurtma=False, ish_turi='Gaz plitasi (profilaktika)')
        kv = Kvitansiya.objects.get()
        self.assertEqual(len(kv.qatorlar), 1)
        self.assertEqual((kv.qatorlar[0]['soni'], kv.qatorlar[0]['jami_dan']), (1, 150000))
        self.assertIn('Gaz plitasi (profilaktika)', html)

    def test_shartnoma_raqami_kod_maydonida(self):
        self.tasdiqla_sozlama()
        sh = self.x.post('/api/hujjatlar/shartnoma/', {'buyurtma': self.b.pk}, format='json').json()
        k, html = self.sahifa()
        self.assertEqual(Kvitansiya.objects.get().shartnoma_raqami, sh['raqam'])
        self.assertIn(sh['raqam'], html)

    def test_eski_kvitansiya_snapshotsiz_ham_ochiladi(self):
        k, _ = self.sahifa()
        Kvitansiya.objects.update(qatorlar=[], buyurtma_summa=None)
        r = Client().get(f"/kvitansiya/{k['token']}/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('150 000', r.content.decode())

    def test_kompaniya_telefoni_qogozdagi_kabi(self):
        k, html = self.sahifa()
        self.assertIn('(98) 274 62 87', html)
        self.assertIn('(91) 974 62 87', html)

    def test_servis_boshligi_sozlamadan(self):
        s = Sozlama.olish()
        s.servis_boshligi = 'Sinov Boshliq'
        s.save()
        k, html = self.sahifa()
        self.assertIn('Sinov Boshliq', html)

    def test_sahifada_kirill_harflari_aralashib_qolmagan(self):
        # Hujjat lotin yozuvida: tasodifan kirill harfi kirib qolishining oldini oladi
        k, html = self.sahifa()
        tana = re.sub(r'<style.*?</style>', '', html, flags=re.S)
        self.assertIsNone(re.search('[А-Яа-яЁёҚқҒғҲҳЎў]', tana))
