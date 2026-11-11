"""Mijoz bilan hujjatlar: SHARTNOMA (buyurtma bo'yicha) va KVITANSIYA (olingan pul bo'yicha).

Asosiy qoidalar:
  * hujjat tuzilgan paytdagi ma'lumot (mijoz ismi, TELEFONI, TURAR JOYI, xizmatlar, summa)
    hujjatning o'zida SAQLANADI — keyin mijoz profili yoki narxnoma o'zgarsa ham hujjat o'zgarmaydi;
  * hujjat o'chirilmaydi: xato bo'lsa BEKOR qilinadi va yangisi chiqariladi;
  * raqamlar ketma-ket va takrorlanmaydi (yil bo'yicha: KV-2026-000123, SH-2026-000045);
  * mijozga SMS boradi: kvitansiya raqami va havolasi, shartnoma uchun tasdiqlash kodi.
"""
import secrets

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone

SHARTNOMA_NAMUNA = """XIZMAT KO'RSATISH SHARTNOMASI № {raqam}
{sana}

{kompaniya} (keyingi o'rinlarda «Ijrochi») bir tomondan va {mijoz_ism} (keyingi o'rinlarda «Buyurtmachi») ikkinchi tomondan quyidagilar haqida shartnoma tuzdilar.

1. SHARTNOMA PREDMETI
Ijrochi Buyurtmachining manzilida: {manzil} quyidagi xizmatlarni bajaradi:
{xizmatlar}

2. XIZMAT NARXI
Xizmatlarning umumiy narxi: {summa} so'm.

3. TARAFLARNING ALOQA MA'LUMOTLARI
Buyurtmachi: {mijoz_ism}, telefon: {mijoz_telefon}, manzil: {manzil}.
Ijrochi: {kompaniya}. Ijrochi vakili: {xodim}.

[DIQQAT: bu faqat namunaviy matn. Kompaniyaning tasdiqlangan huquqiy shartnoma matni (to'lov tartibi, kafolat, javobgarlik, nizolarni hal qilish) bilan almashtirilishi kerak.]
"""


class Sozlama(models.Model):
    """Kompaniya rekvizitlari va shartnoma matni (yagona yozuv). Django panelida tahrirlanadi."""
    kompaniya_nomi = models.CharField(max_length=200, default="«Soar Gaz Building» MChJ")
    stir = models.CharField('STIR (INN)', max_length=30, blank=True)
    manzil = models.CharField('Kompaniya manzili', max_length=250, blank=True)
    telefon = models.CharField('Kompaniya telefoni', max_length=40, blank=True)
    bank_nomi = models.CharField(max_length=120, blank=True)
    hisob_raqam = models.CharField('Hisob raqami', max_length=40, blank=True)
    mfo = models.CharField('MFO', max_length=10, blank=True)
    direktor = models.CharField('Direktor', max_length=120, blank=True)
    servis_boshligi = models.CharField(
        "Servis xizmat ko'rsatish bo'limi boshlig'i", max_length=120, blank=True,
        help_text="Kvitansiya pastida chiqadi")
    kvitansiya_izoh = models.CharField(
        "Kvitansiya pastidagi izoh", max_length=300, blank=True,
        help_text="Masalan: «Kvitansiyani saqlab qo'ying»")
    shartnoma_matni = models.TextField(
        default=SHARTNOMA_NAMUNA,
        help_text="Quyidagi o'rinlar avtomatik to'ldiriladi: {raqam} {sana} {kompaniya} {mijoz_ism} "
                  "{mijoz_telefon} {manzil} {xizmatlar} {summa} {xodim}")
    shartnoma_tasdiqlangan = models.BooleanField(
        "Shartnoma matni tasdiqlangan", default=False,
        help_text="Yuridik matn kiritilib, direktor tasdiqlamaguncha xodimlar shartnoma tuza olmaydi")
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hujjat sozlamasi'
        verbose_name_plural = 'Hujjat sozlamalari'

    def __str__(self):
        return 'Hujjat sozlamasi'

    @classmethod
    def olish(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Hisoblagich(models.Model):
    turi = models.CharField(max_length=12)
    yil = models.PositiveSmallIntegerField()
    oxirgi = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('turi', 'yil')]


PREFIKS = {'kvitansiya': 'KV', 'shartnoma': 'SH'}


def raqam_ber(turi):
    """Yil ichida ketma-ket raqam: KV-2026-000001. Bitta tranzaksiyada hisoblagich oshiriladi."""
    yil = timezone.localtime().year
    with transaction.atomic():
        h, _ = Hisoblagich.objects.get_or_create(turi=turi, yil=yil)
        Hisoblagich.objects.filter(pk=h.pk).update(oxirgi=F('oxirgi') + 1)
        h.refresh_from_db()
    return f'{PREFIKS[turi]}-{yil}-{h.oxirgi:06d}'


