from django.contrib import admin
from .models import SmsXabar


@admin.register(SmsXabar)
class SmsXabarAdmin(admin.ModelAdmin):
    list_display = ['mijoz', 'matn', 'oqildi', 'yaratilgan']
    list_filter = ['oqildi']
    search_fields = ['mijoz__telefon', 'matn']
    ordering = ['-yaratilgan']
    # __str__ mijoz.telefon ni o'qiydi — JOIN'siz har qator uchun so'rov
    list_select_related = ('mijoz',)
