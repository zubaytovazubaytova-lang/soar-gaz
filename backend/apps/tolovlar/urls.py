from django.urls import path
from . import bank, views

urlpatterns = [
    path('sorov/', views.sorov_yaratish),
    # Mahsulot (katalog) so'rovlari
    path('mahsulot-sorov/', views.mahsulot_sorov_yaratish),
    # Metrologiya bo'limi arizasi (ochiq)
    path('metrologiya-ariza/', views.metrologiya_ariza_yaratish),
    path('mahsulot-sorovlar/', views.mahsulot_sorovlar_list),
    path('mahsulot-sorovlar/<int:pk>/', views.mahsulot_sorov_update),
    path('', views.tolovlar_list),
    path('<int:pk>/', views.sorov_update),
    # To'lov tizimi webhooklari
    path('click/prepare/', views.click_prepare),
    path('click/complete/', views.click_complete),
    path('payme/', views.payme_endpoint),
    # Bank (hisob raqam) orqali to'lov: chek yuklash va tasdiqlash
    path('bank/buyurtma/<int:pk>/', bank.buyurtma_bank_tolovi),
    path('bank/xarid/<str:raqam>/', bank.xarid_bank_tolovi),
    path('bank/rekvizitlar/', bank.rekvizitlar_ochiq),
    path('click/buyurtma/<int:pk>/', bank.buyurtma_click),
    path('bank/cheklar/', bank.cheklar),
    path('bank/click-tolovlar/', bank.click_tolovlar),
    path('bank/cheklar/<int:pk>/chek/', bank.chek_fayli),
    path('bank/cheklar/<int:pk>/tekshir/', bank.chek_tekshir),
]