def token_yasa():
    return secrets.token_urlsafe(12)


SMS_HOLATLAR = [
    ('kutilmoqda', 'Yuborilmagan'),
    ('yuborildi', 'Yuborildi'),
    ('xato', 'Yuborilmadi (xato)'),
]


class Kvitansiya(models.Model):
    tushum = models.OneToOneField('tushum.Tushum', on_delete=models.PROTECT, related_name='kvitansiya')
    raqam = models.CharField(max_length=20, unique=True)
    token = models.CharField(max_length=24, unique=True, default=token_yasa)
    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='kvitansiyalar')
    # Kvitansiyaga yozilgan mijoz ro'yxatga olinadi (hisobi bo'lmasa avtomatik ochiladi)
    mijoz = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='kvitansiyalari')
    yangi_mijoz = models.BooleanField('Shu kvitansiya bilan ro\'yxatga olingan', default=False)
    # Mijoz ma'lumoti hujjat tuzilgan paytdagi qiymatda saqlanadi
    mijoz_ism = models.CharField(max_length=120)
    mijoz_telefon = models.CharField(max_length=20)
    manzil = models.CharField('Turar joy', max_length=300)
    buyurtma_id = models.PositiveIntegerField(null=True, blank=True)
    shartnoma_raqami = models.CharField('Kod (shartnoma raqami)', max_length=20, blank=True)
    # Qog'oz kvitansiyadagi jadval: [{raqam, nomi, ustun_nomi, soni, narx, jami}] (tuzilgan paytdagi qiymat)
    qatorlar = models.JSONField(default=list)
    buyurtma_summa = models.BigIntegerField('Buyurtmaning umumiy summasi', null=True, blank=True)
    ish_turi = models.CharField(max_length=450, blank=True)
    summa = models.BigIntegerField()
    usul_nomi = models.CharField(max_length=40)
    izoh = models.CharField(max_length=255, blank=True)
    holat = models.CharField(max_length=6, default='amal', choices=[('amal', 'Amalda'), ('bekor', 'Bekor qilingan')])
    bekor_sababi = models.CharField(max_length=255, blank=True)
    bekor_vaqti = models.DateTimeField(null=True, blank=True)
    bekor_qilgan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name='+')
    sms_holat = models.CharField(max_length=10, choices=SMS_HOLATLAR, default='kutilmoqda')
    sms_vaqti = models.DateTimeField(null=True, blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-yaratilgan']
        verbose_name = 'Kvitansiya'
        verbose_name_plural = 'Kvitansiyalar'
        permissions = [('kvitansiya_bekor', 'Kvitansiyani bekor qilish')]

    def __str__(self):
        return f'{self.raqam} — {self.mijoz_ism}, {self.summa} so\'m'


SHARTNOMA_HOLATLAR = [
    ('qoralama', 'Tuzildi (tasdiqlanmagan)'),
    ('tasdiq_kutilmoqda', 'SMS kod yuborildi'),
    ('tasdiqlandi', 'Mijoz SMS kod bilan tasdiqladi'),
    ('qogoz', "Qog'ozga imzolandi"),
    ('bekor', 'Bekor qilingan'),
]


class Shartnoma(models.Model):
    buyurtma = models.ForeignKey('buyurtmalar.Buyurtma', on_delete=models.PROTECT, related_name='shartnomalar')
    raqam = models.CharField(max_length=20, unique=True)
    token = models.CharField(max_length=24, unique=True, default=token_yasa)
    xodim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='shartnomalar')
    mijoz = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='shartnomalari')
    mijoz_ism = models.CharField(max_length=120)
    mijoz_telefon = models.CharField(max_length=20)
    manzil = models.CharField('Turar joy', max_length=300)
    # Tuzilgan paytdagi xizmatlar: [{nomi, ustun_nomi, soni, narx_dan, narx_gacha}]
    xizmatlar = models.JSONField(default=list)
    summa = models.BigIntegerField()
    matn = models.TextField()
    holat = models.CharField(max_length=20, choices=SHARTNOMA_HOLATLAR, default='qoralama')
    # SMS tasdiqlash kodi: kodning o'zi saqlanmaydi, faqat imzolangan xesh
    kod_xesh = models.CharField(max_length=64, blank=True)
    kod_vaqti = models.DateTimeField(null=True, blank=True)
    kod_urinish = models.PositiveSmallIntegerField(default=0)
    tasdiq_vaqti = models.DateTimeField(null=True, blank=True)
    bekor_sababi = models.CharField(max_length=255, blank=True)
    bekor_vaqti = models.DateTimeField(null=True, blank=True)
    yaratilgan = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-yaratilgan']
        verbose_name = 'Shartnoma'
        verbose_name_plural = 'Shartnomalar'
        permissions = [('shartnoma_bekor', 'Shartnomani bekor qilish')]
        constraints = [
            # Bitta buyurtmada bir vaqtda faqat bitta amaldagi shartnoma (bekor qilinganlari hisobga kirmaydi)
            models.UniqueConstraint(fields=['buyurtma'], condition=~Q(holat='bekor'),
                                    name='buyurtmada_bitta_amaldagi_shartnoma'),
        ]

    def __str__(self):
        return f'{self.raqam} — {self.mijoz_ism}'

    @property
    def tasdiqlanganmi(self):
        return self.holat in ('tasdiqlandi', 'qogoz')


