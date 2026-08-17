from django.urls import path
from . import views

urlpatterns = [
    path('', views.buyurtmalar_list),
    path('statistika/', views.statistika),
    path('<int:pk>/tayinlash/', views.tayinlash),
    path('<int:pk>/', views.buyurtma_update),
    path('<int:pk>/qabul/', views.qabul),
    path('<int:pk>/natija/', views.natija),
    path('<int:pk>/foto/', views.foto_yuklash),
]
