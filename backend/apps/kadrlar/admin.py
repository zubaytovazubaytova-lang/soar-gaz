from django.contrib import admin

from .models import KunlikHisobot, XodimHujjati


@admin.register(KunlikHisobot)
class KunlikHisobotAdmin(admin.ModelAdmin):
    list_display = ['sana', 'xodim', 'joy', 'ish']
    list_filter = ['sana']
    search_fields = ['xodim__ism', 'xodim__telefon', 'joy', 'ish']
    date_hierarchy = 'sana'
    autocomplete_fields = []

    # Hisobot — xodimning o'z so'zi: panelda ham o'zgartirilmaydi
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


@admin.register(XodimHujjati)
class XodimHujjatiAdmin(admin.ModelAdmin):
    list_display = ['xodim', 'turi', 'raqami', 'sana', 'amal_qiladi', 'kiritgan']
    list_filter = ['turi']
    search_fields = ['xodim__ism', 'xodim__telefon', 'raqami']
    raw_id_fields = ['xodim', 'kiritgan']
