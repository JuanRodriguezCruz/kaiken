from django.urls import path

from . import views

urlpatterns = [
    path('api/tenders/', views.tender_list, name='tender_list'),
    path('api/tenders/<str:identifier>/', views.tender_detail, name='tender_detail'),
    # Rutas públicas para vistas HTML
    path('tenders/', views.tender_list, name='tender_list_html'),
    path('tenders/new/', views.tender_create, name='tender_create'),
    path('tenders/<str:identifier>/', views.tender_detail, name='tender_detail_html'),
]


