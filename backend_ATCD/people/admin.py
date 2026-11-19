# people/admin.py
from django.contrib import admin
from .models import (Staff, Student, StaffPosition, )

admin.site.site_header = "Aviation Training Center Documentation (ATCD)"  # Верхний заголовок (слева в шапке)
admin.site.site_title = "ATCD NordStar"                        # Заголовок вкладки браузера
admin.site.index_title = "Добро пожаловать в панель управления Training center NordStar" # Приветствие на главной странице админки


from training.models import InstructorQualification


class QualificationInline(admin.TabularInline):
    model = InstructorQualification
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('subject', 'device_type', 'certificate_number', 'effective_from', 'valid_until', 'is_verified', 'is_active')
    readonly_fields = fields
    def has_add_permission(self, request, obj=None): return False


class StaffPositionInline(admin.TabularInline):
    model = StaffPosition
    extra = 1
    verbose_name = "История должности"
    verbose_name_plural = "История должностей"

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'organization', 'position', 'is_instructor', 'is_active']
    list_filter = ['is_active', 'is_instructor', 'organization', 'position']
    search_fields = ['full_name', 'rauts_id', 'email']
    inlines = [StaffPositionInline, QualificationInline]
    change_list_template = 'admin/core/staff/change_list.html'



@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['surname', 'name', 'patronymic', 'profession', 'citizenship', 'aircraft_type', 'is_active']
    list_filter = ['is_active', 'profession', 'citizenship', 'aircraft_type', 'sex']
    search_fields = ['surname', 'name', 'email', 'employee_id', 'snils']
    change_list_template = 'admin/core/student/change_list.html'

