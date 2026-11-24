"""Xizmatlar narxnomasi (hujjat shaklidagi narxlar ro'yxati).

Katalogdagi mahsulot narxlaridan (apps.katalog.KatalogNarx) farqi: bu yerda
har qatorda IKKI narx ustuni bor (profilaktika va texnik ko'rik/reviziya),
narx esa oraliq bo'lishi mumkin (masalan «210 000 – 330 000») yoki matn
(«ish hajmi va kelishuv asosida»).

Narxlarni administrator boshqaruv panelidan o'zgartiradi, xodimlar portalida
esa faqat ko'rishadi. Har o'zgarish Faoliyat jurnaliga yoziladi.
"""
from django.db import models


#  Xizmat tarmoqlari. Tarmoq narxnomaga TEGISHLI: narxlar tarmoqqa qarab farq qiladi.
#  Buyurtma o'z tarmog'ini oladi (`Buyurtma.tarmoq`) va faqat shu tarmoq
#  narxnomalaridan xizmat tanlanadi; tushum tarmoq va bo'limni tanlangan ish
#  turidan (yoki buyurtmadan) meros qiladi — hisobotlar tarmoq bo'yicha ajraladi.
TARMOQ_CHOICES = [
    ('ulgurji', 'Ulgurji (sanoat, kichik va o\'rta biznes)'),
    ('aholi', 'Aholi'),
]
BOLIM_CHOICES = [
    ('buyurtma', 'Buyurtma asosida'),
    ('profilaktika', "Profilaktika va texnik ko'rik"),
    ('ornatish', "Yangi jihoz o'rnatib ishga tushirish"),
    ('metrologiya', 'Metrologiya xizmatlari'),
]
# Saytdagi Metrologiya bo'limining qaysi xizmatida narx ko'rinishi (qator darajasida)
SAYT_XIZMAT_CHOICES = [
    ('', "Saytda ko'rsatilmaydi"),
    ('kalibrovka', 'Kalibrovka'),
    ('almashtirish', 'Almashtirish'),
    ('qiyoslov', "Davlat qiyoslov ko'rigi"),
]
TARMOQ_NOMI = dict(TARMOQ_CHOICES)
BOLIM_NOMI = dict(BOLIM_CHOICES)


