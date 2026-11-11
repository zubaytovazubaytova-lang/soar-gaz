from django.urls import path
from . import views

urlpatterns = [
    path('', views.xabarlar_xodim),                 # xodim: o'z xabarlari
    path('oqildi/', views.xabarlar_oqildi),         # xodim: o'qilgan deb belgilash
    path('admin/', views.xabarlar_admin),           # admin: tarix (GET) va yuborish (POST)
]
