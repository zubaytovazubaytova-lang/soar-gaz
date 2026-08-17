from django.urls import path

from . import views

urlpatterns = [
    path('narxlar/', views.narxlar),
    path('media/', views.media),
    path('hujjatlar/<slug:kalit>/', views.hujjatlar),
    path('hujjat/<str:token>/', views.hujjat_ochish),
]
