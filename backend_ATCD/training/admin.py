# training/admin.py
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Course, Module, Stage, Section, Subsection, Subject, InstructorQualification
)

# ==========================================
# УЧЕБНЫЙ ПЛАН (Иерархия)
# ==========================================

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    verbose_name = "Модуль"
    verbose_name_plural = "Модули"
    fields = ['title', 'duration', 'mod_id', 'aircraft_type']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'company_code', 'approved', 'approved_date']
    list_filter = ['approved']
    search_fields = ['title', 'prog_id', 'company_code']
    inlines = [ModuleInline]
    change_list_template = 'admin/core/course/change_list.html'

class StageInline(admin.TabularInline):
    model = Stage
    extra = 0
    verbose_name = "Этап"
    verbose_name_plural = "Этапы"
    fields = ['title', 'order', 'description']


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'aircraft_type', 'duration']
    list_filter = ['code', 'aircraft_type']
    search_fields = ['title', 'code', 'mod_id']
    inlines = [StageInline]


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    verbose_name = "Дисциплина"
    verbose_name_plural = "Дисциплины"
    fields = ['title', 'duration_hours', 'order']


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ['title', 'module', 'order']
    list_filter = ['module']
    search_fields = ['title', 'description']
    inlines = [SectionInline]


class SubsectionInline(admin.TabularInline):
    model = Subsection
    extra = 0
    verbose_name = "Тема"
    verbose_name_plural = "Темы"
    fields = ['title', 'duration_hours', 'order']


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'stage', 'duration_hours', 'order']
    list_filter = [
        'stage__module__code',  # ← Фильтр по коду модуля (например, ППП.АУЦ.11 - М.1)
        'stage',
    ]
    search_fields = ['title', 'detail']
    inlines = [SubsectionInline]


@admin.register(Subsection)
class SubsectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'section', 'duration_hours', 'order']
    list_filter = [
        'section__stage__module__code',  # ← Фильтр по коду модуля
        'section',
    ]
    search_fields = ['title', 'detail']



@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('name',)


@admin.register(InstructorQualification)
class InstructorQualificationAdmin(admin.ModelAdmin):
    # ВАЖНО: указываем путь к нашему шаблону change_list
    change_list_template = 'admin/training/instructorqualification/change_list.html'

    list_display = (
        'staff',
        'subject',
        'device_type',
        'certificate_number',
        'issue_date',
        'validity_months',
        'expiration_date_display',
        'months_left_display',
        'status_badge',
        'is_active'
    )
    list_filter = ('is_active', 'subject', 'device_type')
    search_fields = ('staff__full_name', 'subject__name', 'certificate_number')
    ordering = ('staff__full_name', 'subject__name')

    @admin.display(description="Действителен до")
    def expiration_date_display(self, obj):
        return obj.expiration_date.strftime('%d.%m.%Y')

    @admin.display(description="Осталось")
    def months_left_display(self, obj):
        months = obj.months_left
        if months < 0:
            return f"Просрочено на {-months} мес."
        return f"{months} мес."

    @admin.display(description="Статус")
    def status_badge(self, obj):
        colors = {
            'valid': 'green',
            'warning': 'orange',
            'critical': 'red',
            'inactive': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        labels = {
            'valid': '✅ Действует',
            'warning': '⚠️ Истекает скоро',
            'critical': '🔴 Требует внимания',
            'inactive': '⏸️ Неактивен'
        }
        label = labels.get(obj.status, '—')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            label
        )