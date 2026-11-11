"""Django admin sayti: direktor (va egasi) uchun «Rahbariyat» bosh sahifasi va xavfsiz kirish.

Direktor `/admin/` ga kiradi. Bu panel SMS kodsiz, faqat parol bilan ochilgani uchun
kirish urinishlari bu yerda cheklanadi: ketma-ket noto'g'ri parolda raqam vaqtincha
to'sib qo'yiladi (hisob bloklanmaydi — hujumchi direktorni butunlay chiqarib tashlay olmasin).
Har kirish va xato urinish Faoliyat jurnaliga yoziladi.
"""
from django.conf import settings
from django.contrib import admin
from django.core.cache import cache
from django.http import HttpResponse
from django.urls import NoReverseMatch, reverse


def _pul(n):
    return f'{int(n or 0):,}'.replace(',', ' ') + " so'm"


def _havola(request, nom, ruxsat, parametr=''):
    """Bo'limga havola — faqat foydalanuvchida ko'rish huquqi bo'lsa (aks holda 403 sahifasiga olib bormasin)."""
    if not request.user.has_perm(ruxsat):
        return ''
    try:
        return reverse(nom) + parametr
    except NoReverseMatch:
        return ''


def rahbariyat_korinishi(request):
    """Django panel bosh sahifasi uchun tayyor (formatlangan) ma'lumot."""
    from apps.auth_app.rahbariyat import yigma

    h = yigma()
    t = h['tushum']
    b = h['buyurtmalar']
    x = h['xodimlar']
    sahifalar = {
        'cash': _havola(request, 'admin:tushum_tushum_changelist', 'tushum.view_tushum', '?holat__exact=kutilmoqda'),
        'joy': _havola(request, 'admin:joylashuv_smena_changelist', 'joylashuv.view_smena'),
        'orders': _havola(request, 'admin:buyurtmalar_buyurtma_changelist', 'buyurtmalar.view_buyurtma'),
    }
    holat_nomi = {'yangi': 'Yangi', 'qabul': 'Qabul qilingan', 'bajarilmoqda': 'Bajarilmoqda',
                  'bajarildi': 'Bajarilgan', 'bekor': 'Bekor'}
    # Tezkor havolalar: barcha jarayon bir joydan. Faqat foydalanuvchida huquq bo'lgan bo'limlar chiqadi.
    havolalar = [(nom, url) for nom, url in [
        ('Kutilayotgan tushumlar', sahifalar['cash']),
        ('Yangi buyurtmalar', _havola(request, 'admin:buyurtmalar_buyurtma_changelist',
                                      'buyurtmalar.view_buyurtma', '?holat__exact=yangi')),
        ('Xodimlar xaritasi', _havola(request, 'admin:xarita', 'joylashuv.view_smena')),
        ('Xodimlarga xabar', _havola(request, 'admin:auth_app_xodim_changelist', 'aloqa.add_xabar')),
        ('Mijozlar', _havola(request, 'admin:auth_app_mijoz_changelist', 'auth_app.view_mijoz')),
        ('Narxnoma', _havola(request, 'admin:narxnoma_narxnoma_changelist', 'narxnoma.view_narxnoma')),
        ('Faoliyat jurnali', _havola(request, 'admin:auth_app_audityozuv_changelist', 'auth_app.view_audityozuv')),
    ] if url]
    return {
        'havolalar': havolalar,
        'diqqat': [dict(d, havola=sahifalar.get(d['sahifa'], '')) for d in h['diqqat']],
        'kartalar': [
            {'nom': 'Aholi: qabul qilingan (bu oy)', 'qiymat': _pul(t['aholi']['oy_qabul']),
             'izoh': f"topshirilishi kutilmoqda: {_pul(t['aholi']['kutilmoqda'])}"},
            {'nom': 'Ulgurji: qabul qilingan (bu oy)', 'qiymat': _pul(t['ulgurji']['oy_qabul']),
             'izoh': f"topshirilishi kutilmoqda: {_pul(t['ulgurji']['kutilmoqda'])}"},
            {'nom': 'Topshirilishi kutilayotgan pul',
             'qiymat': _pul(t['aholi']['kutilmoqda'] + t['ulgurji']['kutilmoqda'] + t['boshqa']['kutilmoqda']),
             'izoh': 'xodimlarda turibdi'},
            {'nom': 'Mijozlardan olinmagan qoldiq',
             'qiymat': _pul(b['qoldiq']['aholi'] + b['qoldiq']['ulgurji']), 'izoh': 'tasdiqlangan summadan'},
        ],
        'buyurtma': [(holat_nomi[k], b['holatlar'].get(k, 0)) for k in holat_nomi] + [
            ('Xodim tayinlanmagan (yangi)', b['tayinlanmagan']),
            ('Bu oy tasdiqlangan: aholi', _pul(b['oy_tasdiqlangan']['aholi'])),
            ('Bu oy tasdiqlangan: ulgurji', _pul(b['oy_tasdiqlangan']['ulgurji'])),
        ],
        'xodim': [('Faol xodimlar', x['faol']), ('Hozir smenada', x['smenada']),
                  ('Aloqada', x['aloqada']), ('Aloqada emas', x['aloqasiz'])],
        'qarz': [dict(q, summa_matn=_pul(q['summa'])) for q in h['qarzdorlar']],
        'faoliyat': h['faoliyat'],
    }


