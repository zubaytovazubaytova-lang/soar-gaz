from django.urls import path
from . import views

urlpatterns = [
    path('', views.tushum_xodim),                      # xodim: ro'yxat (GET) va kiritish (POST)
    path('admin/', views.tushum_admin),                # admin: hammasi
    path('<int:pk>/qabul/', views.tushum_qabul),
    path('<int:pk>/rad/', views.tushum_rad),
]
