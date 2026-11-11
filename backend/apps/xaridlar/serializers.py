from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import (Xarid, XaridQatori, YETKAZISH_CHOICES, TOLOV_USULI_CHOICES,
                     HOLAT_CHOICES, ONLAYN_USULLAR, KURYER_HOLATLARI,
                     MUAMMO_CHOICES)

# ──────────────────────────────────────────────────────────────
#  JSON shakli xaridlar-app/lib/types.ts dagi `Order` bilan
#  aynan bir xil (camelCase) — frontend tiplari o'zgarmaydi.
# ──────────────────────────────────────────────────────────────

HOLATLAR = {kod for kod, _ in HOLAT_CHOICES}
MUAMMOLAR = {kod for kod, _ in MUAMMO_CHOICES}
YETKAZISHLAR = {kod for kod, _ in YETKAZISH_CHOICES}
TOLOV_USULLARI = {kod for kod, _ in TOLOV_USULI_CHOICES}


class XaridQatoriSerializer(serializers.ModelSerializer):
    productId = serializers.CharField(source='mahsulot_id')
    name = serializers.CharField(source='nomi')
    price = serializers.IntegerField(source='narx')
    qty = serializers.IntegerField(source='miqdor')
    image = serializers.CharField(source='rasm')

    class Meta:
        model = XaridQatori
        fields = ['productId', 'slug', 'name', 'price', 'qty', 'image']


def niqob_ism(ism):
    """«Ali Valiyev» -> «Ali V.»"""
    qismlar = (ism or '').split()
    if not qismlar:
        return ''
    return qismlar[0] + (f' {qismlar[1][0]}.' if len(qismlar) > 1 else '')


def niqob_telefon(telefon):
    """«+998901234567» -> «+998 ** *** ** 67»"""
    raqamlar = ''.join(ch for ch in (telefon or '') if ch.isdigit())
    return '+998 ** *** ** ' + raqamlar[-2:] if len(raqamlar) >= 2 else ''


class XaridSerializer(serializers.ModelSerializer):
    """Faqat o'qish uchun — yozish `xarid_yaratish` view'ida.

    `context={'yashirin': True}` — buyurtma egasi tasdiqlanmagan so'rovchi uchun:
    ism va telefon niqoblanadi, manzil, koordinatalar, kuryer ma'lumoti va yetkazish
    izohi umuman berilmaydi (buyurtma raqamini bilish egalik dalili emas).
    """
    id = serializers.CharField(source='raqam', read_only=True)
    createdAt = serializers.DateTimeField(source='yaratilgan', read_only=True)
    status = serializers.CharField(source='holat', read_only=True)
    items = XaridQatoriSerializer(source='qatorlar', many=True, read_only=True)
    total = serializers.IntegerField(source='jami', read_only=True)
    installService = serializers.BooleanField(source='ornatish_xizmati', read_only=True)
    customer = serializers.SerializerMethodField()
    delivery = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()

    class Meta:
        model = Xarid
        fields = ['id', 'createdAt', 'status', 'customer', 'delivery',
                  'payment', 'installService', 'items', 'total', 'totals']

    def to_representation(self, obj):
        d = super().to_representation(obj)
        if self.context.get('yashirin'):
            d['restricted'] = True
        return d

    def get_customer(self, obj):
        if self.context.get('yashirin'):
            return {'name': niqob_ism(obj.ism), 'phone': niqob_telefon(obj.telefon), 'address': ''}
        return {'name': obj.ism, 'phone': obj.telefon, 'address': obj.manzil}

    def get_delivery(self, obj):
        yashirin = self.context.get('yashirin')
        d = {'method': obj.yetkazish, 'note': '' if yashirin else obj.yetkazish_izohi,
             'time': obj.yetkazish_vaqti, 'price': obj.yetkazish_narxi,
             'region': obj.tuman, 'eta': obj.yetkazish_muddati}

        # Yetkazib bo'lmagan bo'lsa — sabab va urinishlar soni
        if obj.muammo:
            d['problem'] = {
                'code': obj.muammo,
                'label': obj.get_muammo_display(),
                'note': obj.muammo_izohi,
                'at': obj.muammo_vaqti,
                'attempts': obj.urinish_soni,
            }

        # Kuryer joylashuvi faqat yo'lda bo'lgan buyurtmalarda ochiladi —
        # yetkazib berilgandan keyin kuryerni kuzatishning hojati yo'q
        if not yashirin and obj.holat in KURYER_HOLATLARI and obj.kuryer_lat is not None:
            d['courier'] = {
                'lat': obj.kuryer_lat,
                'lng': obj.kuryer_lng,
                'updated': obj.kuryer_yangilangan,
                'name': obj.kuryer.ism if obj.kuryer else '',
                'phone': obj.kuryer.telefon if obj.kuryer else '',
            }
        if not yashirin and obj.manzil_lat is not None:
            d['destination'] = {'lat': obj.manzil_lat, 'lng': obj.manzil_lng}
        return d

    def get_totals(self, obj):
        """Summaning to'liq tafsiloti — chek/xulosa ko'rsatish uchun."""
        return {
            'items': obj.mahsulotlar_summasi,
            'discount': obj.chegirma,
            'promo': obj.promokod,
            'delivery': obj.yetkazish_narxi,
            'install': obj.ornatish_narxi,
            'grand': obj.jami,
        }

    def get_payment(self, obj):
        d = {
            'method': obj.tolov_usuli,
            'paid': obj.tolandi,
            'state': obj.tolov_holati,
            'attempts': obj.tolov_urinishlari,
            # Naqd va bo'lib to'lashda onlayn to'lov havolasi bo'lmaydi
            'online': obj.tolov_usuli in ONLAYN_USULLAR,
        }
        if obj.bolib_oy:
            d['months'] = obj.bolib_oy
            d['monthly'] = obj.oylik_tolov
        return d


