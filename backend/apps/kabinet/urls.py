from django.urls import path
from . import views

urlpatterns = [
    # 1. Bosh sahifa
    path('obzor/', views.obzor),
    # 2. Buyurtmalar
    path('buyurtmalar/', views.buyurtmalarim),
    path('buyurtmalar/<int:pk>/', views.buyurtma_detal),
    # 3. Obyektlar va uskunalar
    path('obyektlar/', views.obyektlar),
    path('obyektlar/<int:pk>/', views.obyekt_detal),
    path('uskunalar/', views.uskunalar),
    path('uskunalar/<int:pk>/', views.uskuna_detal),
    # 4. Hisoblagichlar
    path('hisoblagichlar/', views.hisoblagichlar),
    path('hisoblagichlar/<int:pk>/', views.hisoblagich_detal),
    path('hisoblagichlar/<int:pk>/tekshiruv/', views.tekshiruvga_yozilish),
    # 5. To'lovlar
    path('tolovlar/', views.tolovlarim),
    # 5b. Do'kon xaridlari
    path('xaridlarim/', views.xaridlarim),
    path('xaridlarim/<str:raqam>/', views.xarid_detal),
    # 6. Hujjatlar
    path('hujjatlar/', views.hujjatlar),
    path('hujjat/<str:token>/', views.hujjat_ochish),
    # 7. Bildirishnomalar
    path('bildirishnomalar/', views.bildirishnomalar),
    path('bildirishnomalar/oqildi/', views.bildirishnoma_oqildi),
    # 8. Sharhlar
    path('sharhlar/', views.sharhlar),
    path('sharhlar/<int:pk>/', views.sharh_detal),
    # 9. Yordam markazi
    path('yordam/murojaatlar/', views.murojaatlar),
    path('yordam/murojaatlar/<int:pk>/xabar/', views.murojaat_xabar),
    path('yordam/murojaatlar/<int:pk>/yopish/', views.murojaat_yopish),
    path('yordam/faq/', views.faq),
    path('yordam/qongiroq/', views.qongiroq_sorovi),
    # 10. Sozlamalar
    path('sozlamalar/', views.sozlamalar),
    path('hisob/ochirish/', views.hisobni_ochirish),
]
