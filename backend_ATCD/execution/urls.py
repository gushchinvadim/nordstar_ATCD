# execution/urls.py
from django.urls import path
from . import api_views, instructor_views, student_views, director_views, methodist_views, instructor_management, funding
from .api_views import change_password, StudentCreateAPIView

app_name = 'execution'

urlpatterns = [
    path('methodist/funding/references/', funding.methodist_funding_references, name='funding_references'),
    path('methodist/groups/<int:group_id>/funding/', funding.group_funding, name='group_funding'),
    path('methodist/instructor-subjects/', instructor_management.add_instructor_subject, name='add_instructor_subject'),
    path('methodist/instructor-section-mappings/', instructor_management.instructor_section_mappings, name='instructor_section_mappings'),
    path('methodist/instructor-section-mappings/<int:pk>/', instructor_management.update_instructor_section_mapping, name='update_instructor_section_mapping'),
    path('methodist/instructors/references/', instructor_management.instructor_references, name='instructor_references'),
    path('methodist/instructors/', instructor_management.instructors, name='manage_instructors'),
    path('methodist/instructors/<int:pk>/', instructor_management.instructor_detail, name='manage_instructor'),
    path('methodist/instructors/<int:pk>/qualifications/', instructor_management.add_instructor_qualification, name='add_instructor_qualification'),
    path('methodist/instructors/<int:pk>/account/', instructor_management.instructor_account, name='instructor_account'),
    path('methodist/qualifications/<int:pk>/confirm/', instructor_management.confirm_instructor_qualification, name='confirm_instructor_qualification'),
    path('methodist/qualifications/<int:pk>/revoke/', instructor_management.revoke_instructor_qualification, name='revoke_instructor_qualification'),
    path('methodist/groups/<int:group_id>/cancel/', methodist_views.cancel_group, name='methodist_cancel_group'),
    path('methodist/students/', methodist_views.StudentList.as_view(), name='methodist_students'),
    path('methodist/students/<int:pk>/', methodist_views.StudentDetail.as_view(), name='methodist_student'),
    path('methodist/students/<int:pk>/reset-password/', methodist_views.reset_student_password, name='methodist_student_reset'),
    path('methodist/groups/<int:group_id>/archive/', methodist_views.archive_group, name='methodist_archive_group'),
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

    path('director/cancelled-groups/', director_views.director_cancelled_groups, name='director_cancelled_groups'),
    path('director/cancelled-groups/<int:group_id>/', director_views.director_cancelled_detail, name='director_cancelled_detail'),
    path('director/cancelled-groups/<int:group_id>/archive/', director_views.director_archive_cancelled, name='director_archive_cancelled'),
    path('director/statistics/auc/filters/', director_views.director_statistics_filters, name='director_statistics_filters'),
    path('director/statistics/auc/', director_views.director_auc_statistics, name='director_auc_statistics'),
    # === ДИРЕКТОР ===
    path('director/groups/', director_views.director_groups, name='director_groups'),
    path('director/groups/<int:group_id>/approve/', director_views.director_approve_schedule, name='director_approve_schedule'),
]