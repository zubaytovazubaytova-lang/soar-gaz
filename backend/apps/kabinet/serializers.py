from rest_framework import serializers

from apps.auth_app.serializers import JoylashuvMixin
from .models import (
    Obyekt, Uskuna, Hisoblagich, Hujjat, Bildirishnoma, Sharh,
    Murojaat, MurojaatXabar, QongiroqSorovi, SavolJavob, KabinetSozlama,
)


class UskunaSerializer(serializers.ModelSerializer):
    turi_nomi = serializers.CharField(source='get_turi_display', read_only=True)

    class Meta:
        model = Uskuna
        fields = ['id', 'obyekt', 'turi', 'turi_nomi', 'nom', 'model',
                  'seriya_raqam', 'hajm', 'ornatilgan_sana']
        read_only_fields = ['id', 'turi_nomi']


class HisoblagichSerializer(serializers.ModelSerializer):
    turi_nomi = serializers.CharField(source='get_turi_display', read_only=True)
    obyekt_nomi = serializers.CharField(source='obyekt.nom', read_only=True)
    kun_qoldi = serializers.IntegerField(read_only=True)
    muddat_holati = serializers.CharField(read_only=True)

    class Meta:
        model = Hisoblagich
        fields = ['id', 'obyekt', 'obyekt_nomi', 'turi', 'turi_nomi', 'markasi',
                  'seriya_raqam', 'ornatilgan_sana', 'oxirgi_tekshiruv',
                  'keyingi_tekshiruv', 'oxirgi_korsatkich', 'holat',
                  'kun_qoldi', 'muddat_holati']
        read_only_fields = ['id', 'turi_nomi', 'obyekt_nomi', 'kun_qoldi', 'muddat_holati']


class ObyektSerializer(JoylashuvMixin, serializers.ModelSerializer):
    turi_nomi = serializers.CharField(source='get_turi_display', read_only=True)
    uskunalar = UskunaSerializer(many=True, read_only=True)
    hisoblagichlar = HisoblagichSerializer(many=True, read_only=True)
    buyurtma_soni = serializers.SerializerMethodField()

    class Meta:
        model = Obyekt
        fields = ['id', 'nom', 'turi', 'turi_nomi', 'viloyat', 'tuman',
                  'mahalla', 'manzil', 'moljal',
                  'rezervuar_hajmi', 'izoh', 'asosiy', 'yaratilgan',
                  'uskunalar', 'hisoblagichlar', 'buyurtma_soni']
        read_only_fields = ['id', 'turi_nomi', 'yaratilgan', 'uskunalar',
                            'hisoblagichlar', 'buyurtma_soni']

    def get_buyurtma_soni(self, obj):
        # Ro'yxat view'i annotate(buyurtma_soni_db=...) bilan keladi — u holda
        # qo'shimcha so'rov kerak emas. Yakka obyekt uchun eski yo'l qoladi.
        soni = getattr(obj, 'buyurtma_soni_db', None)
        return soni if soni is not None else obj.buyurtmalar.count()


class HujjatSerializer(serializers.ModelSerializer):
    turi_nomi = serializers.CharField(source='get_turi_display', read_only=True)
    obyekt_nomi = serializers.CharField(source='obyekt.nom', read_only=True, default='')
    fayl_url = serializers.SerializerMethodField()
    olcham = serializers.SerializerMethodField()

    class Meta:
        model = Hujjat
        fields = ['id', 'turi', 'turi_nomi', 'nom', 'sana', 'izoh',
                  'obyekt', 'obyekt_nomi', 'fayl_url', 'olcham']
        read_only_fields = fields

    def get_fayl_url(self, obj):
        """Faylga to'g'ridan-to'g'ri /media/ havolasi berilmaydi — shartnoma va
        sertifikatlar shaxsiy hujjat. O'rniga qisqa muddatli imzolangan havola."""
        if not obj.fayl:
            return ''
        from django.core import signing
        from .views import HUJJAT_IMZO_TUZI
        token = signing.dumps({'id': obj.id}, salt=HUJJAT_IMZO_TUZI)
        yol = f'/api/kabinet/hujjat/{token}/'
        so_rov = self.context.get('request')
        return so_rov.build_absolute_uri(yol) if so_rov else yol

    def get_olcham(self, obj):
        """Fayl hajmi KB da — ro'yxatda ko'rsatish uchun."""
        try:
            return round(obj.fayl.size / 1024)
        except (ValueError, OSError):
            return None


class BildirishnomaSerializer(serializers.ModelSerializer):
    turi_nomi = serializers.CharField(source='get_turi_display', read_only=True)

    class Meta:
        model = Bildirishnoma
        fields = ['id', 'turi', 'turi_nomi', 'sarlavha', 'matn', 'bolim',
                  'oqildi', 'yaratilgan']
        read_only_fields = fields


class SharhSerializer(serializers.ModelSerializer):
    buyurtma_nomi = serializers.CharField(source='buyurtma.xizmat_nomi', read_only=True, default='')
    buyurtma_sana = serializers.DateTimeField(source='buyurtma.yaratilgan', read_only=True, default=None)

    class Meta:
        model = Sharh
        fields = ['id', 'buyurtma', 'buyurtma_nomi', 'buyurtma_sana',
                  'baho', 'matn', 'yaratilgan', 'yangilangan']
        read_only_fields = ['id', 'buyurtma_nomi', 'buyurtma_sana', 'yaratilgan', 'yangilangan']

    def validate_baho(self, qiymat):
        if not 1 <= qiymat <= 5:
            raise serializers.ValidationError('Baho 1 dan 5 gacha bo\'lishi kerak')
        return qiymat


class MurojaatXabarSerializer(serializers.ModelSerializer):
    class Meta:
        model = MurojaatXabar
        fields = ['id', 'kim', 'matn', 'yaratilgan']
        read_only_fields = ['id', 'kim', 'yaratilgan']


class MurojaatSerializer(serializers.ModelSerializer):
    xabarlar = MurojaatXabarSerializer(many=True, read_only=True)
    holat_nomi = serializers.CharField(source='get_holat_display', read_only=True)

    class Meta:
        model = Murojaat
        fields = ['id', 'mavzu', 'holat', 'holat_nomi', 'yaratilgan',
                  'yangilangan', 'xabarlar']
        read_only_fields = ['id', 'holat', 'holat_nomi', 'yaratilgan', 'yangilangan', 'xabarlar']


class QongiroqSerializer(serializers.ModelSerializer):
    class Meta:
        model = QongiroqSorovi
        fields = ['id', 'telefon', 'qulay_vaqt', 'mavzu', 'bajarildi', 'yaratilgan']
        read_only_fields = ['id', 'bajarildi', 'yaratilgan']


class SavolJavobSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavolJavob
        fields = ['id', 'savol', 'javob']


class SozlamaSerializer(serializers.ModelSerializer):
    class Meta:
        model = KabinetSozlama
        fields = ['sms_bildirishnoma', 'email_bildirishnoma',
                  'push_bildirishnoma', 'tekshiruv_eslatma']
