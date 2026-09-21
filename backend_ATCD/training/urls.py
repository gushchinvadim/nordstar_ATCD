# training/urls.py
from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [
    path('import-qualifications/', views.import_qualifications_view, name='import_qualifications'),
    path('export-qualifications-template/', views.export_qualifications_template_view, name='export_qualifications_template'),
    path('download-qualifications-template/', views.download_qualifications_template_view, name='download_qualifications_template'),
]