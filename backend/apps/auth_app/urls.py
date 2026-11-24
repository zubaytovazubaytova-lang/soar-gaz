from django.urls import path
from . import rahbariyat, telegram_kirish, views, xodim_telegram

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
    # Telegram orqali kirish / ro'yxatdan o'tish (kodsiz, tekin): apps/auth_app/telegram_kirish.py
    path('telegram/holat/', telegram_kirish.holat),
    path('telegram/boshlash/', telegram_kirish.boshlash),
    path('telegram/callback/', telegram_kirish.callback),
    path('telegram/bot/boshlash/', telegram_kirish.bot_boshlash),     # bot orqali (tanlov sahifasisiz)
    path('telegram/bot/holat/', telegram_kirish.bot_holat),
    path('profil/', views.profil),
    path('tasdiq-kodi/', views.tasdiq_kodi_yuborish),
    path('hududlar/', views.hududlar),
    path('xodim/login/', views.xodim_login),
    path('xodim/profil/', views.xodim_profil),
    path('xodim/telegram-havola/', xodim_telegram.havola),     # xodim: botga ulanish (shaxsiy havola)
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