class HujjatLoyiha(models.Model):
    """Mijozdan kelgan ish (metrologiya arizasi yoki loyiha/metrologiya buyurtmasi) uchun TAYYORLANGAN hujjat.

    Hujjatlar bilan ishlovchi xodim (hujjat turi kabineti) faylni yuklaydi — u «tayyor» turadi, mijoz ko'rmaydi.
    «Mijozga yuborish» bosilganda mijoz kabinetidagi «Hujjatlar»ga (`kabinet.Hujjat`) qo'shiladi va mijozga SMS
    ketadi. Yuborilgan hujjat o'chirilmaydi (qachon, kim yuborgani qoladi)."""

    ariza = models.ForeignKey('tolovlar.MetrologiyaArizasi', on_delete=models.CASCADE, null=True, blank=True,
                              related_name='hujjat_loyihalari', verbose_name='Metrologiya arizasi')
    buyurtma = models.ForeignKey('buyurtmalar.Buyurtma', on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='hujjat_loyihalari', verbose_name='Buyurtma')
    nom = models.CharField(max_length=200, verbose_name='Hujjat nomi')
    turi = models.CharField(max_length=20, default='boshqa', verbose_name='Hujjat turi')
    izoh = models.CharField(max_length=255, blank=True, verbose_name='Izoh')
    fayl = models.FileField(upload_to='hujjat_loyihalar/', verbose_name='Fayl')
    tayyorlagan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+', verbose_name='Tayyorladi')
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yuborilgan = models.DateTimeField(null=True, blank=True, verbose_name='Mijozga yuborilgan vaqt')
    yuborgan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='+', verbose_name='Yubordi')
    mijoz_hujjati = models.OneToOneField('kabinet.Hujjat', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='+', verbose_name='Mijoz kabinetidagi hujjat')

    class Meta:
        verbose_name = 'Tayyorlangan hujjat'
        verbose_name_plural = 'Tayyorlangan hujjatlar'
        ordering = ['-yaratilgan']
        constraints = [models.CheckConstraint(
            check=(Q(ariza__isnull=False, buyurtma__isnull=True) | Q(ariza__isnull=True, buyurtma__isnull=False)),
            name='hujjat_loyiha_bitta_manba')]

    def __str__(self):
        return self.nom


class Topshiriq(models.Model):
    """Ichki topshiriq: Kadrlar mutaxassisi va call-center xodimi hujjatlar bilan ishlovchi xodimga (Ferangiz)
    topshiriq yuboradi; hujjatchi o'ziga ham vazifa qo'sha oladi (`kim == kimga`).
    Bajarilganda natija fayli yuklanadi. Fayllar `hujjatlar_maxfiy/` ostida — nginx ularni ochiq bermaydi,
    faqat tekshiruvli endpoint (`topshiriq.fayl_olish`) orqali beriladi."""

    HOLATLAR = [('yangi', 'Yangi'), ('jarayonda', 'Jarayonda'), ('bajarildi', 'Bajarildi'), ('bekor', 'Bekor qilingan')]
    FAOL = ('yangi', 'jarayonda')

    sarlavha = models.CharField(max_length=200, verbose_name='Topshiriq')
    matn = models.TextField(blank=True, max_length=2000, verbose_name='Tafsilot')
    muddat = models.DateField(null=True, blank=True, verbose_name='Muddat')
    kim = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='+', verbose_name='Yubordi')
    kimga = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+',
                              verbose_name='Kimga')
    holat = models.CharField(max_length=12, choices=HOLATLAR, default='yangi', verbose_name='Holat')
    fayl = models.FileField(upload_to='hujjatlar_maxfiy/topshiriq/', blank=True, verbose_name='Biriktirilgan fayl')
    natija_fayl = models.FileField(upload_to='hujjatlar_maxfiy/topshiriq_natija/', blank=True,
                                   verbose_name='Natija fayli')
    natija_izoh = models.CharField(max_length=255, blank=True, verbose_name='Natija izohi')
    yaratilgan = models.DateTimeField(auto_now_add=True)
    bajarilgan = models.DateTimeField(null=True, blank=True, verbose_name='Bajarilgan vaqt')

    class Meta:
        verbose_name = 'Topshiriq'
        verbose_name_plural = 'Topshiriqlar'
        ordering = ['-yaratilgan']
        indexes = [models.Index(fields=['kimga', 'holat'])]

    def __str__(self):
        return self.sarlavha
