from django.urls import path
from . import views

urlpatterns = [
    path('weekly/', views.weekly_report, name='weekly_report'),
    path('monthly/', views.monthly_report, name='monthly_report'),
    path('custom/', views.custom_report, name='custom_report'),

    path('weekly/pdf/', views.weekly_report_pdf, name='weekly_report_pdf'),
    path('monthly/pdf/', views.monthly_report_pdf, name='monthly_report_pdf'),
    path('custom/pdf/', views.custom_report_pdf, name='custom_report_pdf'),
]
