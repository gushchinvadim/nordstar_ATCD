# people/admin.py
from django.contrib import admin
from .models import (Staff, Student, StaffPosition, )

admin.site.site_header = "Aviation Training Center Documentation (ATCD)"  # Верхний заголовок (слева в шапке)
admin.site.site_title = "ATCD NordStar"                        # Заголовок вкладки браузера
admin.site.index_title = "Добро пожаловать в панель управления Training center NordStar" # Приветствие на главной странице админки


class StaffPositionInline(admin.TabularInline):
    model = StaffPosition
    extra = 1
    verbose_name = "История должности"
    verbose_name_plural = "История должностей"

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'organization', 'position', 'is_active']
    list_filter = ['is_active', 'organization', 'position']
    search_fields = ['full_name', 'rauts_id', 'email']
    inlines = [StaffPositionInline]
    change_list_template = 'admin/core/staff/change_list.html'



@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['surname', 'name', 'patronymic', 'profession', 'citizenship', 'aircraft_type', 'is_active']
    list_filter = ['is_active', 'profession', 'citizenship', 'aircraft_type', 'sex']
    search_fields = ['surname', 'name', 'email', 'employee_id', 'snils']
    change_list_template = 'admin/core/student/change_list.html'

