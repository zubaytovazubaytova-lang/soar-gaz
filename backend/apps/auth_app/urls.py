from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('admin/login/', views.admin_login),
    path('admin/otp/', views.admin_otp_tasdiqlash),
    # Access token muddati tugaganda refresh token bilan yangilanadi —
    # mijozdan qayta SMS kod so'ralmasligi uchun.
    path('token/yangilash/', TokenRefreshView.as_view()),
    path('royxat/', views.royxatdan_otish),
    path('otp/yuborish/', views.otp_yuborish),
    path('otp/tasdiqlash/', views.otp_tasdiqlash),
    path('profil/', views.profil),
    path('hududlar/', views.hududlar),
    path('xodim/login/', views.xodim_login),
    path('xodim/profil/', views.xodim_profil),
    path('mijozlar/', views.mijozlar_list),
    path('jurnal/', views.audit_list),
    path('xodimlar/', views.XodimlarView.as_view()),
    path('xodimlar/<int:pk>/', views.XodimDetailView.as_view()),
    path('xodimlar/<int:pk>/kod/', views.xodim_kod_yangila),
]
