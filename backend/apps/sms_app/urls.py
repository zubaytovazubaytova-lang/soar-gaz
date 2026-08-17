from django.urls import path
from . import views

urlpatterns = [
    path('', views.sms_list),
    path('yuborish/', views.sms_yuborish),
    path('oqildi/', views.sms_oqildi),
]
