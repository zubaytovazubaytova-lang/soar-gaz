from django.urls import path
from . import views

urlpatterns = [
    # Xodim
    path('smena/', views.smena_holat),
    path('smena/boshlash/', views.smena_boshlash),
    path('smena/tugatish/', views.smena_tugatish),
    path('nuqta/', views.nuqta_yubor),
    # Admin
    path('royxat/', views.joylashuv_royxat),
    path('yol/<int:xodim_id>/', views.joylashuv_yol),
]
