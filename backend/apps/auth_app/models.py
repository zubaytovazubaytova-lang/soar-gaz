import secrets

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


def kirish_kodi_yasa(uzunlik=6):
    """Xodim uchun takrorlanmaydigan kirish kodi.

    `secrets` ishlatiladi (`random` emas): kod — parolning o'rnini bosadi,
    shuning uchun taxmin qilib bo'lmaydigan bo'lishi kerak. Chalkashadigan
    belgilar (0/O, 1/I) chiqarib tashlangan — kod og'zaki aytiladi.

    Format: `XD-` + 6 belgi (masalan XD-K7M4PQ). Mijozlarning bir martalik SMS
    kodi esa faqat 6 ta raqam — ikkalasi hech qachon adashmaydi.
    """
    ALIFBO = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
    return 'XD-' + ''.join(secrets.choice(ALIFBO) for _ in range(uzunlik))


# Hududlar ro'yxati alohida faylda — u yerda 14 ta viloyat va 203 ta
# tuman/shahar viloyatlar bo'yicha guruhlangan holda turadi.
from .hududlar import HUDUDLAR, TUMANLAR  # noqa: F401  (eski nom saqlanadi)

ROL_CHOICES = [
    ('admin', 'Admin'),
    ('mijoz', 'Mijoz'),
    ('xodim', 'Xodim'),
]

HOLAT_CHOICES = [
    ('faol', 'Faol'),
    ('nofaol', 'Nofaol'),
]

# Xodim lavozimlari — xodimlar portalida ko'rsatiladi
LAVOZIM_CHOICES = [
    ('Montaj ustasi', 'Montaj ustasi'),
    ('Katta montaj ustasi', 'Katta montaj ustasi'),
    ('Loyihachi muhandis', 'Loyihachi muhandis'),
    ('Metrolog', 'Metrolog'),
    ("Mehnat muhofazasi va texnika xavfsizligi bo'yicha muhandis", "Mehnat muhofazasi va texnika xavfsizligi bo'yicha muhandis"),
    ('Call center operatori', 'Call center operatori'),
    ("Kadrlar bo'yicha mutaxassis", "Kadrlar bo'yicha mutaxassis"),
]


class FoydalanuvchiManager(BaseUserManager):
    def create_user(self, telefon, password=None, **extra_fields):
        if not telefon:
            raise ValueError('Telefon raqam kiritilishi shart')
        user = self.model(telefon=telefon, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, telefon, password=None, **extra_fields):
        extra_fields.setdefault('rol', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(telefon, password, **extra_fields)


MULK_CHOICES = [
    ('uy', 'Xususiy uy'),
    ('kvartira', 'Kvartira'),
    ('korxona', 'Korxona / tashkilot'),
]


class Foydalanuvchi(AbstractBaseUser, PermissionsMixin):
    telefon = models.CharField(max_length=20, unique=True)
    ism = models.CharField(max_length=100, blank=True)
    manzil = models.CharField(max_length=255, blank=True)
    # ---- Joylashuv ----
    # Viloyat va tuman ro'yxatdan TANLANADI (hududlar.py), mahalla/ko'cha esa
    # qo'lda yoziladi — ular juda ko'p va o'zgaruvchan, ro'yxat tuzib
    # bo'lmaydi. `choices` ataylab qo'yilmagan: tekshiruv forma va serializer
    # darajasida bo'ladi, model esa eski va qo'lda kiritilgan qiymatlarni ham
    # saqlay olishi kerak.
    viloyat = models.CharField(max_length=50, blank=True)
    tuman = models.CharField(max_length=50, blank=True)
    mahalla = models.CharField(max_length=120, blank=True,
                               verbose_name="Mahalla / ko'cha")
    # Mijoz profili — kabinetda to'ldiriladi
    qoshimcha_telefon = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    mulk_turi = models.CharField(max_length=15, choices=MULK_CHOICES, blank=True)
    moljal = models.CharField(max_length=255, blank=True, verbose_name="Mo'ljal")
    # Xodim profili — faqat Django admin panelida to'ldiriladi
    # `choices` yo'q — yuqoridagi `tuman` bilan bir xil sabab: yangi lavozim
    # paydo bo'lishi mumkin, LAVOZIM_CHOICES esa taklif ro'yxati bo'lib qoladi.
    lavozim = models.CharField(max_length=100, blank=True)
    # Xodim portalga TELEFON + shu KOD bilan kiradi (parol emas). Kodni admin
    # beradi va istalgan vaqtda yangilaydi. Mijozlarda bu maydon bo'sh turadi —
    # ular SMS orqali bir martalik kod bilan kiradi.
    kirish_kodi = models.CharField(max_length=12, blank=True, db_index=True,
                                   verbose_name='Kirish kodi')
    tabel_raqam = models.CharField(max_length=20, blank=True, verbose_name='Tabel raqami')
    ishga_kirgan = models.DateField(null=True, blank=True, verbose_name='Ishga kirgan sana')
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='mijoz')
    holat = models.CharField(max_length=10, choices=HOLAT_CHOICES, default='faol')
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'telefon'
    REQUIRED_FIELDS = []

    objects = FoydalanuvchiManager()

    class Meta:
        verbose_name = 'Foydalanuvchi'
        verbose_name_plural = 'Foydalanuvchilar'

    def __str__(self):
        return f"{self.ism or self.telefon} ({self.rol})"

    @property
    def tuman_nomi(self):
        return self.tuman


