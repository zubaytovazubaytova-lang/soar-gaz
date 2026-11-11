from django.urls import path
from . import operator, views, xizmatlar

urlpatterns = [
    path('', views.buyurtmalar_list),
    path('statistika/', views.statistika),
    # Qo'ng'iroq vazifasi (Ruxsora, Nargiza): arizalar, yo'naltirish, qo'ng'iroqlar jurnali
    path('operator/arizalar/', operator.arizalar),
    path('operator/arizalar/<int:pk>/tayinlash/', operator.ariza_tayinlash),
    path('operator/arizalar/<int:pk>/joy/', operator.ariza_joy),
    path('operator/arizalar/<int:pk>/yaqin/', operator.ariza_yaqin),
    path('operator/arizalar/<int:pk>/yaqin-yuborish/', operator.ariza_yaqin_yuborish),
    path('operator/geokod/', operator.geokod),                    # manzil -> xarita joyi
    path('operator/qongiroqlar/', operator.qongiroqlar),          # qo'ng'iroq vazifasi
    path('<int:pk>/tayinlash/', views.tayinlash),
    path('<int:pk>/', views.buyurtma_update),
    path('<int:pk>/qabul/', views.qabul),
    path('<int:pk>/natija/', views.natija),
    path('<int:pk>/foto/', views.foto_yuklash),
    # Narxnomadan xizmat tanlash va summani tasdiqlash (xodim / admin)
    path('<int:pk>/xizmatlar/', xizmatlar.xizmat_biriktirish),
    path('<int:pk>/summa/', xizmatlar.summa_tasdiqlash),
    path('xizmatlar/<int:xid>/', xizmatlar.xizmat_olib_tashlash),
]
