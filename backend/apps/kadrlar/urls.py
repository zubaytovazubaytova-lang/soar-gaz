from django.urls import path
from . import views

urlpatterns = [
    path('hisobot/', views.hisobot_xodim),               # har bir xodim: bugungi o'z hisoboti (GET, POST)
    path('kun/', views.kun_korinishi),                   # kadrlar: davomat + hisobotlar (?sana=)
    path('davomat/', views.davomat_belgilash),           # kadrlar: qo'lda keldi / kelmadi belgilash
    path('eslatma/', views.hisobot_eslatma),             # kadrlar: hisobot topshirmaganlarga xabar
    path('hujjatlar/', views.hujjatlar),                 # kadrlar: reestr (GET), yozuv qo'shish (POST)
    path('hujjatlar/<int:pk>/', views.hujjat_ochir),     # kadrlar: yozuvni o'chirish
]
