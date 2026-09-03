# docs/urls.py
from . import views, api_views
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
    path('enrollment/<int:enrollment_id>/create-iup/', views.create_iup_view, name='create_iup'),
    path('api/enrollment/<int:enrollment_id>/iup-preview/', views.iup_preview_schedule, name='iup_preview_schedule'),
    path('iup/<int:iup_id>/regenerate/', views.regenerate_iup, name='regenerate_iup'),
    path('group/<int:group_id>/download-folder/', views.download_group_folder, name='download_group_folder'),
    path('group/<int:group_id>/dismissal-reference/', views.dismissal_reference_view, name='dismissal_reference'),
    path('iup/<int:iup_id>/view/', views.view_iup, name='view_iup'),
    path('iup/<int:iup_id>/edit/', views.edit_iup_view, name='edit_iup'),
    path('api/groups/', api_views.groups_list, name='api_groups_list'),
    path('api/me/', api_views.current_user_info, name='api_me'),
    path('api/directions/', api_views.directions_list, name='api_directions_list'),
    path('api/group/<int:group_id>/', api_views.group_detail, name='api_group_detail'),
    # API endpoints для справочников
    path('api/modules/', api_views.modules_list, name='api_modules_list'),
    path('api/staff/', api_views.staff_list, name='api_staff_list'),
    path('api/students/', api_views.students_list, name='api_students_list'),
    path('api/locations/', api_views.locations_list, name='api_locations_list'),
    path('api/groups/create/', api_views.create_group, name='api_create_group'),
    # Старый эндпоинт (для дашборда, оставляем как есть)
    path('api/group/<int:group_id>/', api_views.group_detail, name='api_group_detail'),

    # НОВЫЙ эндпоинт специально для формы редактирования
    path('api/group/<int:group_id>/edit/', api_views.group_detail_edit, name='api_group_detail_edit'),
    path('api/group/<int:group_id>/update/', api_views.update_group, name='api_update_group'),
    # Генерация расписания
    path('api/group/<int:group_id>/generate-schedule/', api_views.generate_group_schedule,
         name='api_generate_schedule'),

]



# Раздача медиа-файлов в режиме DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)