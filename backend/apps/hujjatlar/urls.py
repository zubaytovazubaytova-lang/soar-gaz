from django.urls import path
from . import ish, topshiriq, views

urlpatterns = [
    # Hujjatlar bilan ishlovchi xodim: mijozlardan kelgan ishlar, hujjat tayyorlash va mijozga yuborish
    path('ish/', ish.ishlar),
    path('ish/hujjatlar/', ish.tayyor_hujjatlar),                   # «Mijozga yuborish» bo'limi ro'yxati
    path('ish/hujjat/<int:pk>/', ish.hujjat_ochirish),
    path('ish/hujjat/<int:pk>/yuborish/', ish.hujjat_yuborish),
    path('ish/<str:kalit>/holat/', ish.ish_holat),
    path('ish/<str:kalit>/hujjat/', ish.hujjat_yuklash),
    # Ichki topshiriqlar: Kadrlar/call center -> hujjatchi, hujjatchi -> o'ziga; natija fayli
    path('topshiriq/', topshiriq.topshiriqlar),
    path('topshiriq/<int:pk>/holat/', topshiriq.holat),
    path('topshiriq/<int:pk>/bajarildi/', topshiriq.bajarildi),
    path('topshiriq/<int:pk>/fayl/<str:tur>/', topshiriq.fayl_olish),
    path('kvitansiya/', views.kvitansiyalar),                     # GET ro'yxat, POST chiqarish
    path('kvitansiya/<int:pk>/sms/', views.kvitansiya_sms),
    path('kvitansiya/<int:pk>/bekor/', views.kvitansiya_bekor),     # faqat administrator
    path('shartnoma/', views.shartnomalar),                         # GET ro'yxat, POST tuzish
    path('shartnoma/<int:pk>/kod/', views.shartnoma_kod),           # SMS kod yuborish
    path('shartnoma/<int:pk>/tasdiq/', views.shartnoma_tasdiq),     # mijoz aytgan kodni kiritish
    path('shartnoma/<int:pk>/qogoz/', views.shartnoma_qogoz),
    path('shartnoma/<int:pk>/bekor/', views.shartnoma_bekor),
]
