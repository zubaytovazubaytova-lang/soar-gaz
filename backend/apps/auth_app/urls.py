from django.urls import path
from . import rahbariyat, views

urlpatterns = [
    path('admin/login/', views.admin_login),
    path('admin/otp/', views.admin_otp_tasdiqlash),
    # Access token muddati tugaganda refresh token bilan yangilanadi —
    # mijozdan qayta SMS kod so'ralmasligi uchun.
    path('token/yangilash/', views.token_yangilash),
    path('chiqish/', views.chiqish),
    path('royxat/', views.royxatdan_otish),
    path('otp/yuborish/', views.otp_yuborish),
    path('otp/tasdiqlash/', views.otp_tasdiqlash),
    path('profil/', views.profil),
    path('tasdiq-kodi/', views.tasdiq_kodi_yuborish),
    path('hududlar/', views.hududlar),
    path('xodim/login/', views.xodim_login),
    path('xodim/profil/', views.xodim_profil),
    path('xodim/sertifikatlar/', views.xodim_sertifikatlar),
    path('xodim/ish-haqi/', views.xodim_ish_haqi),
    path('mijozlar/', views.mijozlar_list),
    path('jurnal/', views.audit_list),
    path('xodimlar/', views.XodimlarView.as_view()),
    path('xodimlar/<int:pk>/', views.XodimDetailView.as_view()),
    path('xodimlar/<int:pk>/kod/', views.xodim_kod_yangila),
    # Egasi: foydalanuvchi nomidan faqat o'qish rejimida ko'rish
    path('korish/<int:pk>/', views.korish_boshlash),
    # Rahbariyat bosh sahifasi (direktor va egasi): umumiy ko'rinish, faqat o'qish
    path('rahbariyat/', rahbariyat.rahbariyat),
]