class XaridKirishSerializer(serializers.Serializer):
    """POST /api/xaridlar/ kirish ma'lumotlarini tekshiradi."""

    class _Customer(serializers.Serializer):
        name = serializers.CharField(max_length=120)
        phone = serializers.CharField(max_length=30)
        address = serializers.CharField(max_length=255, required=False, allow_blank=True)

    class _Delivery(serializers.Serializer):
        method = serializers.ChoiceField(choices=sorted(YETKAZISHLAR), default='kuryer')
        note = serializers.CharField(required=False, allow_blank=True)
        time = serializers.CharField(max_length=80, required=False, allow_blank=True)
        region = serializers.CharField(max_length=60, required=False, allow_blank=True)

    class _Payment(serializers.Serializer):
        method = serializers.ChoiceField(choices=sorted(TOLOV_USULLARI), default='naqd')
        # Bo'lib to'lash uchun oylar soni (faqat method='bolib' bo'lganda)
        months = serializers.IntegerField(required=False, min_value=0, max_value=36, default=0)

    class _Item(serializers.Serializer):
        # Faqat id va miqdor. Narx/nom/rasm mijozdan QABUL QILINMAYDI —
        # ular apps.xaridlar.mahsulotlar orqali serverdagi katalogdan olinadi.
        productId = serializers.CharField(max_length=60, required=False, allow_blank=True)
        # Marketing sayti katalogi: `kalit` (narx KatalogNarx dan olinadi) + ko'rsatish uchun nom
        kalit = serializers.CharField(max_length=80, required=False, allow_blank=True)
        name = serializers.CharField(max_length=200, required=False, allow_blank=True)
        image = serializers.CharField(max_length=60, required=False, allow_blank=True)
        qty = serializers.IntegerField(min_value=1, max_value=999)

        def validate(self, d):
            if not (d.get('productId') or d.get('kalit') or d.get('name')):
                raise serializers.ValidationError(_("Mahsulot ko'rsatilmagan"))
            return d

    customer = _Customer()
    delivery = _Delivery(required=False)
    payment = _Payment(required=False)
    installService = serializers.BooleanField(required=False, default=False)
    promo = serializers.CharField(max_length=40, required=False, allow_blank=True)
    items = _Item(many=True, allow_empty=False)

    def validate_items(self, qiymat):
        if not qiymat:
            raise serializers.ValidationError(_("Savat bo'sh"))
        return qiymat
