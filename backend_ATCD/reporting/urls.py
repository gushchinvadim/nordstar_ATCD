# reporting/urls.py
from django.urls import path
from . import views

app_name = 'reporting'

urlpatterns = [
    path('rauc/save-excel/<int:group_id>/', views.save_rauc_excel, name='save_rauc_excel'),
    path('rauc/save-xml/<int:group_id>/', views.save_rauc_xml, name='save_rauc_xml'),
    path('rauc/preview-xml/<path:file_path>/', views.preview_rauc_xml, name='preview_rauc_xml'),
    path('rauc/download/<path:file_path>/', views.download_rauc_file, name='download_rauc_file'),
    path('frdo/save-excel/<int:group_id>/', views.save_frdo_excel, name='save_frdo_excel'),
    path('frdo/download/<path:file_path>/', views.download_frdo_file, name='download_frdo_file'),
]