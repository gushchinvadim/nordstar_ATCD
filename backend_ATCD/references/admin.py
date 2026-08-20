# references/admin.py
from django.contrib import admin
from .models import (
    AircraftType, Citizenship, Location, Position, StudentProfession,
    Organization, Classroom, License
)


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ['organ', 'license_number', 'issue_date', 'end_date']
    list_filter = ['organ']
    search_fields = ['organ', 'license_number']

@admin.register(AircraftType)
class AircraftTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(Citizenship)
class CitizenshipAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'name', 'addr', 'dept']
    search_fields = ['full_name', 'name', 'addr', 'dept']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(StudentProfession)
class StudentProfessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'location', 'address', 'is_active']
    list_filter = ['is_active', 'location']
    search_fields = ['company_name']


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ['title', 'location', 'organization', 'get_full_address', 'audience', 'contact_name']
    list_filter = ['location', 'organization']
    search_fields = ['title', 'address']
    change_list_template = 'admin/references/classroom/change_list.html'

    def get_full_address(self, obj):
        """Выводит адрес аудитории, а если его нет — адрес организации"""
        return obj.full_address

    get_full_address.short_description = 'Фактический адрес'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        if obj and obj.organization and obj.organization.address:
            help_text = f"💡 Если оставить пустым, будет использован адрес организации: «{obj.organization.address}»"
        else:
            help_text = " Если оставить пустым, при генерации документов будет подставлен адрес организации"

        form.base_fields['address'].help_text = help_text
        return form