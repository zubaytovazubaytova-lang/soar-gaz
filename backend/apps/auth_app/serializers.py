from django.utils.translation import gettext as _
from rest_framework import serializers

from .hududlar import viloyat_tumanlari, viloyatlar, tuman_viloyati
from .models import Foydalanuvchi, kirish_kodi_yasa


class JoylashuvMixin:
    """Viloyat va tumanni ro'yxat bo'yicha tekshiradi.

    Viloyat va tuman TANLANADI — ular ro'yxatdagi qiymat bo'lishi shart,
    aks holda hisobot va filtrlash buziladi. Mahalla/ko'cha esa qo'lda
    yoziladi va tekshirilmaydi: ular juda ko'p va o'zgaruvchan.

    Eski yozuvlarni buzmaslik uchun bo'sh qiymatga ruxsat beriladi.
    """

    def validate(self, malumot):
        malumot = super().validate(malumot)
        viloyat = malumot.get('viloyat', '')
        tuman = malumot.get('tuman', '')

        if viloyat and viloyat not in viloyatlar():
            raise serializers.ValidationError(
                {'viloyat': 'Bunday viloyat ro\'yxatda yo\'q'})

        if tuman:
            if not viloyat:
                # Viloyat berilmagan bo'lsa, tumandan o'zi aniqlanadi
                viloyat = tuman_viloyati(tuman)
                if not viloyat:
                    raise serializers.ValidationError(
                        {'tuman': 'Bunday tuman ro\'yxatda yo\'q'})
                malumot['viloyat'] = viloyat
            elif tuman not in viloyat_tumanlari(viloyat):
                raise serializers.ValidationError(
                    {'tuman': f'"{tuman}" — {viloyat} tarkibida bunday '
                              f'tuman yo\'q'})

        return malumot


class FoydalanuvchiSerializer(JoylashuvMixin, serializers.ModelSerializer):
    tuman_nomi = serializers.ReadOnlyField()

    class Meta:
        model = Foydalanuvchi
        fields = ['id', 'telefon', 'ism', 'manzil', 'viloyat', 'tuman', 'mahalla',
                  'tuman_nomi', 'rol', 'holat', 'yaratilgan']
        read_only_fields = ['id', 'yaratilgan', 'rol']


class XodimSerializer(serializers.ModelSerializer):
    """Xodim ma'lumotlari — ro'yxatda ko'rsatish uchun (faqat o'qish)."""
    tuman_nomi = serializers.ReadOnlyField()

    class Meta:
        model = Foydalanuvchi
        fields = ['id', 'telefon', 'ism', 'lavozim', 'viloyat', 'tuman',
                  'mahalla', 'tuman_nomi', 'holat', 'ishga_kirgan',
                  'kirish_kodi', 'yaratilgan']
        read_only_fields = fields


class XodimJamoaSerializer(serializers.ModelSerializer):
    """Jamoa ro'yxati ODDIY XODIM uchun: KIRISH KODISIZ. Kod xodimning parolini bosib turadi — uni faqat
    administrator ko'radi (XodimSerializer). Aks holda har bir xodim boshqasining nomidan kira olardi."""
    tuman_nomi = serializers.ReadOnlyField()

    class Meta:
        model = Foydalanuvchi
        fields = ['id', 'telefon', 'ism', 'lavozim', 'viloyat', 'tuman',
                  'mahalla', 'tuman_nomi', 'holat', 'ishga_kirgan', 'yaratilgan']
        read_only_fields = fields


class XodimYaratishSerializer(JoylashuvMixin, serializers.ModelSerializer):
    """Admin panelidan yangi xodim kiritish.

    Xodim o'zi ro'yxatdan o'ta olmaydi — hisobni admin ochadi. Parol yo'q:
    tizim KIRISH KODI yaratadi, admin uni xodimga aytadi va xodim telefon
    raqami + shu kod bilan portalga kiradi.

    Kod javobda qaytariladi — admin uni bir marta ko'radi va yozib oladi.
    """

    class Meta:
        model = Foydalanuvchi
        fields = ['id', 'telefon', 'ism', 'lavozim', 'viloyat', 'tuman',
                  'mahalla', 'holat', 'ishga_kirgan', 'kirish_kodi']
        read_only_fields = ['kirish_kodi']

    def validate_telefon(self, qiymat):
        # Foydalanuvchi "+998 90 123 45 67" ko'rinishida kiritishi mumkin
        telefon = qiymat.replace(' ', '').replace('-', '')
        if Foydalanuvchi.objects.filter(telefon=telefon).exists():
            raise serializers.ValidationError(
                _('Bu telefon raqam allaqachon ro\'yxatda bor'))
        return telefon

    def create(self, malumot):
        telefon = malumot.pop('telefon')
        # Kod noyob bo'lishi kerak: xodim faqat telefon + kod bilan kiradi,
        # takrorlangan kod chalkashlik keltirib chiqaradi.
        while True:
            kod = kirish_kodi_yasa()
            if not Foydalanuvchi.objects.filter(kirish_kodi=kod).exists():
                break
        xodim = Foydalanuvchi.objects.create_user(
            telefon=telefon, password=None, rol='xodim',
            kirish_kodi=kod, **malumot)
        # Parol ishlatilmaydi — hech qanday parol bilan kirib bo'lmasin
        xodim.set_unusable_password()
        xodim.save(update_fields=['password'])
        return xodim


class XodimHolatSerializer(serializers.ModelSerializer):
    """Xodimni faol/nofaol qilish.

    Xodim o'chirilmaydi — uning nomi eski buyurtmalarda qolishi kerak.
    Nofaol xodim portalga kira olmaydi (xodim_login tekshiradi).
    """

    class Meta:
        model = Foydalanuvchi
        fields = ['id', 'holat']


class RoyxatSerializer(JoylashuvMixin, serializers.ModelSerializer):
    """Mijozning o'zi ro'yxatdan o'tishi. Rol har doim 'mijoz' bo'ladi —
    mijoz o'ziga admin/xodim roli bera olmasligi uchun."""
    ism = serializers.CharField(max_length=100)

    class Meta:
        model = Foydalanuvchi
        fields = ['ism', 'telefon', 'manzil', 'viloyat', 'tuman', 'mahalla',
                  'qoshimcha_telefon', 'email', 'mulk_turi', 'moljal']

    def validate_telefon(self, qiymat):
        telefon = qiymat.replace(' ', '')
        if not telefon:
            raise serializers.ValidationError(_('Telefon raqam kiritilishi shart'))
        if Foydalanuvchi.objects.filter(telefon=telefon).exists():
            raise serializers.ValidationError(_('Bu raqam allaqachon ro\'yxatdan o\'tgan'))
        return telefon

    def create(self, validated_data):
        validated_data['rol'] = 'mijoz'
        return Foydalanuvchi.objects.create_user(**validated_data)


class ProfilSerializer(JoylashuvMixin, serializers.ModelSerializer):

    class Meta:
        model = Foydalanuvchi
        fields = ['ism', 'manzil', 'viloyat', 'tuman', 'mahalla',
                  'qoshimcha_telefon', 'email', 'mulk_turi', 'moljal']


class XodimProfilSerializer(serializers.ModelSerializer):
    """Xodim o'z kabinetida faqat aloqa ma'lumotlarini o'zgartira oladi.
    Ism, lavozim, tabel raqam va filial — admin panelidan boshqariladi."""

    class Meta:
        model = Foydalanuvchi
        fields = ['email', 'qoshimcha_telefon']
