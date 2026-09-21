# execution/urls.py
from django.urls import path
from . import api_views
from . import student_views
from . import director_views

app_name = 'execution'

urlpatterns = [
    # === ИНСТРУКТОР ===
    path('instructor/schedule/', api_views.InstructorScheduleView.as_view(), name='instructor_schedule'),
    path('instructor/schedule/<int:pk>/log/', api_views.log_schedule_action, name='log_schedule_action'),
    path('instructor/grades/<int:group_id>/', api_views.InstructorGradesView.as_view(), name='instructor_grades'),
    path('instructor/grades/', api_views.save_instructor_grades, name='save_instructor_grades'),
    path('instructor/groups/', api_views.instructor_groups_view, name='instructor_groups'),
    path('instructor/groups/<int:group_id>/complete/', api_views.instructor_complete_group, name='instructor_complete_group'),
    path('instructor/log/', api_views.instructor_log_action, name='instructor_log_action'),

    # === СТУДЕНТ ===
    path('student/modules/', student_views.student_modules, name='student_modules'),
    path('student/confirm/', student_views.student_confirm_action, name='student_confirm_action'),

    # === ДИРЕКТОР ===
    path('director/groups/', director_views.director_groups, name='director_groups'),
    path('director/groups/<int:group_id>/approve/', director_views.director_approve_schedule, name='director_approve_schedule'),
]