from rest_framework import serializers
from .models import Buyurtma, BuyurtmaFoto


class BuyurtmaSerializer(serializers.ModelSerializer):
    # Bazadagi ustun emas, joriy tildagi yorliq (`Accept-Language`).
    xizmat_nomi = serializers.CharField(source='get_xizmat_display', read_only=True)
    holat_nomi = serializers.CharField(source='get_holat_display', read_only=True)
    mijoz_malumot = serializers.SerializerMethodField()
    xodim_malumot = serializers.SerializerMethodField()

    class Meta:
        model = Buyurtma
        fields = [
            'id', 'obyekt', 'xizmat', 'xizmat_nomi', 'tuman', 'manzil', 'tavsif',
            'vaqt_istagi', 'holat', 'holat_nomi', 'natija', 'natija_soat', 'natija_sana',
            'material', 'tolandi', 'yaratilgan', 'yangilangan',
            'mijoz_malumot', 'xodim_malumot',
        ]
        read_only_fields = ['id', 'xizmat_nomi', 'holat_nomi', 'yaratilgan',
                            'yangilangan']

    def get_mijoz_malumot(self, obj):
        if not obj.mijoz:
            return None
        return {
            'id': obj.mijoz.id,
            'ism': obj.mijoz.ism,
            'telefon': obj.mijoz.telefon,
            'manzil': obj.mijoz.manzil,
            'tuman': obj.mijoz.tuman,
        }

    def get_xodim_malumot(self, obj):
        if not obj.xodim:
            return None
        return {
            'id': obj.xodim.id,
            'ism': obj.xodim.ism,
            'telefon': obj.xodim.telefon,
            'tuman': obj.xodim.tuman,
        }
