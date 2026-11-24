from django.contrib import admin
from .models import TolovSorovi, MahsulotSorovi, MetrologiyaArizasi


@admin.register(TolovSorovi)
class TolovSoroviAdmin(admin.ModelAdmin):
    list_display = ['id', 'ism', 'telefon', 'tolov_turi_nomi', 'tolov_tizimi',
                    'summa', 'holat', 'yaratilgan']
    list_filter = ['holat', 'tolov_turi', 'tolov_tizimi']
    search_fields = ['ism', 'telefon', 'xizmat_turi']
    ordering = ['-yaratilgan']
    list_editable = ['holat']


@admin.register(MahsulotSorovi)
class MahsulotSoroviAdmin(admin.ModelAdmin):
    list_display = ['id', 'mahsulot', 'miqdor', 'ism', 'telefon',
                    'katalog', 'holat', 'yaratilgan']
    list_filter = ['holat', 'katalog']
    search_fields = ['ism', 'telefon', 'mahsulot']
    ordering = ['-yaratilgan']
    list_editable = ['holat']


@admin.register(MetrologiyaArizasi)
class MetrologiyaArizasiAdmin(admin.ModelAdmin):
    list_display = ['id', 'xizmat_nomi', 'ism', 'telefon', 'hisoblagich',
                    'seriya_raqam', 'manzil', 'holat', 'yaratilgan']
    list_filter = ['holat', 'xizmat', 'hisoblagich']
    search_fields = ['ism', 'telefon', 'seriya_raqam', 'manzil']
    ordering = ['-yaratilgan']
    list_editable = ['holat']


from django.contrib import messages  # noqa: E402

from .bank import tekshir, tekshiruvchimi  # noqa: E402
from .models import BankTolovi, Rekvizit  # noqa: E402


@admin.register(Rekvizit)
class RekvizitAdmin(admin.ModelAdmin):
    list_display = ['yonalish', 'korxona', 'bank', 'hisob_raqam', 'mfo', 'stir', 'ruxsatnoma', 'faol']
    list_editable = ['faol']


@admin.register(BankTolovi)
class BankTolovAdmin(admin.ModelAdmin):
    list_display = ['id', 'buyurtma', 'mijoz', 'summa', 'holat', 'tekshirdi', 'yaratilgan']
    list_filter = ['holat']
    search_fields = ['mijoz__telefon', 'mijoz__ism', 'buyurtma__id']
    readonly_fields = ['buyurtma', 'mijoz', 'summa', 'hisob_raqam', 'chek', 'izoh', 'holat', 'rad_sabab',
                       'tekshirdi', 'tekshirilgan', 'tolov_sorovi', 'yaratilgan']
    actions = ['tasdiqlash']

    def has_add_permission(self, request):
        return False

    @admin.action(description="Tanlangan cheklarni tasdiqlash (pul bankda ko'rildi)")
    def tasdiqlash(self, request, qs):
        if not tekshiruvchimi(request.user):
            self.message_user(request, "Ruxsat yo'q", messages.ERROR)
            return
        soni = sum(1 for t in qs if tekshir(t, request.user, 'tasdiq', request=request) is None)
        self.message_user(request, f"{soni} ta chek tasdiqlandi")
