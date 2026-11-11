from django.urls import path
from . import views

urlpatterns = [
    path('metrologiya/', views.metrologiya_narxlar),              # OCHIQ (faqat o'qish): sayt uchun narxlar
    path('ochiq/', views.ochiq_narxnomalar),                      # OCHIQ (faqat o'qish): sayt "Narxnoma" oynasi
    path('', views.narxnoma_royxat),                              # xodim va admin: ko'rish
    path('admin/', views.narxnoma_admin),                         # admin: hammasi (nofaol qatorlar bilan)
    path('<int:pk>/', views.narxnoma_yangila),                    # admin: sarlavha, sana, eslatma
    path('<int:pk>/qator/', views.qator_qosh),                    # admin: yangi qator
    path('qator/<int:pk>/', views.qator_yangila),                 # admin: qatorni o'zgartirish
]
