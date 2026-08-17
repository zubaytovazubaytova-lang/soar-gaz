import secrets

from django.db import models
from django.conf import settings
from django.utils import timezone

# ──────────────────────────────────────────────────────────────
#  Xaridlar (internet-do'kon) buyurtmalari.
#  Xizmat buyurtmalari (apps.buyurtmalar.Buyurtma) dan alohida:
#  bu yerda savat qatorlari, yetkazish va to'lov usuli bor.
#  Holat kodlari xaridlar-app/lib/types.ts dagi OrderStatus bilan bir xil.
# ──────────────────────────────────────────────────────────────

HOLAT_CHOICES = [
    ('qabul_qilindi', 'Qabul qilindi'),
    ('tasdiqlandi', 'Tasdiqlandi'),
    ('tayyorlanmoqda', 'Tayyorlanmoqda'),
    ('jonatildi', "Jo'natildi"),
    ('yolda', "Yo'lda"),
    ('muammo', "Yetkazib bo'lmadi"),
    ('yetkazildi', 'Yetkazildi'),
    ('bekor', 'Bekor qilindi'),
]

# Yetkazib berishda uchraydigan muammolar
MUAMMO_CHOICES = [
    ('javob_bermadi', 'Mijoz javob bermadi'),
    ('manzil_topilmadi', 'Manzil topilmadi'),
    ('rad_etdi', 'Mijoz qabul qilishdan bosh tortdi'),
    ('vaqt_mos_emas', 'Vaqt mos kelmadi'),
    ('boshqa', 'Boshqa sabab'),
]

MUAMMO_SMS = {
    'javob_bermadi': "kuryer siz bilan bog'lana olmadi. Iltimos, biz bilan bog'laning yoki saytdan qayta yetkazishni so'rang.",
    'manzil_topilmadi': "kuryer manzilni topa olmadi. Iltimos, manzilni aniqlashtiring.",
    'rad_etdi': "buyurtma qabul qilinmadi. Savolingiz bo'lsa bog'laning.",
    'vaqt_mos_emas': "yetkazish vaqti mos kelmadi. Qulay vaqtni saytdan tanlang.",
    'boshqa': "buyurtmani yetkazib bo'lmadi. Operator siz bilan bog'lanadi.",
}

# Buyurtma normal oqimi (bekor qilish bundan tashqarida)
HOLAT_OQIMI = ['qabul_qilindi', 'tasdiqlandi', 'tayyorlanmoqda',
               'jonatildi', 'yolda', 'yetkazildi']

# Holat o'zgarganda mijozga yuboriladigan SMS matnlari
HOLAT_SMS = {
    'tasdiqlandi':    "buyurtmangiz tasdiqlandi. Tayyorlashni boshladik.",
    'tayyorlanmoqda': "buyurtmangiz tayyorlanmoqda.",
    'jonatildi':      "buyurtmangiz ombordan jo'natildi.",
    'yolda':          "kuryer yo'lga chiqdi! Holatni saytdan kuzatishingiz mumkin.",
    'yetkazildi':     "buyurtmangiz yetkazib berildi. Xaridingiz uchun rahmat!",
    'bekor':          "buyurtmangiz bekor qilindi. Savolingiz bo'lsa bog'laning.",
}

# Kuryer joylashuvi ko'rsatiladigan holatlar
KURYER_HOLATLARI = {'jonatildi', 'yolda'}

YETKAZISH_CHOICES = [
    ('kuryer', 'Kuryer yetkazadi'),
    ('filialdan', 'Filialdan olib ketish'),
]

TOLOV_USULI_CHOICES = [
    ('naqd', 'Naqd (yetkazishda) — COD'),
    ('click', 'Click'),
    ('payme', 'Payme'),
    ('karta', 'Uzcard / Humo'),
    ('bolib', "Bo'lib to'lash"),
]

# Onlayn to'lov havolasi quriladigan usullar.
# 'karta' (Uzcard/Humo) provayder checkout sahifasi orqali o'tadi —
# qaysi provayder ishlatilishi settings.KARTA_PROVAYDER da belgilanadi.
ONLAYN_USULLAR = {'click', 'payme', 'karta'}

TOLOV_HOLAT_CHOICES = [
    ('kutilmoqda', 'To\'lov kutilmoqda'),
    ('tolandi', 'To\'landi'),
    ('xato', 'To\'lov amalga oshmadi'),
    ('bekor', 'Bekor qilindi'),
]


