# training/admin.py
from django.contrib import admin
from .models import (
    Course, Module, Stage, Section, Subsection
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