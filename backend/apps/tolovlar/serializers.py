import re
from datetime import date

from rest_framework import serializers
from .models import TolovSorovi, MahsulotSorovi, MetrologiyaArizasi


class TolovSoroviSerializer(serializers.ModelSerializer):
    class Meta:
        model = TolovSorovi
        fields = [
            'id', 'ism', 'telefon', 'tolov_turi', 'tolov_turi_nomi',
            'tolov_tizimi', 'xizmat_turi', 'summa', 'izoh', 'muddat',
            'holat', 'tashqi_id', 'yaratilgan', 'yangilangan',
        ]
        read_only_fields = [
            'id', 'tolov_turi_nomi', 'holat', 'tashqi_id',
            'yaratilgan', 'yangilangan',
        ]


class MahsulotSoroviSerializer(serializers.ModelSerializer):
    class Meta:
        model = MahsulotSorovi
        fields = [
            'id', 'ism', 'telefon', 'mahsulot', 'katalog', 'miqdor',
            'birlik', 'izoh', 'holat', 'yaratilgan', 'yangilangan',
        ]
        read_only_fields = ['id', 'holat', 'yaratilgan', 'yangilangan']


HISOBLAGICH_MODELLARI = ['G4', 'G6', 'G10', 'G16', 'G25', 'G40+', 'Ultratovush']
# Qayta yuborilgan arizani aniqlashda "hali ochiq" deb hisoblanadigan holatlar
OCHIQ_HOLATLAR = ['yangi', 'korildi', 'boglandi']


class MetrologiyaArizasiSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetrologiyaArizasi
        fields = [
            'id', 'ism', 'telefon', 'xizmat', 'hisoblagich', 'seriya_raqam',
            'ornatilgan_yil', 'manzil', 'izoh', 'holat', 'yaratilgan',
        ]
        read_only_fields = ['id', 'holat', 'yaratilgan']
        # Saytdagi forma bu maydonlarni majburiy deb belgilaydi — serverda ham shunday
        extra_kwargs = {
            'hisoblagich': {'required': True, 'allow_blank': False},
            'seriya_raqam': {'required': True, 'allow_blank': False},
        }

    def validate_telefon(self, v):
        """Telefonni yagona +998XXXXXXXXX ko'rinishiga keltiradi.

        Ilgari "90 123 45 67" → "901234567" saqlanardi: SMS noto'g'ri raqamga
        ketardi va ariza mijoz hisobiga bog'lanmasdi."""
        raqamlar = re.sub(r'\D', '', v or '')
        if len(raqamlar) == 9:                                   # 901234567
            raqamlar = '998' + raqamlar
        elif len(raqamlar) == 10 and raqamlar.startswith('0'):   # 0901234567
            raqamlar = '998' + raqamlar[1:]
        if raqamlar.startswith('998'):
            if len(raqamlar) != 12:
                raise serializers.ValidationError("Telefon raqami noto'g'ri")
        elif not (9 <= len(raqamlar) <= 15):                     # chet el raqami
            raise serializers.ValidationError("Telefon raqami noto'g'ri")
        return '+' + raqamlar

    def validate_hisoblagich(self, v):
        v = (v or '').strip()
        if v not in HISOBLAGICH_MODELLARI:
            raise serializers.ValidationError("Hisoblagich modelini ro'yxatdan tanlang")
        return v

    def validate_seriya_raqam(self, v):
        return re.sub(r'\s+', '', v or '').upper()

    def validate_ornatilgan_yil(self, v):
        if v is not None and not (1990 <= v <= date.today().year):
            raise serializers.ValidationError("O'rnatilgan yil noto'g'ri")
        return v

    def validate(self, attrs):
        # Bir xil ariza ikki marta tushmasin (qayta bosish, sekin tarmoq)
        mavjud = MetrologiyaArizasi.objects.filter(
            telefon=attrs.get('telefon'), seriya_raqam=attrs.get('seriya_raqam'),
            xizmat=attrs.get('xizmat'), holat__in=OCHIQ_HOLATLAR).first()
        if mavjud:
            raise serializers.ValidationError(
                f"Bu hisoblagich uchun ariza allaqachon qabul qilingan (#{mavjud.id}). "
                f"Mutaxassisimiz tez orada bog'lanadi.")
        return attrs
