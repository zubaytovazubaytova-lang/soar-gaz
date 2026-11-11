from django.contrib import admin

from apps.tushum.models import Tushum
from .models import Buyurtma, BuyurtmaFoto, BuyurtmaXizmat


class FaqatOqishInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


class XizmatInline(FaqatOqishInline):
    """Xodim tanlagan narxnoma xizmatlari (narx shu paytdagi qiymatda)."""
    model = BuyurtmaXizmat
    verbose_name_plural = 'Tanlangan xizmatlar (narxnomadan)'
    fields = ['nomi', 'ustun_nomi', 'soni', 'narx_dan', 'narx_gacha', 'qoshgan', 'yaratilgan']
    readonly_fields = fields


class TushumInline(FaqatOqishInline):
    """Shu buyurtma bo'yicha olingan pul va uning holati."""
    model = Tushum
    fk_name = 'buyurtma'
    verbose_name_plural = "Olingan pul (tushumlar)"
    fields = ['yaratilgan', 'xodim', 'summa', 'usul', 'ish_turi', 'holat', 'hal_qilgan', 'hal_vaqti', 'rad_sababi']
    readonly_fields = fields


@admin.register(Buyurtma)
class BuyurtmaAdmin(admin.ModelAdmin):
    list_display = ['id', 'xizmat_nomi', 'tarmoq', 'holat', 'tuman', 'mijoz_ism', 'mijoz_telefon',
                    'manzil', 'xodim', 'tasdiq_summa', 'tolandi', 'yaratilgan']
    list_filter = ['holat', 'tarmoq', 'tolandi', 'xizmat', 'tuman']
    search_fields = ['mijoz__telefon', 'mijoz__ism', 'mijoz_telefon', 'mijoz_ism', 'manzil']
    ordering = ['-yaratilgan']
    raw_id_fields = ['mijoz', 'xodim']
    list_select_related = ('mijoz', 'xodim')
    # Tasdiqlash vaqti va kimligi o'zgartirilmaydi (summani xodim yoki admin tasdiqlaganda yoziladi)
    readonly_fields = ['tasdiq_vaqt', 'tasdiq_kim']
    inlines = [XizmatInline, TushumInline]


@admin.register(BuyurtmaFoto)
class BuyurtmaFotoAdmin(admin.ModelAdmin):
    list_display = ['buyurtma', 'tur', 'yaratilgan']
    list_select_related = ('buyurtma',)
