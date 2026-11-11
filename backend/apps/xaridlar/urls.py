from django.urls import path
from . import views

urlpatterns = [
    path('', views.xaridlar_list),
    path('statistika/', views.statistika),
    path('promokod/', views.promokod_tekshir),
    path('narxlar/', views.narxlar),
    # Kuryer interfeysi
    path('kuryer/', views.kuryer_royxati),
    path('<str:raqam>/qabul/', views.kuryer_qabul),
    path('<str:raqam>/holat/', views.kuryer_holat),
    path('<str:raqam>/muammo/', views.yetkazish_muammosi),
    path('<str:raqam>/qayta/', views.qayta_yetkazish),
    path('<str:raqam>/tolov/', views.tolov_boshqarish),
    path('<str:raqam>/korish/', views.xarid_tasdiqlash),
    path('<str:raqam>/kuryer/', views.kuryer_joylashuvi),
    path('<str:raqam>/', views.xarid_detail),
]
