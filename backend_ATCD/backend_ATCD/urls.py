
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.admin_views import import_program_view, import_staff_view, import_students_view, import_group_enroll_view, import_organizations_view

urlpatterns = [
    path('admin/import/program/', import_program_view, name='import_program'),
    path('admin/import/staff/', import_staff_view, name='import_staff'),
    path('admin/import/students/', import_students_view, name='import_students'),
    path('admin/import/group_enroll/', import_group_enroll_view, name='import_group_enroll'),
    path('admin/import/organizations/', import_organizations_view, name='import_organizations'),
    path('docs/', include('docs.urls')),
    path('admin/', admin.site.urls),
    path('reporting/', include('reporting.urls')),
]

# Раздача медиа-файлов в режиме разработки (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)