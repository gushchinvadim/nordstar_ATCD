# training/admin.py
from django.contrib import admin, messages
from django import forms
from django.utils import timezone
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError, PermissionDenied
from .qualification_services import register_qualification, confirm_qualification, audit_qualification, STATUS_LABELS
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
    list_display = ['title', 'company_code', 'frdo_template_type', 'approved', 'approved_date']
    list_filter = ['frdo_template_type', 'approved']
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
    list_display = ['title', 'stage', 'subject', 'teaching_device_type', 'duration_hours', 'order']
    list_filter = [
        'stage__module__code',  # ← Фильтр по коду модуля (например, ППП.АУЦ.11 - М.1)
        'stage',
    ]
    autocomplete_fields = ['subject']
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


class QualificationForm(forms.ModelForm):
    class Meta:
        model = InstructorQualification
        fields = '__all__'

    def clean(self):
        data = super().clean()
        if self.instance.is_verified:
            return data
        number, until = data.get('certificate_number'), data.get('valid_until')
        if bool(number) != bool(until):
            raise forms.ValidationError('Укажите номер документа и дату окончания вместе либо оставьте оба поля пустыми до получения сведений.')
        if until and data.get('effective_from') and until < data['effective_from']:
            raise forms.ValidationError('Дата окончания не может быть раньше даты начала действия.')
        if until and data.get('issue_date') and until < data['issue_date']:
            raise forms.ValidationError('Дата выдачи не может быть позже даты окончания.')
        return data


