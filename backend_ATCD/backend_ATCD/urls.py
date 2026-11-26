# backend_ATCD/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.admin_views import import_program_view, import_staff_view, import_students_view, import_group_enroll_view, \
    import_organizations_view
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from execution.sim_export import sim_schedule

urlpatterns = [
    path("api/integrations/sim-training/schedule/", sim_schedule),
    path('', include('landing.urls')),

    path('admin/import/program/', import_program_view, name='import_program'),
    path('admin/import/staff/', import_staff_view, name='import_staff'),
    path('admin/import/students/', import_students_view, name='import_students'),
    path('admin/import/group_enroll/', import_group_enroll_view, name='import_group_enroll'),
    path('admin/import/organizations/', import_organizations_view, name='import_organizations'),
    # Keep qualification tools behind the existing /admin/ Django proxy.
    path('admin/training-tools/', include('training.urls')),
    path('admin/', admin.site.urls),

    # Compatibility for existing local links; generated links use /admin/.
    path('training/', include('training.urls', namespace='training_legacy')),
    path('reporting/', include('reporting.urls')),

    # HTML-маршруты документов (если они нужны по старым ссылкам)
    path('docs/', include('docs.urls')),

    # === API МАРШРУТИЗАЦИЯ (ЧЕТКОЕ РАЗДЕЛЕНИЕ) ===
    path('api/docs/', include('docs.api_urls')),  # <-- Справочники, группы, помощь
    path('api/execution/', include('execution.urls')),  # <-- Логика выполнения
    path('api/', include('references.urls')),

    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[
        0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)