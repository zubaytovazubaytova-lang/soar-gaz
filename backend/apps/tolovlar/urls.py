from django.urls import path
from . import views

urlpatterns = [
    path('sorov/', views.sorov_yaratish),
    # Mahsulot (katalog) so'rovlari
    path('mahsulot-sorov/', views.mahsulot_sorov_yaratish),
    path('mahsulot-sorovlar/', views.mahsulot_sorovlar_list),
    path('mahsulot-sorovlar/<int:pk>/', views.mahsulot_sorov_update),
    path('', views.tolovlar_list),
    path('<int:pk>/', views.sorov_update),
    # To'lov tizimi webhooklari
    path('click/prepare/', views.click_prepare),
    path('click/complete/', views.click_complete),
    path('payme/', views.payme_endpoint),
]