class RenewalForm(forms.Form):
    certificate_number = forms.CharField(label='Номер документа', max_length=100)
    effective_from = forms.DateField(label='Действует с', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    valid_until = forms.DateField(label='Действителен до (включительно)', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    issue_date = forms.DateField(label='Дата выдачи (если известна)', required=False, widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    reason = forms.CharField(label='Причина продления или замены', widget=forms.Textarea)


class RevocationForm(forms.Form):
    reason = forms.CharField(label='Причина аннулирования с сегодняшнего дня', widget=forms.Textarea, max_length=2000)


@admin.register(InstructorQualification)
class InstructorQualificationAdmin(admin.ModelAdmin):
    change_list_template = 'admin/training/instructorqualification/change_list.html'
    form = QualificationForm
    list_display = ('staff', 'subject', 'device_type', 'certificate_number', 'valid_until',
        'days_left_display', 'status_badge', 'renew_link')
    list_filter = ('is_active', 'is_verified', 'subject', 'device_type', ('valid_until', admin.DateFieldListFilter))
    search_fields = ('staff__full_name', 'subject__name', 'certificate_number')
    autocomplete_fields = ('staff', 'subject')
    list_select_related = ('staff', 'subject', 'superseded_by')
    ordering = ('staff__full_name', 'subject__name', '-effective_from')
    fields = ('staff', 'subject', 'device_type', 'certificate_number', 'issue_date', 'effective_from',
        'valid_until', 'legacy_expiration_date_display', 'status_badge', 'days_left_display', 'waiver_notes',
        'is_verified', 'confirmed_at', 'confirmed_by', 'revoked_on', 'revocation_reason', 'renew_link', 'revoke_link')
    readonly_fields = ('is_verified', 'confirmed_at', 'confirmed_by', 'revoked_on', 'revocation_reason',
        'legacy_expiration_date_display', 'status_badge', 'days_left_display', 'renew_link', 'revoke_link')

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj:
            fields += ['staff', 'subject', 'device_type']
            if obj.is_verified or not obj.is_active:
                fields += ['certificate_number', 'issue_date', 'effective_from', 'valid_until']
        return fields

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            row = register_qualification(request.user, obj.staff_id, {
                'subject': obj.subject, 'device_type': obj.device_type, 'certificate_number': obj.certificate_number,
                'issue_date': obj.issue_date, 'effective_from': obj.effective_from,
                'valid_until': obj.valid_until, 'waiver_notes': obj.waiver_notes})
            obj.__dict__.update(row.__dict__)
        elif not obj.is_verified and obj.is_active and obj.valid_until and obj.certificate_number:
            row = confirm_qualification(request.user, obj.pk, {
                'certificate_number': obj.certificate_number, 'valid_until': obj.valid_until,
                'effective_from': obj.effective_from, 'issue_date': obj.issue_date, 'waiver_notes': obj.waiver_notes})
            obj.__dict__.update(row.__dict__)
        else:
            super().save_model(request, obj, form, change)
            audit_qualification(request.user, obj, 'qualification_note_changed')

    @admin.display(description='Прежняя расчётная дата (не подтверждена)')
    def legacy_expiration_date_display(self, obj):
        value = obj.legacy_expiration_date if obj and not obj.is_verified else None
        return value.strftime('%d.%m.%Y') if value else '—'

    @admin.display(description='Осталось дней')
    def days_left_display(self, obj):
        if not obj or obj.days_left is None or not obj.is_verified: return 'Не подтверждён'
        days = obj.days_left
        return f'Просрочен на {-days} дн.' if days < 0 else ('Истекает сегодня' if days == 0 else f'{days} дн.')

    @admin.display(description='Статус')
    def status_badge(self, obj):
        if not obj or not obj.pk: return 'Новый допуск'
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', obj.status_color, STATUS_LABELS[obj.status])

    @admin.display(description='Продление / замена')
    def renew_link(self, obj):
        if not obj or not obj.pk or not obj.is_active: return '—'
        return format_html('<a href="{}">Продлить / заменить документ</a>', reverse('admin:qualification_renew', args=[obj.pk]))

    @admin.display(description='Аннулирование')
    def revoke_link(self, obj):
        if not obj or not obj.pk or not obj.is_active: return '—'
        return format_html('<a href="{}">Аннулировать с причиной</a>', reverse('admin:qualification_revoke', args=[obj.pk]))

    def get_urls(self):
        return [path('<int:pk>/renew/', self.admin_site.admin_view(self.renew_view), name='qualification_renew'),
            path('<int:pk>/revoke/', self.admin_site.admin_view(self.revoke_view), name='qualification_revoke')] + super().get_urls()

    def renew_view(self, request, pk):
        return self.document_action(request, pk, 'renew')

    def revoke_view(self, request, pk):
        return self.document_action(request, pk, 'revoke')

    def document_action(self, request, pk, action):
        obj = get_object_or_404(InstructorQualification, pk=pk)
        if not self.has_change_permission(request, obj): raise PermissionDenied()
        Form = RenewalForm if action == 'renew' else RevocationForm
        form = Form(request.POST if request.method == 'POST' else None,
            initial={'effective_from': max(timezone.localdate(), obj.effective_from)})
        if request.method == 'POST' and form.is_valid():
            try:
                if action == 'renew':
                    data = dict(form.cleaned_data)
                    data.update(subject=obj.subject, device_type=obj.device_type)
                    row = register_qualification(request.user, obj.staff_id, data, reason=data['reason'])
                else:
                    from .qualification_services import revoke_qualification
                    row = revoke_qualification(request.user, obj.pk, form.cleaned_data['reason'])
                self.message_user(request, 'Сведения сохранены, история допусков сохранена.', messages.SUCCESS)
                return redirect('admin:training_instructorqualification_change', row.pk)
            except ValidationError as error:
                form.add_error(None, error)
        admin_form = admin.helpers.AdminForm(form, [(None, {'fields': list(form.fields)})], {})
        context = {**self.admin_site.each_context(request), 'title': ('Продление / замена допуска' if action == 'renew' else 'Аннулирование допуска'),
            'subtitle': str(obj), 'opts': self.model._meta, 'original': obj, 'adminform': admin_form,
            'media': self.media + admin_form.media, 'errors': admin.helpers.AdminErrorList(form, []),
            'inline_admin_formsets': [], 'has_editable_inline_admin_formsets': False, 'add': True, 'change': False, 'is_popup': False,
            'has_add_permission': True, 'has_change_permission': True, 'has_view_permission': True,
            'has_delete_permission': False, 'save_as': False, 'show_save': True,
            'show_save_and_continue': False, 'show_save_and_add_another': False}
        return TemplateResponse(request, 'admin/change_form.html', context)