class Sertifikat(models.Model):
    """Xodimning sertifikati / attestatsiyasi — admin panelida xodim sahifasidan kiritiladi,
    xodim kabinetida («Sertifikatlarim») faqat o'qiydi."""

    xodim = models.ForeignKey(Foydalanuvchi, on_delete=models.CASCADE,
                              related_name='sertifikatlar', verbose_name='Xodim')
    nomi = models.CharField(max_length=200, verbose_name='Sertifikat nomi')
    raqami = models.CharField(max_length=60, blank=True, verbose_name='Raqami')
    berilgan = models.DateField(null=True, blank=True, verbose_name='Berilgan sana')
    amal_qiladi = models.DateField(null=True, blank=True, verbose_name='Amal qilish muddati (gacha)',
                                   help_text="Bo'sh qoldirilsa — muddatsiz")

    class Meta:
        verbose_name = 'Sertifikat'
        verbose_name_plural = 'Sertifikatlar'
        ordering = ['amal_qiladi', 'nomi']

    def __str__(self):
        return f"{self.nomi} ({self.xodim})"

    # Muddati tugashiga shuncha kun qolganda xodimga ogohlantirish ko'rsatiladi
    OGOHLANTIRISH_KUN = 90

    @property
    def holat(self):
        """'muddatsiz' | 'amalda' | 'yaqin' (tez orada tugaydi) | 'tugagan'."""
        if self.amal_qiladi is None:
            return 'muddatsiz'
        qoldi = (self.amal_qiladi - timezone.localdate()).days
        if qoldi < 0:
            return 'tugagan'
        return 'yaqin' if qoldi <= self.OGOHLANTIRISH_KUN else 'amalda'


class IshHaqi(models.Model):
    """Xodimning oylik ish haqi yozuvi (oyiga bitta). Admin (tizim egasi) kiritadi;
    xodim FAQAT o'zinikini ko'radi. Bonus avtomatik hisoblanmaydi — qo'lda kiritiladi."""

    xodim = models.ForeignKey(Foydalanuvchi, on_delete=models.CASCADE,
                              related_name='ish_haqlari', verbose_name='Xodim')
    oy = models.DateField(verbose_name='Oy',
                          help_text="Oyning istalgan kuni — saqlashda 1-sanaga keltiriladi")
    asosiy = models.BigIntegerField(default=0, verbose_name="Asosiy oylik (so'm)")
    bonus = models.BigIntegerField(default=0, verbose_name="Bonus (so'm)")
    izoh = models.CharField(max_length=200, blank=True, verbose_name='Izoh')

    class Meta:
        verbose_name = 'Ish haqi'
        verbose_name_plural = 'Ish haqi'
        ordering = ['-oy']
        constraints = [models.UniqueConstraint(fields=['xodim', 'oy'], name='ish_haqi_oyiga_bitta')]

    def save(self, *args, **kwargs):
        self.oy = self.oy.replace(day=1)
        super().save(*args, **kwargs)

    @property
    def jami(self):
        return self.asosiy + self.bonus

    def __str__(self):
        return f"{self.xodim} — {self.oy:%m.%Y}: {self.jami:,} so'm"