class Xarid(models.Model):
    raqam = models.CharField(max_length=20, unique=True, db_index=True)
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='xaridlari', null=True, blank=True
    )

    ism = models.CharField(max_length=120)
    telefon = models.CharField(max_length=30, db_index=True)
    manzil = models.CharField(max_length=255, blank=True)

    yetkazish = models.CharField(max_length=20, choices=YETKAZISH_CHOICES, default='kuryer')
    yetkazish_izohi = models.TextField(blank=True)
    # Mijoz tanlagan yetkazish vaqti, masalan "Ertaga, 09:00–12:00"
    yetkazish_vaqti = models.CharField(max_length=80, blank=True)
    # Hudud — narx va muddat shunga qarab hisoblanadi
    tuman = models.CharField(max_length=60, blank=True, db_index=True)
    yetkazish_muddati = models.CharField(max_length=60, blank=True)

    # ── Yetkazib berishdagi muammo ──
    muammo = models.CharField(max_length=20, choices=MUAMMO_CHOICES, blank=True)
    muammo_izohi = models.TextField(blank=True)
    muammo_vaqti = models.DateTimeField(null=True, blank=True)
    urinish_soni = models.PositiveIntegerField(default=0)
    tolov_usuli = models.CharField(max_length=20, choices=TOLOV_USULI_CHOICES, default='naqd')
    ornatish_xizmati = models.BooleanField(default=False)

    # ── Bo'lib to'lash ──
    bolib_oy = models.PositiveIntegerField(default=0, help_text="0 — bo'lib to'lash tanlanmagan")
    oylik_tolov = models.BigIntegerField(default=0)
    # ── To'lov holati (qayta urinishlarni kuzatish uchun) ──
    tolov_holati = models.CharField(max_length=20, choices=TOLOV_HOLAT_CHOICES,
                                    default='kutilmoqda', blank=True)
    tolov_urinishlari = models.PositiveIntegerField(default=0)

    # ── Summalar (barchasi so'mda, server tomonda hisoblanadi) ──
    mahsulotlar_summasi = models.BigIntegerField(default=0)
    chegirma = models.BigIntegerField(default=0)
    promokod = models.CharField(max_length=40, blank=True)
    yetkazish_narxi = models.BigIntegerField(default=0)
    ornatish_narxi = models.BigIntegerField(default=0)
    jami = models.BigIntegerField(default=0)

    holat = models.CharField(max_length=20, choices=HOLAT_CHOICES, default='qabul_qilindi')
    tolandi = models.BooleanField(default=False)

    # Onlayn to'lov uchun tolovlar.TolovSorovi bilan bog'lanish
    tolov_sorovi = models.ForeignKey(
        'tolovlar.TolovSorovi', on_delete=models.SET_NULL,
        related_name='xaridlari', null=True, blank=True
    )

    # ── Kuryer va uning joylashuvi ──
    kuryer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='yetkazadigan_xaridlar', null=True, blank=True
    )
    kuryer_lat = models.FloatField(null=True, blank=True)
    kuryer_lng = models.FloatField(null=True, blank=True)
    kuryer_yangilangan = models.DateTimeField(null=True, blank=True)
    # Yetkazish manzilining koordinatasi (xaritada nishon sifatida)
    manzil_lat = models.FloatField(null=True, blank=True)
    manzil_lng = models.FloatField(null=True, blank=True)

    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Xarid buyurtmasi'
        verbose_name_plural = 'Xarid buyurtmalari'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.raqam} — {self.ism} ({self.get_holat_display()})"

    # Chalkashadigan belgilar (0/O, 1/I/L) ataylab yo'q — raqam telefonda
    # aytiladi va chekka yoziladi.
    RAQAM_ALIFBOSI = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'
    RAQAM_UZUNLIGI = 6

    @staticmethod
    def raqam_yasash():
        """Noyob buyurtma raqami: SG-<yil2><oy2>-<tasodifiy>.

        Ilgari oxirgi qism ketma-ket edi (`SG-2607-0001`, `-0002`, ...). Buyurtma
        sahifasi va to'lov/qayta yetkazish amallari esa raqamni bilishning o'zini
        egalik dalili deb qabul qiladi — ya'ni raqamlarni sanab chiqib begona
        buyurtmani ochish va o'zgartirish mumkin edi. Tasodifiy qism buni
        to'xtatadi (31^6 ≈ 887 mln variant).

        Eski ketma-ket raqamlar o'z holicha ishlashda davom etadi.
        """
        now = timezone.localtime()
        prefiks = f"SG-{now:%y%m}-"
        while True:
            tasodifiy = ''.join(
                secrets.choice(Xarid.RAQAM_ALIFBOSI)
                for _ in range(Xarid.RAQAM_UZUNLIGI)
            )
            raqam = f"{prefiks}{tasodifiy}"
            if not Xarid.objects.filter(raqam=raqam).exists():
                return raqam

    def save(self, *args, **kwargs):
        if not self.raqam:
            self.raqam = self.raqam_yasash()
        super().save(*args, **kwargs)


