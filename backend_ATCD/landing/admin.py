# landing/admin.py
from django.contrib import admin
from .models import NewsItem, CourseHighlight, StatBlock, AboutSection, Partner


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'published_at', 'is_active']
    list_filter = ['is_active', 'published_at']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(CourseHighlight)
class CourseHighlightAdmin(admin.ModelAdmin):
    list_display = ['module', 'order', 'is_featured']
    list_filter = ['is_featured']


@admin.register(StatBlock)
class StatBlockAdmin(admin.ModelAdmin):
    list_display = ['title', 'value', 'order']
    list_editable = ['value', 'order']


@admin.register(AboutSection)
class AboutSectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'order']
    list_editable = ['order']


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'order']
    list_editable = ['order']