class XodimManager(FoydalanuvchiManager):
    def get_queryset(self):
        return super().get_queryset().filter(rol='xodim')


class Xodim(Foydalanuvchi):
    """Admin panelida xodimlarni alohida ro'yxat sifatida ko'rsatish uchun.
    Yangi jadval yaratmaydi — Foydalanuvchi jadvalining rol='xodim' qismi.
    Xodimlar faqat shu yerdan kiritiladi, portalda ro'yxatdan o'tish yo'q."""

    objects = XodimManager()

    class Meta:
        proxy = True
        verbose_name = 'Xodim'
        verbose_name_plural = 'Xodimlar'

    def save(self, *args, **kwargs):
        self.rol = 'xodim'
        super().save(*args, **kwargs)


class MijozManager(FoydalanuvchiManager):
    def get_queryset(self):
        return super().get_queryset().filter(rol='mijoz')


class Mijoz(Foydalanuvchi):
    """Django panelida mijozlarni alohida (FAQAT O'QISH uchun) ro'yxat sifatida ko'rsatish.
    Yangi jadval yaratmaydi — Foydalanuvchi jadvalining rol='mijoz' qismi. Direktor bu orqali
    mijozlar bazasini ko'radi, to'liq Foydalanuvchi sahifasini (parol shifri bilan) ko'rmaydi."""

    objects = MijozManager()

    class Meta:
        proxy = True
        verbose_name = 'Mijoz'
        verbose_name_plural = 'Mijozlar'


AUDIT_AMAL_CHOICES = [
    ('kirish', 'Tizimga kirdi'),
    ('kirish_xato', 'Noto\'g\'ri parol'),
    ('kirish_blok', 'Hisob bloklandi'),
    ('chiqish', 'Tizimdan chiqdi'),
    ('xodim_qoshildi', 'Yangi xodim qo\'shildi'),
    ('xodim_holat', 'Xodim holati o\'zgardi'),
    ('xodim_kod', 'Xodimga yangi kod berildi'),
    ('ariza_tayinlandi', 'Ariza xodimga tayinlandi'),
    ('ruxsat_rad', 'Ruxsat rad etildi'),
    ('admin_ochildi', 'Bloklangan hisob qayta faollashtirildi'),
    ('joylashuv_rozilik', 'Xodim joylashuv kuzatuviga rozilik berdi'),
    ('smena_boshlandi', 'Smena boshlandi (joylashuv yoqildi)'),
    ('smena_tugadi', 'Smena tugadi (joylashuv o\'chdi)'),
    ('joylashuv_korildi', 'Xodimlar joylashuvi ko\'rildi'),
    ('tushum_kiritildi', 'Xodim mijozdan olingan pulni kiritdi'),
    ('tushum_qabul', 'Administrator xodimdan pulni qabul qildi'),
    ('tushum_rad', 'Tushum yozuvi rad etildi'),
    ('xabar_yuborildi', 'Xodimlarga xabar yuborildi'),
    ('narx_ozgardi', "Xizmat narxi o'zgartirildi"),
    ('narx_qoshildi', "Narxnomaga yangi qator qo'shildi"),
    ('buyurtma_xizmat', 'Buyurtmaga narxnoma xizmati biriktirildi/olib tashlandi'),
    ('buyurtma_summa', 'Buyurtma summasi tasdiqlandi/o\'zgartirildi'),
    ('buyurtma_tarmoq', "Buyurtma narx tarmog'i o'zgartirildi"),
    ('korish_boshlandi', "Egasi foydalanuvchi nomidan ko'rishni boshladi"),
    ('korish_rad', "Ko'rish rejimida o'zgartirish urinishi bloklandi"),
    ('panel_ozgarish', "Django panelida o'zgartirildi"),
    ('mijoz_ochildi', "Hujjat orqali yangi mijoz ro'yxatga olindi"),
    ('ariza_qongiroq', "Qo'ng'iroq arizasi operator tomonidan qabul qilindi"),
    ('buyurtma_tayinlandi', 'Buyurtmaga xodim tayinlandi'),
    ('hujjat_yuborildi', 'Tayyor hujjat mijozga yuborildi'),
    ('kvitansiya_berildi', 'Mijozga kvitansiya berildi'),
    ('kvitansiya_bekor', 'Kvitansiya bekor qilindi'),
    ('shartnoma_tuzildi', 'Mijoz bilan shartnoma tuzildi'),
    ('shartnoma_tasdiq', 'Shartnoma tasdiqlandi'),
    ('shartnoma_bekor', 'Shartnoma bekor qilindi'),
]


