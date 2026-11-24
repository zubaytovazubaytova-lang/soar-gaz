from django.urls import path
from . import views, xodim_malumot

urlpatterns = [
    path('hisobot/', views.hisobot_xodim),               # har bir xodim: bugungi o'z hisoboti (GET, POST)
    path('kun/', views.kun_korinishi),                   # kadrlar: davomat + hisobotlar (?sana=)
    path('davomat/', views.davomat_belgilash),           # kadrlar: qo'lda keldi / kelmadi belgilash
    path('eslatma/', views.hisobot_eslatma),
    path('bot-eslatma/', views.bot_eslatma),
    # Kadrlar: xodimlar ma'lumotlari (ishga kirgan sana, tabel, sertifikatlar). Ish haqi — faqat Django panelida
    path('xodimlar/', xodim_malumot.xodimlar),
    path('xodimlar/<int:pk>/', xodim_malumot.xodim),
    path('xodimlar/<int:pk>/sertifikat/', xodim_malumot.sertifikat_qosh),
    path('sertifikat/<int:sid>/', xodim_malumot.sertifikat_ochir),             # kadrlar: Telegram botga ulanmaganlarga xabar             # kadrlar: hisobot topshirmaganlarga xabar
    path('hujjatlar/', views.hujjatlar),                 # kadrlar: reestr (GET), yozuv qo'shish (POST)
    path('hujjatlar/<int:pk>/', views.hujjat_ochir),     # kadrlar: yozuvni o'chirish
]
