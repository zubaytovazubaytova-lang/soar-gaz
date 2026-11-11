from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm

from .hal import ALLAQACHON, OK, TOPILMADI, hal_qil
from .models import Tushum


class HalForm(ActionForm):
    """Amallar satri yonida rad etish sababi uchun maydon."""
    sabab = forms.CharField(required=False, max_length=255, label='Rad etish sababi',
                            widget=forms.TextInput(attrs={'size': 40, 'placeholder': 'Faqat "Rad etish" uchun'}))


@admin.register(Tushum)
class TushumAdmin(admin.ModelAdmin):
    """Pul yozuvlari Django panelida O'ZGARTIRILMAYDI (qo'shish, tahrirlash, o'chirish yo'q):
    hisob "kim, qachon, qancha" aniq qolishi kerak. Faqat `hal_qilish` huquqi borlar
    (direktor, egasi) kutilayotgan yozuvni qabul qiladi yoki sabab bilan rad etadi — bu
    boshqaruv panelidagi qoida bilan bir xil va Faoliyat jurnaliga yoziladi."""
    list_display = ['yaratilgan', 'xodim', 'summa', 'ish_turi', 'usul', 'tarmoq', 'holat',
                    'hal_qilgan', 'hal_vaqti']
    list_filter = ['holat', 'tarmoq', 'usul']
    search_fields = ['xodim__ism', 'xodim__telefon', 'izoh', 'ish_turi']
    date_hierarchy = 'yaratilgan'
    action_form = HalForm
    actions = ['qabul_qilish', 'rad_etish']

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def has_hal_qilish_permission(self, request):
        return request.user.has_perm('tushum.hal_qilish')

    def _hal_qil(self, request, queryset, holat, sabab=''):
        ok = 0
        for pk in queryset.values_list('pk', flat=True):
            natija, _t = hal_qil(request, pk, holat, sabab)
            if natija == OK:
                ok += 1
            elif natija == ALLAQACHON:
                self.message_user(request, f'#{pk}: allaqachon hal qilingan', messages.WARNING)
            elif natija == TOPILMADI:
                self.message_user(request, f'#{pk}: topilmadi', messages.WARNING)
        return ok

    @admin.action(description="QABUL qilish (pulni qo'limga oldim)", permissions=['hal_qilish'])
    def qabul_qilish(self, request, queryset):
        ok = self._hal_qil(request, queryset, 'qabul')
        if ok:
            self.message_user(request, f'{ok} ta tushum qabul qilindi.', messages.SUCCESS)

    @admin.action(description='RAD etish (sababni yuqoridagi maydonga yozing)', permissions=['hal_qilish'])
    def rad_etish(self, request, queryset):
        sabab = (request.POST.get('sabab') or '').strip()[:255]
        if not sabab:
            self.message_user(request, 'Rad etish sababini yozing (amallar satridagi maydon).', messages.ERROR)
            return
        ok = self._hal_qil(request, queryset, 'rad', sabab)
        if ok:
            self.message_user(request, f'{ok} ta tushum rad etildi.', messages.SUCCESS)
