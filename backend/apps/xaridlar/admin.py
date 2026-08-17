from django.contrib import admin

from .models import Xarid, XaridQatori, Promokod


class XaridQatoriInline(admin.TabularInline):
    model = XaridQatori
    extra = 0
    readonly_fields = ['mahsulot_id', 'slug', 'nomi', 'narx', 'miqdor', 'rasm']
    can_delete = False


@admin.register(Xarid)
class XaridAdmin(admin.ModelAdmin):
    list_display = ['raqam', 'ism', 'telefon', 'yetkazish', 'yetkazish_vaqti', 'tolov_usuli',
                    'jami', 'chegirma', 'promokod', 'holat', 'tolandi', 'yaratilgan']
    list_filter = ['holat', 'yetkazish', 'tuman', 'muammo', 'tolov_usuli',
                   'tolandi', 'ornatish_xizmati']
    search_fields = ['raqam', 'ism', 'telefon', 'manzil', 'promokod']
    readonly_fields = ['raqam', 'mahsulotlar_summasi', 'chegirma', 'promokod',
                       'yetkazish_narxi', 'ornatish_narxi', 'jami',
                       'kuryer_lat', 'kuryer_lng', 'kuryer_yangilangan',
                       'yaratilgan', 'yangilangan']
    list_editable = ['holat']
    ordering = ['-yaratilgan']
    inlines = [XaridQatoriInline]


@admin.register(Promokod)
class PromokodAdmin(admin.ModelAdmin):
    list_display = ['kod', 'tur', 'qiymat', 'eng_kam_summa', 'limit',
                    'ishlatilgan', 'boshlanish', 'tugash', 'faol']
    list_filter = ['faol', 'tur']
    search_fields = ['kod', 'tavsif']
    readonly_fields = ['ishlatilgan', 'yaratilgan']
    list_editable = ['faol']
    ordering = ['-yaratilgan']
