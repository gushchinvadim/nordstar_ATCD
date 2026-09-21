# docs/api_urls.py
from django.urls import path
from . import api_views

app_name = 'docs_api'

urlpatterns = [
    # === ПОЛЬЗОВАТЕЛЬ И СПРАВОЧНИКИ ===
    path('me/', api_views.current_user_info, name='api_me'),
    path('me/roles/', api_views.user_roles, name='user_roles'),
    path('directions/', api_views.directions_list, name='api_directions_list'),
    path('modules/', api_views.modules_list, name='api_modules_list'),
    path('staff/', api_views.staff_list, name='api_staff_list'),
    path('students/', api_views.students_list, name='api_students_list'),
    path('locations/', api_views.locations_list, name='api_locations_list'),

    # === УПРАВЛЕНИЕ ГРУППАМИ ===
    path('groups/', api_views.groups_list, name='api_groups_list'),
    path('groups/create/', api_views.create_group, name='api_create_group'),
    path('group/<int:group_id>/', api_views.group_detail, name='api_group_detail'),
    path('group/<int:group_id>/edit/', api_views.group_detail_edit, name='api_group_detail_edit'),
    path('group/<int:group_id>/update/', api_views.update_group, name='api_update_group'),
    path('group/<int:group_id>/generate-schedule/', api_views.generate_group_schedule, name='api_generate_schedule'),

    # === НОВОЕ: СПРАВКА ДЛЯ ЛЕНДИНГА ===
    path('help/content/', api_views.get_help_content, name='api_help_content'),
]