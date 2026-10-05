# execution/urls.py
from django.urls import path
from . import api_views, instructor_views, student_views, director_views
from .api_views import change_password, StudentCreateAPIView

app_name = 'execution'

urlpatterns = [
    # === ИЗМЕНЕНИЕ ПАРОЛЯ ===
    path('auth/change-password/', change_password, name='change_password'),

    # === МЕТОДИСТ ===
    path('methodist/groups/<int:group_id>/complete/', api_views.methodist_complete_group, name='methodist_complete_group'),
    
    # === ИНСТРУКТОР ===
    path('instructor/schedule/', api_views.InstructorScheduleView.as_view(), name='instructor_schedule'),
    path('instructor/schedule/<int:pk>/log/', api_views.log_schedule_action, name='log_schedule_action'),
    path('instructor/grades/<int:group_id>/', api_views.InstructorGradesView.as_view(), name='instructor_grades'),
    path('instructor/grades/', api_views.save_instructor_grades, name='save_instructor_grades'),
    path('instructor/groups/', api_views.instructor_groups_view, name='instructor_groups'),
    path('instructor/groups/<int:group_id>/complete/', api_views.instructor_complete_group, name='instructor_complete_group'),
    path('instructor/log/', api_views.instructor_log_action, name='instructor_log_action'),
    path('instructor/schedule/<int:group_id>/', instructor_views.instructor_schedule_view, name='instructor_schedule'),
    path('instructor/instructing/', instructor_views.instructor_instructing_view, name='instructor_instructing'),
    path('instructor/journal/<int:group_id>/', instructor_views.instructor_journal_view, name='instructor_journal'),

        # === СТУДЕНТ ===
    path('student/modules/', student_views.student_modules, name='student_modules'),
    path('student/confirm/', student_views.student_confirm_action, name='student_confirm_action'),
    path('students/', StudentCreateAPIView.as_view(), name='student-create'),
    path('student/schedule/<int:group_id>/', student_views.student_schedule_view, name='student_schedule'),
    path('student/instructing/', student_views.student_instructing_view, name='student_instructing'),

    # === ДИРЕКТОР ===
    path('director/groups/', director_views.director_groups, name='director_groups'),
    path('director/groups/<int:group_id>/approve/', director_views.director_approve_schedule, name='director_approve_schedule'),
]