class SoarAdminSite(admin.AdminSite):
    @staticmethod
    def _xato_sababi(request):
        """Jurnalga yoziladigan sabab. Django parol to'g'ri bo'lsa ham xodim huquqi (is_staff)
        bo'lmagan hisobni xuddi parol xatosidek rad etadi — egasi chalg'ib qolmasligi uchun
        jurnalda farqlanadi. Foydalanuvchiga ko'rsatiladigan javob o'zgarmaydi."""
        from apps.auth_app.models import Foydalanuvchi

        telefon = (request.POST.get('username') or '').replace(' ', '')[:30]
        parol = request.POST.get('password') or ''
        user = Foydalanuvchi.objects.filter(telefon=telefon).first()
        if user is not None and user.check_password(parol):
            if not user.is_active:
                return f"Django paneli: {telefon} — parol to'g'ri, lekin hisob faol emas"
            if not user.is_staff:
                return (f"Django paneli: {telefon} — parol to'g'ri, lekin Django paneliga ruxsat yo'q "
                        f"(egasi «Xodim huquqi / is_staff» va «Direktor» guruhini berishi kerak)")
        return f"Django paneli: {telefon} — noto'g'ri parol"

    site_header = 'Soar Gaz — Django paneli (egasi uchun)'
    site_title = 'Soar Gaz'
    index_title = 'Rahbariyat'
    index_template = 'rahbariyat/admin_index.html'

    def get_urls(self):
        from django.urls import path
        return [
            path('xarita/', self.admin_view(self.xarita_sahifa), name='xarita'),
            path('xarita/malumot/', self.admin_view(self.xarita_malumot), name='xarita_malumot'),
        ] + super().get_urls()

    def xarita_sahifa(self, request):
        """Smenadagi xodimlar xaritasi (xodimlar portali kabi OpenStreetMap + Leaflet)."""
        from django.core.exceptions import PermissionDenied
        from django.template.response import TemplateResponse

        if not request.user.has_perm('joylashuv.view_smena'):
            raise PermissionDenied
        kontekst = dict(self.each_context(request), title='Xodimlar xaritasi')
        return TemplateResponse(request, 'rahbariyat/xarita.html', kontekst)

    def xarita_malumot(self, request):
        from django.core.exceptions import PermissionDenied
        from django.core.serializers.json import DjangoJSONEncoder
        from django.http import JsonResponse

        from apps.joylashuv.views import _korildi_yoz, smenadagilar

        if not request.user.has_perm('joylashuv.view_smena'):
            raise PermissionDenied
        natija = smenadagilar()
        _korildi_yoz(request, 'royxat', 'xarita (smenadagi xodimlar, Django paneli)')   # 10 daqiqada bir marta
        return JsonResponse(natija, safe=False, encoder=DjangoJSONEncoder)

    def index(self, request, extra_context=None):
        extra = dict(extra_context or {})
        if getattr(request.user, 'rol', '') == 'admin':
            extra['rahbariyat'] = rahbariyat_korinishi(request)
        return super().index(request, extra)

    def login(self, request, extra_context=None):
        from apps.auth_app.models import audit_yoz

        limit = settings.ADMIN_URINISH_LIMIT
        daqiqa = settings.OTP_BLOK_DAQIQA
        kalit = None
        if request.method == 'POST':
            telefon = (request.POST.get('username') or '').replace(' ', '')[:30]
            kalit = f'django_admin:urinish:{telefon}'
            if cache.get(kalit, 0) >= limit:
                audit_yoz(request, 'ruxsat_rad', f'Django paneli: {telefon} — urinishlar chegarasi')
                return HttpResponse(
                    f"Juda ko'p noto'g'ri urinish. {daqiqa} daqiqadan keyin qayta urinib ko'ring.",
                    status=429, content_type='text/plain; charset=utf-8')

        javob = super().login(request, extra_context)

        if kalit is not None:
            if javob.status_code in (301, 302):         # muvaffaqiyatli kirish
                cache.delete(kalit)
                audit_yoz(request, 'kirish', 'Django paneliga kirdi')
            else:                                         # forma qayta ko'rsatildi
                cache.set(kalit, cache.get(kalit, 0) + 1, daqiqa * 60)
                audit_yoz(request, 'kirish_xato', self._xato_sababi(request))
        return javob
