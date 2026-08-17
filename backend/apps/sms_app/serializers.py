from rest_framework import serializers
from .models import SmsXabar


class SmsSerializer(serializers.ModelSerializer):
    telefon = serializers.SerializerMethodField()

    class Meta:
        model = SmsXabar
        fields = ['id', 'matn', 'oqildi', 'yaratilgan', 'telefon']

    def get_telefon(self, obj):
        return obj.mijoz.telefon if obj.mijoz else ''
