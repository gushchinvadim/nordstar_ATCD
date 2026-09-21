# landing/api_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncMonth

from .models import NewsItem, CourseHighlight, StatBlock, AboutSection, Partner
from execution.models import Enrollment, Group
from training.models import Module


@api_view(['GET'])
@permission_classes([AllowAny])
def landing_content(request):
    """
    GET /api/landing/content/
    Возвращает весь контент для лендинга
    """
    # 1. Новости (только активные, последние 6)
    news = NewsItem.objects.filter(is_active=True)[:6]
    news_data = [{
        'id': item.id,
        'title': item.title,
        'slug': item.slug,
        'content': item.content,
        'image': item.image.url if item.image else None,
        'published_at': item.published_at.isoformat()
    } for item in news]

    # 2. Рекомендуемые курсы
    courses = CourseHighlight.objects.select_related('module').filter(is_featured=True)[:6]
    courses_data = [{
        'id': item.id,
        'module_id': item.module.id,
        'title': item.module.title,
        'code': item.module.code,
        'description': item.description,
        'duration': item.module.duration_hours if hasattr(item.module, 'duration_hours') else None
    } for item in courses]

    # 3. Блоки статистики (из админки)
    stat_blocks = StatBlock.objects.all()
    stats_data = [{
        'id': item.id,
        'title': item.title,
        'value': item.value,
        'description': item.description,
        'icon': item.icon
    } for item in stat_blocks]

    # 4. Динамическая статистика из БД
    total_graduates = Enrollment.objects.filter(status='completed').count()
    active_groups = Group.objects.filter(status='in_progress').count()
    total_courses = Module.objects.count()

    # Популярные курсы (топ-5 по количеству зачислений)
    # Идем через Group к Enrollment
    popular_courses = Module.objects.annotate(
        enrollment_count=Count('group__enrollment')  # Правильный путь через Group
    ).order_by('-enrollment_count')[:5]

    popular_courses_data = [{
        'title': module.title,
        'code': module.code,
        'enrollments': module.enrollment_count
    } for module in popular_courses]

    # Статистика по месяцам (последние 12 месяцев)
    twelve_months_ago = timezone.now() - timedelta(days=365)

    # Используем TruncMonth для группировки по месяцам
    monthly_enrollments = Enrollment.objects.filter(
        completed_at__gte=twelve_months_ago
    ).annotate(
        month=TruncMonth('completed_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    monthly_data = [{
        'month': item['month'].strftime('%Y-%m'),
        'count': item['count']
    } for item in monthly_enrollments]

    # 5. Секции "О компании"
    about_sections = AboutSection.objects.all()
    about_data = [{
        'id': item.id,
        'title': item.title,
        'content': item.content,
        'image': item.image.url if item.image else None
    } for item in about_sections]

    # 6. Партнеры
    partners = Partner.objects.all()
    partners_data = [{
        'id': item.id,
        'name': item.name,
        'logo': item.logo.url if item.logo else None,
        'website': item.website
    } for item in partners]

    return Response({
        'news': news_data,
        'courses': courses_data,
        'stats': stats_data,
        'dynamic_stats': {
            'total_graduates': total_graduates,
            'active_groups': active_groups,
            'total_courses': total_courses,
            'popular_courses': popular_courses_data,
            'monthly_enrollments': monthly_data
        },
        'about': about_data,
        'partners': partners_data
    })