# from django.contrib import admin
# from .models import (
#     AircraftType, Citizenship, Location, Position, StudentProfession,
#     Organization, Staff, StaffPosition, Student, Classroom,
#     Course, Module, Stage, Section, Subsection
# )
#
#
# # ==========================================
# # БАЗОВЫЕ СПРАВОЧНИКИ
# # ==========================================
#
# @admin.register(AircraftType)
# class AircraftTypeAdmin(admin.ModelAdmin):
#     list_display = ['name', 'code']
#     search_fields = ['name', 'code']
#
#
# @admin.register(Citizenship)
# class CitizenshipAdmin(admin.ModelAdmin):
#     list_display = ['name', 'code']
#     search_fields = ['name', 'code']
#
#
# @admin.register(Location)
# class LocationAdmin(admin.ModelAdmin):
#     list_display = ['name', 'addr', 'dept']
#     search_fields = ['name', 'addr', 'dept']
#
#
# @admin.register(Position)
# class PositionAdmin(admin.ModelAdmin):
#     list_display = ['name', 'code']
#     search_fields = ['name', 'code']
#
#
# @admin.register(StudentProfession)
# class StudentProfessionAdmin(admin.ModelAdmin):
#     list_display = ['name', 'code']
#     search_fields = ['name', 'code']
#
#
# # ==========================================
# # ОРГАНИЗАЦИИ И ПЕРСОНАЛ
# # ==========================================
#
#
# class StaffPositionInline(admin.TabularInline):
#     model = StaffPosition
#     extra = 1
#     verbose_name = "История должности"
#     verbose_name_plural = "История должностей"
#
#
#
#
#
# # # ==========================================
# # # УЧЕБНЫЙ ПЛАН (Иерархия)
# # # ==========================================
# #
# # class ModuleInline(admin.TabularInline):
# #     model = Module
# #     extra = 0
# #     verbose_name = "Модуль"
# #     verbose_name_plural = "Модули"
# #     fields = ['title', 'duration', 'mod_id', 'aircraft_type']
# #
# #
# # @admin.register(Course)
# # class CourseAdmin(admin.ModelAdmin):
# #     list_display = ['title', 'company_code', 'approved', 'approved_date']
# #     list_filter = ['approved']
# #     search_fields = ['title', 'prog_id', 'company_code']
# #     inlines = [ModuleInline]
# #     change_list_template = 'admin/core/course/change_list.html'
# #
# # class StageInline(admin.TabularInline):
# #     model = Stage
# #     extra = 0
# #     verbose_name = "Этап"
# #     verbose_name_plural = "Этапы"
# #     fields = ['title', 'order', 'description']
# #
# #
# # @admin.register(Module)
# # class ModuleAdmin(admin.ModelAdmin):
# #     list_display = ['title', 'course', 'aircraft_type', 'duration']
# #     list_filter = ['course', 'aircraft_type']
# #     search_fields = ['title', 'code', 'mod_id']
# #     inlines = [StageInline]
# #
# #
# # class SectionInline(admin.TabularInline):
# #     model = Section
# #     extra = 0
# #     verbose_name = "Дисциплина"
# #     verbose_name_plural = "Дисциплины"
# #     fields = ['title', 'duration_hours', 'order']
# #
# #
# # @admin.register(Stage)
# # class StageAdmin(admin.ModelAdmin):
# #     list_display = ['title', 'module', 'order']
# #     list_filter = ['module']
# #     search_fields = ['title', 'description']
# #     inlines = [SectionInline]
# #
# #
# # class SubsectionInline(admin.TabularInline):
# #     model = Subsection
# #     extra = 0
# #     verbose_name = "Тема"
# #     verbose_name_plural = "Темы"
# #     fields = ['title', 'duration_hours', 'order']
# #
# #
# # @admin.register(Section)
# # class SectionAdmin(admin.ModelAdmin):
# #     list_display = ['title', 'stage', 'duration_hours', 'order']
# #     list_filter = ['stage']
# #     search_fields = ['title', 'detail']
# #     inlines = [SubsectionInline]
# #
# #
# # @admin.register(Subsection)
# # class SubsectionAdmin(admin.ModelAdmin):
# #     list_display = ['title', 'section', 'duration_hours', 'order']
# #     list_filter = ['section']
# #     search_fields = ['title', 'detail']