class AuditYozuv(models.Model):
    """Boshqaruv panelidagi har bir muhim amal shu yerga yoziladi.

    Maqsad — "kim, qachon, nima qildi" savoliga javob. Yozuvlar HECH QACHON
    o'zgartirilmaydi va o'chirilmaydi (Django admin panelida ham faqat
    o'qish uchun), aks holda jurnalning ma'nosi qolmaydi.

    `kim` o'chirilgan foydalanuvchida NULL bo'lib qoladi, shuning uchun ism va
    telefon alohida matn sifatida ham saqlanadi — jurnal o'zi to'liq qoladi.
    """
    kim = models.ForeignKey('Foydalanuvchi', on_delete=models.SET_NULL,
                            null=True, blank=True, related_name='audit_yozuvlar')
    kim_ism = models.CharField(max_length=120, blank=True)
    kim_telefon = models.CharField(max_length=30, blank=True)
    amal = models.CharField(max_length=30, choices=AUDIT_AMAL_CHOICES, db_index=True)
    tafsilot = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    vaqt = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Audit yozuvi'
        verbose_name_plural = 'Audit jurnali'
        ordering = ['-vaqt']

    def __str__(self):
        return f"{self.vaqt:%d.%m.%Y %H:%M} — {self.kim_ism or self.kim_telefon}: {self.get_amal_display()}"


def audit_yoz(request, amal, tafsilot='', user=None):
    """Audit yozuvini qo'shadi. Jurnal yozilmagani asosiy amalni buzmasligi
    kerak — shuning uchun har qanday xatolik yutiladi."""
    try:
        kim = user if user is not None else getattr(request, 'user', None)
        if kim is not None and not getattr(kim, 'is_authenticated', False):
            kim = None
        ip = None
        if request is not None:
            ip = (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                  or request.META.get('REMOTE_ADDR'))
        AuditYozuv.objects.create(
            kim=kim,
            kim_ism=getattr(kim, 'ism', '') or '',
            kim_telefon=getattr(kim, 'telefon', '') or '',
            amal=amal,
            tafsilot=tafsilot[:255],
            ip=ip or None,
        )
    except Exception:
        pass


class OtpKod(models.Model):
    telefon = models.CharField(max_length=20)
    kod = models.CharField(max_length=6)
    yaratilgan = models.DateTimeField(auto_now_add=True)
    ishlatildi = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'OTP Kod'
        ordering = ['-yaratilgan']

    def __str__(self):
        return f"{self.telefon} — {self.kod}"

    def muddati_utganmi(self):
        from django.conf import settings
        limit = timezone.now() - timezone.timedelta(minutes=getattr(settings, 'OTP_EXPIRE_MINUTES', 5))
        return self.yaratilgan < limit
