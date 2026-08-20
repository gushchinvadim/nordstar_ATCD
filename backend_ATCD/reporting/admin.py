# reporting/admin.py
from django.contrib import admin
from .models import RegulatoryReport, RegulatoryReportItem


@admin.register(RegulatoryReport)
class RegulatoryReportAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'report_type', 'status', 'created_at', 'created_by'
    ]
    list_filter = ['report_type', 'status']
    search_fields = ['title']
    readonly_fields = ['created_at', 'updated_at']

    filter_horizontal = ['groups']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by')


@admin.register(RegulatoryReportItem)
class RegulatoryReportItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'report', 'is_valid', 'validation_error']
    list_filter = ['is_valid', 'report__report_type']
    search_fields = ['student__surname', 'student__name']
    readonly_fields = ['payload']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'report')