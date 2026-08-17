from rest_framework import serializers
from .models import TolovSorovi, MahsulotSorovi


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
