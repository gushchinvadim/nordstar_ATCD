# docs/urls.py
from . import views
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

app_name = 'docs'

urlpatterns = [
    path('schedule/<int:group_id>/', views.schedule_view, name='schedule'),
    path('enrollment-order/<int:group_id>/', views.enrollment_order_view, name='enrollment_order'),
    path('save-document/<int:group_id>/', views.save_document_view, name='save_document'),
    path('send-order-email/<int:group_id>/', views.send_enrollment_order_email, name='send_order_email'),
    path('send-schedule-email/<int:group_id>/', views.send_schedule_email, name='send_schedule_email'),
    path('journal/<int:group_id>/', views.journal_view, name='journal'),
    path('land-training-task/<int:group_id>/', views.land_training_task_view, name='land_training_task'),
    path('water-training-task/<int:group_id>/', views.water_training_task_view, name='water_training_task'),
    path('grades/<int:group_id>/', views.group_grades_view, name='group_grades'),
    path('complete-enrollment/<int:enrollment_id>/', views.complete_enrollment, name='complete_enrollment'),
    path('dismiss-enrollments/<int:group_id>/', views.dismiss_enrollments, name='dismiss_enrollments'),
    path('dismissal-ok/<int:group_id>/', views.dismissal_ok_view, name='dismissal_ok'),
    path('dismissal-ot/<int:group_id>/', views.dismissal_ot_view, name='dismissal_ot'),
    path('complete-all/<int:group_id>/', views.complete_all_enrollments, name='complete_all_enrollments'),
    path('download/<path:file_path>/', views.download_document, name='download_document'),
    path('dashboard/<int:group_id>/', views.group_documents_dashboard, name='documents_dashboard'),
    path('generate-all/<int:group_id>/', views.generate_all_documents, name='generate_all_documents'),
    path('dismissal-ot-list/<int:group_id>/', views.dismissal_ot_list_view, name='dismissal_ot_list'),  # <-- ДОБАВИТЬ
    path('group/<int:group_id>/certificate/', views.certificate_batch_view, name='certificate_batch'),

]

# Раздача медиа-файлов в режиме DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)