class XaridQatori(models.Model):
    xarid = models.ForeignKey(Xarid, on_delete=models.CASCADE, related_name='qatorlar')
    mahsulot_id = models.CharField(max_length=60)
    slug = models.SlugField(max_length=160)
    nomi = models.CharField(max_length=200)
    narx = models.BigIntegerField(default=0)
    miqdor = models.PositiveIntegerField(default=1)
    # Mahsulot ko'rinishi: rasm URL yoki Font Awesome ikonka nomi ("fa-fire")
    rasm = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'Xarid qatori'
        verbose_name_plural = 'Xarid qatorlari'
        ordering = ['id']

    def __str__(self):
        return f"{self.nomi} ×{self.miqdor}"

    @property
    def summa(self):
        return self.narx * self.miqdor


# ──────────────────────────────────────────────────────────────
#  Promokodlar
# ──────────────────────────────────────────────────────────────

CHEGIRMA_TURI_CHOICES = [
    ('foiz', 'Foiz (%)'),
    ('summa', "Qat'iy summa (so'm)"),
]


class Promokod(models.Model):
    kod = models.CharField(max_length=40, unique=True)
    tavsif = models.CharField(max_length=200, blank=True)
    tur = models.CharField(max_length=10, choices=CHEGIRMA_TURI_CHOICES, default='foiz')
    qiymat = models.PositiveIntegerField(help_text="Foiz uchun 1–100, summa uchun so'm")
    eng_kam_summa = models.BigIntegerField(
        default=0, help_text="Shu summadan kam buyurtmaga qo'llanmaydi (0 — cheklovsiz)")
    eng_kop_chegirma = models.BigIntegerField(
        default=0, help_text="Foizli chegirma uchun yuqori chegara (0 — cheksiz)")
    boshlanish = models.DateTimeField(null=True, blank=True)
    tugash = models.DateTimeField(null=True, blank=True)
    limit = models.PositiveIntegerField(default=0, help_text='Necha marta ishlatilishi mumkin (0 — cheksiz)')
    ishlatilgan = models.PositiveIntegerField(default=0)
    faol = models.BooleanField(default=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Promokod'
        verbose_name_plural = 'Promokodlar'
        ordering = ['-yaratilgan']

    def __str__(self):
        belgi = '%' if self.tur == 'foiz' else "so'm"
        return f"{self.kod} — {self.qiymat}{belgi}"

    def save(self, *args, **kwargs):
        self.kod = self.kod.strip().upper()
        super().save(*args, **kwargs)

    def tekshir(self, summa):
        """(chegirma, xato_matni) qaytaradi. Xato bo'lsa chegirma = 0."""
        from django.utils import timezone
        hozir = timezone.now()

        if not self.faol:
            return 0, 'Bu promokod faol emas'
        if self.boshlanish and hozir < self.boshlanish:
            return 0, 'Promokod hali ishga tushmagan'
        if self.tugash and hozir > self.tugash:
            return 0, 'Promokod muddati tugagan'
        if self.limit and self.ishlatilgan >= self.limit:
            return 0, 'Promokod ishlatilish limiti tugagan'
        if self.eng_kam_summa and summa < self.eng_kam_summa:
            kerak = f"{self.eng_kam_summa:,}".replace(',', ' ')
            return 0, f"Bu promokod {kerak} so'mdan yuqori buyurtmalarga amal qiladi"

        if self.tur == 'foiz':
            chegirma = summa * min(self.qiymat, 100) // 100
            if self.eng_kop_chegirma:
                chegirma = min(chegirma, self.eng_kop_chegirma)
        else:
            chegirma = self.qiymat

        # Chegirma buyurtma summasidan oshmasin
        return min(chegirma, summa), ''
