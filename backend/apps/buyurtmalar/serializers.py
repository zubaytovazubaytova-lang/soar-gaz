import re

from django.utils.translation import gettext as _
from rest_framework import serializers
from .models import Buyurtma, BuyurtmaFoto


def telefon_tozala(qiymat):
    """"90 123-45-67", "+998 90 123 45 67", "998901234567" -> "+998901234567".
    Raqam shakli noto'g'ri bo'lsa ValidationError."""
    raqam = re.sub(r'[\s\-().]', '', str(qiymat or ''))
    if not raqam:
        return ''
    if raqam.startswith('+'):
        raqamlar = raqam[1:]
    else:
        raqamlar = raqam
    if not raqamlar.isdigit():
        raise serializers.ValidationError(_("Telefon raqam noto'g'ri"))
    if len(raqamlar) == 9:                                # 901234567
        raqamlar = '998' + raqamlar
    if not (9 <= len(raqamlar) <= 15):
        raise serializers.ValidationError(_("Telefon raqam noto'g'ri"))
    return '+' + raqamlar


def xizmatlar_malumoti(b):
    """Buyurtmaga biriktirilgan narxnoma xizmatlari va ularning jami summasi.
    Narxlar ichki (ulgurji narxnoma) — faqat admin va xodimga beriladi."""
    qatorlar = list(b.xizmatlar.all())          # prefetch bo'lsa qo'shimcha so'rov yo'q
    return {
        'royxat': [{
            'id': x.id, 'nomi': x.nomi, 'ustun': x.ustun,
            'ustun_nomi': x.ustun_nomi, 'soni': x.soni,
            'narx_dan': x.narx_dan, 'narx_gacha': x.narx_gacha,
        } for x in qatorlar],
        'jami_dan': sum(x.narx_dan * x.soni for x in qatorlar),
        'jami_gacha': sum((x.narx_gacha if x.narx_gacha is not None else x.narx_dan) * x.soni
                          for x in qatorlar),
        # Xodim tasdiqlagan yakuniy summa (None — hali tasdiqlanmagan)
        'tasdiq_summa': b.tasdiq_summa,
        'tasdiq_vaqt': b.tasdiq_vaqt,
        'tasdiq_kim': (b.tasdiq_kim.ism or b.tasdiq_kim.telefon) if b.tasdiq_kim_id else None,
    }


class BuyurtmaSerializer(serializers.ModelSerializer):
    # Bazadagi ustun emas, joriy tildagi yorliq (`Accept-Language`).
    xizmat_nomi = serializers.CharField(source='get_xizmat_display', read_only=True)
    holat_nomi = serializers.CharField(source='get_holat_display', read_only=True)
    tarmoq_nomi = serializers.CharField(source='get_tarmoq_display', read_only=True)
    mijoz_malumot = serializers.SerializerMethodField()
    xodim_malumot = serializers.SerializerMethodField()
    xizmatlar = serializers.SerializerMethodField()
    shartnoma = serializers.SerializerMethodField()

    class Meta:
        model = Buyurtma
        fields = [
            'id', 'obyekt', 'xizmat', 'xizmat_nomi', 'tuman', 'manzil', 'tavsif',
            'mijoz_ism', 'mijoz_telefon', 'tarmoq', 'tarmoq_nomi',
            'vaqt_istagi', 'holat', 'holat_nomi', 'natija', 'natija_soat', 'natija_sana',
            'material', 'tolandi', 'yaratilgan', 'yangilangan',
            'mijoz_malumot', 'xodim_malumot', 'xizmatlar', 'shartnoma',
        ]
        # `tarmoq`ni mijoz belgilay olmaydi: uni faqat server (korxona -> ulgurji) yoki administrator qo'yadi
        read_only_fields = ['id', 'xizmat_nomi', 'holat_nomi', 'yaratilgan',
                            'yangilangan', 'tarmoq', 'tarmoq_nomi']
        extra_kwargs = {
            'mijoz_ism': {'required': False},
            'mijoz_telefon': {'required': False},
        }

    def validate_mijoz_telefon(self, qiymat):
        return telefon_tozala(qiymat)

    def get_shartnoma(self, obj):
        """Amaldagi (bekor qilinmagan) shartnoma — faqat admin va xodimga (ichki hujjat)."""
        if not self.context.get('narx_korsat'):
            return None
        s = next((x for x in obj.shartnomalar.all() if x.holat != 'bekor'), None)
        if s is None:
            return None
        return {'id': s.id, 'raqam': s.raqam, 'holat': s.holat, 'holat_nomi': s.get_holat_display(),
                'url': f'/shartnoma/{s.token}/', 'mijoz_telefon': s.mijoz_telefon}

    def get_xizmatlar(self, obj):
        # Ichki narxlar mijozga ko'rinmasin: faqat view `narx_korsat=True` bersa chiqadi
        if not self.context.get('narx_korsat'):
            return None
        return xizmatlar_malumoti(obj)

    def get_mijoz_malumot(self, obj):
        if not obj.mijoz:
            # Mijoz hisobi o'chirilgan bo'lsa ham buyurtmada aloqa saqlanib qoladi
            if obj.mijoz_ism or obj.mijoz_telefon:
                return {'id': None, 'ism': obj.mijoz_ism, 'telefon': obj.mijoz_telefon,
                        'manzil': obj.manzil, 'tuman': obj.tuman}
            return None
        # Ism va telefon — buyurtmaning o'zidan (profildagisi emas); manzil ham
        # buyurtmadagi: mijoz ariza uchun boshqa manzil ko'rsatgan bo'lishi mumkin.
        return {
            'id': obj.mijoz.id,
            'ism': obj.mijoz_ism or obj.mijoz.ism,
            'telefon': obj.mijoz_telefon or obj.mijoz.telefon,
            'manzil': obj.manzil or obj.mijoz.manzil,
            'tuman': obj.tuman or obj.mijoz.tuman,
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