class Narxnoma(models.Model):
    tarmoq = models.CharField(max_length=10, choices=TARMOQ_CHOICES, default='ulgurji', db_index=True)
    bolim = models.CharField(max_length=15, choices=BOLIM_CHOICES, default='profilaktika')
    tartib = models.PositiveSmallIntegerField(default=0, help_text="Ro'yxatdagi o'rni")
    sarlavha = models.CharField(max_length=300)
    tavsif = models.CharField(max_length=300, blank=True)
    amal_qiladi = models.DateField(null=True, blank=True, verbose_name='Amal qilish sanasi')
    # Narx ustunlari. 2-ustun bo'sh bo'lsa, narxnomada faqat bitta narx bor
    # (masalan «Buyurtma asosida» yoki «O'rnatish va ishga tushirish»).
    ustun1 = models.CharField(max_length=200, verbose_name='1-narx ustuni nomi')
    ustun1_qisqa = models.CharField(
        max_length=40, blank=True,
        help_text="Tanlangan xizmat yonida ko'rinadi, masalan «profilaktika». Bo'sh bo'lsa ko'rsatilmaydi")
    ustun2 = models.CharField(max_length=200, blank=True, verbose_name='2-narx ustuni nomi')
    ustun2_qisqa = models.CharField(max_length=40, blank=True)
    eslatma = models.TextField(blank=True)
    faol = models.BooleanField(default=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Narxnoma'
        verbose_name_plural = 'Narxnomalar'
        ordering = ['tartib', 'id']
        constraints = [models.UniqueConstraint(fields=['tarmoq', 'bolim'], name='narxnoma_tarmoq_bolim_yagona')]

    def __str__(self):
        return f'{self.tarmoq_nomi} — {self.bolim_nomi}'

    @property
    def tarmoq_nomi(self):
        return TARMOQ_NOMI.get(self.tarmoq, self.tarmoq)

    @property
    def bolim_nomi(self):
        return BOLIM_NOMI.get(self.bolim, self.bolim)

    def ustun_qisqa(self, ustun):
        """'p' / 'r' ustunining qisqa nomi (bo'sh bo'lishi mumkin)."""
        return self.ustun1_qisqa if ustun == 'p' else self.ustun2_qisqa

    def ustun_bormi(self, ustun):
        return bool(self.ustun1) if ustun == 'p' else bool(self.ustun2)


class NarxnomaQator(models.Model):
    narxnoma = models.ForeignKey(Narxnoma, on_delete=models.CASCADE, related_name='qatorlar')
    tartib = models.PositiveIntegerField(help_text='Hujjatdagi tartib raqami (№)')
    nomi = models.CharField(max_length=400)
    # 1-ustun (profilaktika). Bitta narx bo'lsa faqat `p_dan`; oraliq bo'lsa `p_dan` va `p_gacha`
    p_dan = models.BigIntegerField(null=True, blank=True)
    p_gacha = models.BigIntegerField(null=True, blank=True)
    # 2-ustun (texnik ko'rik / reviziya)
    r_dan = models.BigIntegerField(null=True, blank=True)
    r_gacha = models.BigIntegerField(null=True, blank=True)
    # Raqam o'rnida matn kerak bo'lsa («ish hajmi va kelishuv asosida»)
    izoh = models.CharField(max_length=255, blank=True)
    # Faqat «Metrologiya» narxnomalari uchun: shu qator saytdagi qaysi xizmat oynasida ko'rinadi.
    # Bo'sh bo'lsa — saytda chiqmaydi (xodimlar portalida esa avvalgidek ko'rinadi).
    sayt_xizmat = models.CharField(
        max_length=20, blank=True, default='', choices=SAYT_XIZMAT_CHOICES,
        verbose_name="Saytdagi xizmat",
        help_text="Metrologiya narxnomasi: narx saytning qaysi xizmat oynasida ko'rinadi")
    faol = models.BooleanField(default=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Narxnoma qatori'
        verbose_name_plural = 'Narxnoma qatorlari'
        ordering = ['tartib', 'id']

    def __str__(self):
        return f"{self.tartib}. {self.nomi[:60]}"


# ──────────────────────────────────────────────────────────────
#  Seshanba aksiyasi: har seshanba 2 ta servis xizmatiga chegirma (promokod bilan)
# ──────────────────────────────────────────────────────────────
# Seshanba aksiyasi faqat shu narxnoma bo'limlaridagi xizmatlarga (servis)
SERVIS_BOLIMLARI = ('profilaktika', 'buyurtma')


class SeshanbaAksiya(models.Model):
    """Navbatdagi juftlik: bitta xizmat AHOLI uchun, bittasi ULGURJI (korxona) uchun.
    Har seshanba navbat bo'yicha keyingisi amal qiladi: 1-yozuv → birinchi seshanba, 2-yozuv → keyingi
    seshanba va h.k., oxiridan keyin yana boshidan. Faqat xizmatlar uchun (do'kon mahsulotlariga emas).
    Chegirma foizi va promokod — settings da."""
    tartib = models.PositiveSmallIntegerField(default=1, verbose_name='Navbat raqami')
    xizmat1 = models.ForeignKey(NarxnomaQator, on_delete=models.PROTECT, related_name='+',
                                verbose_name='Aholi uchun xizmat',
                                limit_choices_to={'narxnoma__tarmoq': 'aholi'})
    xizmat2 = models.ForeignKey(NarxnomaQator, on_delete=models.PROTECT, related_name='+',
                                verbose_name='Ulgurji (korxona) uchun xizmat',
                                limit_choices_to={'narxnoma__tarmoq': 'ulgurji'})
    faol = models.BooleanField(default=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tartib', 'id']
        verbose_name = 'Seshanba aksiyasi (navbat)'
        verbose_name_plural = 'Seshanba aksiyasi — navbat'

    def __str__(self):
        return f'{self.tartib}-navbat: {self.xizmat1.nomi[:40]} + {self.xizmat2.nomi[:40]}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.xizmat1_id and self.xizmat1.narxnoma.tarmoq != 'aholi':
            raise ValidationError({'xizmat1': 'Aholi narxnomasidan tanlang'})
        if self.xizmat2_id and self.xizmat2.narxnoma.tarmoq != 'ulgurji':
            raise ValidationError({'xizmat2': 'Ulgurji (korxona) narxnomasidan tanlang'})
        if self.xizmat1_id and self.xizmat1_id == self.xizmat2_id:
            raise ValidationError('Ikki xil xizmat tanlang')

    def qatorlar(self):
        return [self.xizmat1, self.xizmat2]

    def qator_idlari(self):
        """Chegirma qo'llanadigan barcha faol qatorlar. Aholi xizmati — faqat AHOLI servis narxnomalaridagi
        (profilaktika, buyurtma) shu nomli qatorlar; ulgurji xizmati — faqat ULGURJI servis narxnomalaridagi.
        Ya'ni aholining chegirmasi korxonaga, korxonaniki aholiga tushmaydi. O'rnatish va metrologiya
        narxnomalaridagi bir xil nomli qatorlarga ham tushmaydi — aksiya faqat servis uchun."""
        from django.db.models import Q
        shart = (Q(nomi__iexact=self.xizmat1.nomi.strip(), narxnoma__tarmoq='aholi')
                 | Q(nomi__iexact=self.xizmat2.nomi.strip(), narxnoma__tarmoq='ulgurji'))
        return sorted(set(NarxnomaQator.objects.filter(shart, faol=True, narxnoma__bolim__in=SERVIS_BOLIMLARI)
                          .values_list('id', flat=True)) | {self.xizmat1_id, self.xizmat2_id})


def seshanba_aksiyasi(sana):
    """Shu sanada amal qiladigan juftlik (seshanba bo'lmasa yoki navbat bo'sh bo'lsa — None)."""
    import datetime
    from django.conf import settings
    if sana.weekday() != 1:                       # 0 — dushanba, 1 — seshanba
        return None
    boshlanish = getattr(settings, 'SESHANBA_BOSHLANISH', datetime.date(2026, 11, 24))
    if sana < boshlanish:
        return None
    navbat = list(SeshanbaAksiya.objects.filter(faol=True).select_related('xizmat1__narxnoma', 'xizmat2__narxnoma'))
    if not navbat:
        return None
    return navbat[((sana - boshlanish).days // 7) % len(navbat)]


def keyingi_seshanba(sana):
    """Bugun seshanba bo'lsa — bugun, aks holda keyingi seshanba."""
    import datetime
    return sana + datetime.timedelta(days=(1 - sana.weekday()) % 7)


def promokod_oynasi(hozir=None):
    """Promokod amal qiladigan oyna: seshanba 00:00 dan SESHANBA_SOAT soat (standart 50 —
    payshanba 02:00 gacha, Toshkent vaqti). Qaytaradi: (seshanba_sanasi, boshlanish, tugash, amaldami).
    Oyna yopiq bo'lsa — keyingi seshanbaning oynasi."""
    import datetime
    from django.conf import settings
    from django.utils import timezone
    hozir = timezone.localtime(hozir)
    soat = getattr(settings, 'SESHANBA_SOAT', 50)
    oxirgi = hozir.date() - datetime.timedelta(days=(hozir.weekday() - 1) % 7)   # oxirgi seshanba (yoki bugun)
    boshi = timezone.make_aware(datetime.datetime.combine(oxirgi, datetime.time.min))
    if boshi <= hozir < boshi + datetime.timedelta(hours=soat):
        return oxirgi, boshi, boshi + datetime.timedelta(hours=soat), True
    keyingi = oxirgi + datetime.timedelta(days=7)
    kboshi = timezone.make_aware(datetime.datetime.combine(keyingi, datetime.time.min))
    return keyingi, kboshi, kboshi + datetime.timedelta(hours=soat), False


def amaldagi_aksiya(hozir=None):
    """Hozir promokod amal qilsa — o'sha seshanbaning juftligi, aks holda None."""
    sana, _b, _t, amalda = promokod_oynasi(hozir)
    return seshanba_aksiyasi(sana) if amalda else None
