from django.contrib import admin
from .models import Buyurtma, BuyurtmaFoto


@admin.register(Buyurtma)
class BuyurtmaAdmin(admin.ModelAdmin):
    list_display = ['id', 'xizmat_nomi', 'holat', 'tuman', 'mijoz', 'xodim', 'yaratilgan']
    list_filter = ['holat', 'xizmat', 'tuman']
    search_fields = ['mijoz__telefon', 'mijoz__ism', 'manzil']
    ordering = ['-yaratilgan']
    raw_id_fields = ['mijoz', 'xodim']
    list_select_related = ('mijoz', 'xodim')


@admin.register(BuyurtmaFoto)
class BuyurtmaFotoAdmin(admin.ModelAdmin):
    list_display = ['buyurtma', 'tur', 'yaratilgan']
    list_select_related = ('buyurtma',)
