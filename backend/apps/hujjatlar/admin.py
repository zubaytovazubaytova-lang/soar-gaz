from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.utils import timezone

from apps.auth_app.models import audit_yoz
from .models import Kvitansiya, Shartnoma, Sozlama


@admin.register(Sozlama)
class SozlamaAdmin(admin.ModelAdmin):
    """Kompaniya rekvizitlari va shartnoma matni. Yagona yozuv: qo'shish va o'chirish yo'q.

    Shartnoma matnini kompaniyaning tasdiqlangan yuridik matni bilan almashtirib,
    «Shartnoma matni tasdiqlangan» belgisini qo'ymaguncha xodimlar shartnoma tuza olmaydi."""
    fieldsets = (
        ('Kompaniya rekvizitlari (kvitansiya va shartnomada chiqadi)', {
            'fields': ('kompaniya_nomi', 'stir', 'manzil', 'telefon', 'bank_nomi', 'hisob_raqam', 'mfo',
                       'direktor', 'servis_boshligi')}),
        ('Kvitansiya', {'fields': ('kvitansiya_izoh',)}),
        ('Shartnoma', {'fields': ('shartnoma_matni', 'shartnoma_tasdiqlangan'),
                       'description': "Matnni kompaniyaning tasdiqlangan shartnomasi bilan almashtiring. "
                                      "Namunaviy matn faqat tuzilmani ko'rsatish uchun."}),
    )

    def has_add_permission(self, request):
        return not Sozlama.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class BekorForm(ActionForm):
    sabab = forms.CharField(required=False, max_length=255, label='Bekor qilish sababi',
                            widget=forms.TextInput(attrs={'size': 40, 'placeholder': 'Faqat "Bekor qilish" uchun'}))


class FaqatOqish(admin.ModelAdmin):
    """Hujjatlar Django panelida o'zgartirilmaydi va o'chirilmaydi: xato bo'lsa BEKOR qilinadi."""
    action_form = BekorForm
    actions = ['bekor_qilish']

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    bekor_huquqi = ''

    def has_bekor_permission(self, request):
        return request.user.has_perm(f'hujjatlar.{self.bekor_huquqi}')


@admin.register(Kvitansiya)
class KvitansiyaAdmin(FaqatOqish):
    bekor_huquqi = 'kvitansiya_bekor'
    list_display = ['raqam', 'yaratilgan', 'mijoz_ism', 'mijoz_telefon', 'manzil', 'summa', 'xodim',
                    'yangi_mijoz', 'holat', 'sms_holat']
    list_filter = ['holat', 'sms_holat', 'yangi_mijoz', 'usul_nomi']
    search_fields = ['raqam', 'mijoz_ism', 'mijoz_telefon', 'manzil']
    date_hierarchy = 'yaratilgan'

    @admin.action(description='BEKOR qilish (sababni yuqoridagi maydonga yozing)', permissions=['bekor'])
    def bekor_qilish(self, request, queryset):
        sabab = (request.POST.get('sabab') or '').strip()[:255]
        if not sabab:
            self.message_user(request, 'Bekor qilish sababini yozing.', messages.ERROR)
            return
        soni = 0
        for k in queryset.filter(holat='amal'):
            Kvitansiya.objects.filter(pk=k.pk).update(holat='bekor', bekor_sababi=sabab,
                                                       bekor_vaqti=timezone.now(), bekor_qilgan=request.user)
            audit_yoz(request, 'kvitansiya_bekor', f'{k.raqam} — {sabab}')
            soni += 1
        self.message_user(request, f'{soni} ta kvitansiya bekor qilindi.', messages.SUCCESS)


@admin.register(Shartnoma)
class ShartnomaAdmin(FaqatOqish):
    bekor_huquqi = 'shartnoma_bekor'
    list_display = ['raqam', 'yaratilgan', 'mijoz_ism', 'mijoz_telefon', 'manzil', 'summa', 'xodim', 'holat']
    list_filter = ['holat']
    search_fields = ['raqam', 'mijoz_ism', 'mijoz_telefon', 'manzil']
    date_hierarchy = 'yaratilgan'
    exclude = ['kod_xesh']          # tasdiqlash kodi xeshi ko'rinmaydi

    @admin.action(description='BEKOR qilish (sababni yuqoridagi maydonga yozing)', permissions=['bekor'])
    def bekor_qilish(self, request, queryset):
        sabab = (request.POST.get('sabab') or '').strip()[:255]
        if not sabab:
            self.message_user(request, 'Bekor qilish sababini yozing.', messages.ERROR)
            return
        soni = 0
        for s in queryset.exclude(holat='bekor'):
            Shartnoma.objects.filter(pk=s.pk).update(holat='bekor', bekor_sababi=sabab,
                                                      bekor_vaqti=timezone.now(), kod_xesh='')
            audit_yoz(request, 'shartnoma_bekor', f'{s.raqam} — {sabab}')
            soni += 1
        self.message_user(request, f'{soni} ta shartnoma bekor qilindi.', messages.SUCCESS)


from .models import HujjatLoyiha  # noqa: E402


@admin.register(HujjatLoyiha)
class HujjatLoyihaAdmin(admin.ModelAdmin):
    """Tayyorlangan hujjatlar jurnali: faqat ko'rish (hujjatni xodim kabinetidan yuklaydi va yuboradi)."""
    list_display = ['nom', 'turi', 'ariza', 'buyurtma', 'tayyorlagan', 'yaratilgan', 'yuborilgan', 'yuborgan']
    list_filter = ['turi']
    search_fields = ['nom']

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


from .models import Topshiriq  # noqa: E402


@admin.register(Topshiriq)
class TopshiriqAdmin(admin.ModelAdmin):
    """Ichki topshiriqlar jurnali: faqat ko'rish (topshiriqni xodimlar kabinetidan yuboradi va bajaradi)."""
    list_display = ['sarlavha', 'kim', 'kimga', 'holat', 'muddat', 'yaratilgan', 'bajarilgan']
    list_filter = ['holat']
    search_fields = ['sarlavha', 'kim__ism', 'kimga__ism']

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
