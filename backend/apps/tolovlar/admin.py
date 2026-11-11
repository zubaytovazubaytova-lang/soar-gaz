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
