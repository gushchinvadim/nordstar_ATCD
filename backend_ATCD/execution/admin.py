# execution/admin.py
import os
from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404, redirect
from core.services.schedule_generator import generate_schedule_for_group
from .models import Enrollment, Assessment, Certificate, ScheduleItem, Group
from django.conf import settings


class AssessmentInline(admin.TabularInline):
    model = Assessment
    extra = 0  # ← изменено
    verbose_name = "Оценка"
    verbose_name_plural = "Оценки по разделам"
    fields = [
        'section', 'assessment_type', 'score', 'passed',
        'attempt_number', 'assessment_date', 'instructor', 'notes'
    ]
    readonly_fields = ['passed']


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'enrollment', 'section', 'assessment_type',
        'score', 'passed', 'attempt_number', 'assessment_date', 'instructor'
    ]
    list_filter = ['passed', 'assessment_type', 'section__stage__module__code']
    search_fields = [
        'enrollment__student__surname',
        'enrollment__student__name',
        'section__title'
    ]
    raw_id_fields = ['enrollment', 'section', 'instructor']


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = [
        'number', 'student_full_name', 'module_code',
        'certificate_type', 'license',  # ← ДОБАВИТЬ
        'issue_date', 'total_hours'
    ]
    list_filter = ['certificate_type', 'license', 'issue_date']  # ← ДОБАВИТЬ license
    search_fields = ['number', 'student_full_name', 'module_code']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('number', 'certificate_type', 'issue_date', 'license', 'enrollment')
        }),
        ('Данные слушателя', {
            'fields': ('student_full_name', 'student_profession', 'qualification')
        }),
        ('Данные программы', {
            'fields': ('module_code', 'module_title', 'aircraft_type', 'total_hours')
        }),
        ('Файл', {
            'fields': ('pdf_file',)
        }),
        ('Системные поля', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    # Убрали order_in_number и order_in_date — они теперь в Group
    fields = ['student', 'number_in_group', 'status', 'order_out_number', 'order_out_date']
    autocomplete_fields = ['student']


class ScheduleItemInline(admin.TabularInline):
    model = ScheduleItem
    extra = 0
    fields = ['date', 'deadline', 'start_time', 'end_time', 'section', 'classroom', 'instructor', 'status', 'notes']
    autocomplete_fields = ['section', 'classroom', 'instructor']


@admin.action(description='📅 Сгенерировать расписание (с учетом лимита 8ч/день)')
def generate_schedule_action(modeladmin, request, queryset):
    success_count = 0
    for group in queryset:
        try:
            count = generate_schedule_for_group(group)
            success_count += 1
            messages.success(request, f"✅ {group.assigned_number}: создано {count} занятий")
        except Exception as e:
            messages.error(request, f" {group.assigned_number}: {str(e)}")

# ==========================Очистка media папок групп====================

@admin.action(description='🗑 Очистить медиа-файлы выбранных групп')
def cleanup_selected_groups_media(modeladmin, request, queryset):
    """Action для удаления файлов выбранных групп"""
    total_deleted = 0
    total_size = 0

    for group in queryset:
        year = str(group.start_date.year) if group.start_date else 'unknown'
        module_code = group.module.code.replace('/', '_').replace('.', '_') if group.module else 'unknown'
        group_folder = os.path.join(
            settings.MEDIA_ROOT,
            'documents', year, 'groups', module_code, group.assigned_number
        )

        if not os.path.exists(group_folder):
            continue

        for root, dirs, files in os.walk(group_folder):
            # Сохраняем папку reports
            if 'reports' in root:
                continue

            for file in files:
                filepath = os.path.join(root, file)
                total_size += os.path.getsize(filepath)
                os.remove(filepath)
                total_deleted += 1

        # Удаляем пустые папки
        for root, dirs, files in os.walk(group_folder, topdown=False):
            if not files and not dirs:
                os.rmdir(root)

    size_mb = total_size / (1024 * 1024)
    messages.success(
        request,
        f'✅ Удалено {total_deleted} файлов ({size_mb:.2f} MB) из {queryset.count()} групп'
    )

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = [
        'assigned_number', 'application', 'order_in_number', 'order_in_date',
        'module', 'location', 'start_date','mentor', 'curator', 'director', 'status',
        'schedule_button',           # ← должны быть методы класса
        'enrollment_order_button',
        'journal_button',
        'land_task_button',
        'water_task_button',
        'dismissal_ok_button',
        'dismissal_ot_button',
        'grades_button',
        'documents_dashboard_button',

    ]
    list_filter = ['status', 'location', 'is_sdo']
    search_fields = ['assigned_number', 'application']
    inlines = [EnrollmentInline, ScheduleItemInline]
    actions = [
        generate_schedule_action,
        cleanup_selected_groups_media,
        'generate_rauc_action',
        'generate_frdo_action',
    ]

    fieldsets = (
        ('Основная информация', {'fields': ('assigned_number', 'application', 'order_in_number','order_in_date', 'module', 'status')}),
        ('Место и время', {'fields': ('location', 'start_date', 'start_face_to_face', 'end_date', 'is_sdo', 'start_time_default')}),
        ('Преподавательский состав', {'fields': ('mentor','curator', 'director')}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.order_in_number and obj.assigned_number:
            obj.order_in_number = obj.get_generated_order_in_number()
        super().save_model(request, obj, form, change)

    # ↓↓↓ ВСЕ ЭТИ МЕТОДЫ ДОЛЖНЫ БЫТЬ ВНУТРИ КЛАССА (с отступом 4 пробела) ↓↓↓

    def documents_dashboard_button(self, obj):
        url = reverse('docs:documents_dashboard', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" style="background-color: #8e44ad; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">📁 Документы</a>',
            url
        )
    documents_dashboard_button.short_description = 'Управление'

    def schedule_button(self, obj):
        url = reverse('docs:schedule', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;"> Расписание</a>',
            url
        )
    schedule_button.short_description = 'Документы'

    def enrollment_order_button(self, obj):
        url = reverse('docs:enrollment_order', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: #2196F3; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; margin-left: 5px;">📄 Приказ</a>',
            url
        )
    enrollment_order_button.short_description = ' '

    def journal_button(self, obj):
        url = reverse('docs:journal', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: #FF5722; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; margin-left: 5px;"> Журнал</a>',
            url
        )
    journal_button.short_description = ' '

    def land_task_button(self, obj):
        from execution.models import ScheduleItem
        has_asp_land = ScheduleItem.objects.filter(group=obj, session_type='asp-l').exists()
        if not has_asp_land:
            return '-'
        url = reverse('docs:land_training_task', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: #FF5722; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;"> АСП Суша</a>',
            url
        )
    land_task_button.short_description = 'Задания АСП'

    def water_task_button(self, obj):
        from execution.models import ScheduleItem
        has_asp_water = ScheduleItem.objects.filter(group=obj, session_type='asp-w').exists()
        if not has_asp_water:
            return '-'
        url = reverse('docs:water_training_task', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: #03A9F4; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">💧 АСП Вода</a>',
            url
        )
    water_task_button.short_description = ' '

    def grades_button(self, obj):
        url = reverse('docs:group_grades', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" style="background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">📊 Журнал оценок</a>',
            url
        )
    grades_button.short_description = 'Оценки'

    def dismissal_ok_button(self, obj):
        count = obj.enrollment_set.filter(status='completed').count()
        color = '#4CAF50' if count > 0 else '#ccc'
        url = reverse('docs:dismissal_ok', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: {}; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">✅ ОК ({})</a>',
            url, color, count
        )
    dismissal_ok_button.short_description = 'Приказ ОК'

    def dismissal_ot_button(self, obj):
        count = obj.enrollment_set.filter(status='dismissed').count()
        color = '#f44336' if count > 0 else '#ccc'
        url = reverse('docs:dismissal_ot_list', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: {}; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">❌ ОТ ({})</a>',
            url, color, count
        )
    dismissal_ot_button.short_description = 'Приказ ОТ'



    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('media-stats/', self.admin_site.admin_view(self.media_stats_view), name='media_stats'),
        ]
        return custom_urls + urls

    def media_stats_view(self, request):
        """Страница статистики медиа-файлов"""
        media_root = settings.MEDIA_ROOT
        total_size = 0
        total_files = 0
        folder_stats = []

        # Сканируем папку documents
        docs_folder = os.path.join(media_root, 'documents')
        if os.path.exists(docs_folder):
            for year in os.listdir(docs_folder):
                year_path = os.path.join(docs_folder, year)
                if not os.path.isdir(year_path):
                    continue

                year_size = 0
                year_files = 0

                for module_code in os.listdir(year_path):
                    module_path = os.path.join(year_path, module_code)
                    if not os.path.isdir(module_path):
                        continue

                    for group_num in os.listdir(module_path):
                        group_path = os.path.join(module_path, group_num)
                        if not os.path.isdir(group_path):
                            continue

                        group_size = 0
                        group_files = 0

                        for root, dirs, files in os.walk(group_path):
                            for file in files:
                                filepath = os.path.join(root, file)
                                file_size = os.path.getsize(filepath)
                                group_size += file_size
                                group_files += 1

                        year_size += group_size
                        year_files += group_files

                        if group_files > 0:
                            folder_stats.append({
                                'year': year,
                                'module': module_code,
                                'group': group_num,
                                'files': group_files,
                                'size_mb': group_size / (1024 * 1024)
                            })

                total_size += year_size
                total_files += year_files

        context = {
            'total_size_mb': total_size / (1024 * 1024),
            'total_files': total_files,
            'folder_stats': sorted(folder_stats, key=lambda x: x['size_mb'], reverse=True)[:50],
            'title': 'Статистика медиа-файлов',
        }

        return render(request, 'admin/media_stats.html', context)

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'group', 'number_in_group', 'status', 'order_out_number', 'order_out_date']
    list_filter = ['status', 'group']
    search_fields = ['student__surname', 'student__name', 'group__assigned_number']
    autocomplete_fields = ['student', 'group']
    inlines = [AssessmentInline]

    # ← ДОБАВИТЬ ЭТУ СТРОКУ
    readonly_fields = ['order_in_number_display', 'order_in_date_display']

    fieldsets = (
        ('Основная информация', {
            'fields': ('group', 'student', 'number_in_group')
        }),
        ('Приказы о зачислении (из группы)', {
            'fields': ('order_in_number_display', 'order_in_date_display'),
            'classes': ('collapse',),
            'description': 'Эти поля заполняются на уровне группы и отображаются только для справки'
        }),
        ('Приказы об отчислении/завершении', {
            'fields': (
                'order_out_number', 'order_out_date',
            ),
        }),
        ('Статус обучения', {
            'fields': (
                'status', 'completed_at', 'final_result',
                'total_hours_completed'
            ),
        }),
        ('Отчисление', {
            'fields': ('dismissal_reason', 'dismissal_date'),
            'classes': ('collapse',),
        }),
    )

    def order_in_number_display(self, obj):
        """Отображает номер приказа о зачислении из группы"""
        return obj.group.order_in_number if obj.group else '-'

    order_in_number_display.short_description = 'Номер приказа о зачислении'

    def order_in_date_display(self, obj):
        """Отображает дату приказа о зачислении из группы"""
        return obj.group.order_in_date if obj.group and obj.group.order_in_date else '-'

    order_in_date_display.short_description = 'Дата приказа о зачислении'

    actions = ['complete_selected_enrollments', 'dismiss_selected_enrollments']

    @admin.action(description='✅ Завершить обучение для выбранных')
    def complete_selected_enrollments(self, request, queryset):
        from datetime import date
        count = 0
        for enrollment in queryset:
            if enrollment.status in ['enrolled', 'in_progress']:
                if enrollment.check_all_sections_passed():
                    enrollment.status = 'completed'
                    enrollment.completed_at = date.today()
                    enrollment.final_result = 'passed'
                    enrollment.order_out_number = enrollment.generate_order_out_number('completed')
                    enrollment.order_out_date = date.today()
                    enrollment.save()
                    count += 1
        messages.success(request, f'Завершено обучение: {count} чел.')

    @admin.action(description=' Отчислить выбранных')
    def dismiss_selected_enrollments(self, request, queryset):
        from datetime import date
        count = 0
        for enrollment in queryset:
            if enrollment.status in ['enrolled', 'in_progress']:
                enrollment.status = 'dismissed'
                enrollment.dismissal_date = date.today()
                enrollment.dismissal_reason = 'Отчислен по решению методиста'
                enrollment.order_out_number = enrollment.generate_order_out_number('dismissed')
                enrollment.order_out_date = date.today()
                enrollment.save()
                count += 1
        messages.success(request, f'Отчислено: {count} чел.')

@admin.register(ScheduleItem)
class ScheduleItemAdmin(admin.ModelAdmin):
    list_display = ['date', 'start_time', 'end_time', 'group', 'section', 'instructor', 'status']
    list_filter = ['group', 'status', 'date']
    search_fields = ['group__assigned_number', 'section__title']
    date_hierarchy = 'date'