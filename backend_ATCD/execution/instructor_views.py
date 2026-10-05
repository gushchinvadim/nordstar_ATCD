# execution/instructor_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse

from execution.models import ScheduleItem, Group
from docs.utils import get_logo_base64


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_schedule_view(request, group_id):
    """Просмотр расписания группы для инструктора (с JWT аутентификацией)"""
    try:
        staff = request.user.staff
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    # Получаем группу
    group = get_object_or_404(Group, id=group_id)

    # Проверяем, что инструктор ведёт занятия в этой группе
    has_access = ScheduleItem.objects.filter(group=group, instructor=staff).exists()
    if not has_access:
        return Response({'error': 'У вас нет доступа к расписанию этой группы'}, status=status.HTTP_403_FORBIDDEN)

    schedule_items = ScheduleItem.objects.filter(group=group).select_related(
        'section', 'subsection', 'classroom', 'instructor'
    ).order_by('date', 'start_time')

    context = {
        'group': group,
        'schedule_items': schedule_items,
        'logo_base64': get_logo_base64(),
        'is_instructor_view': True,
    }

    html_content = render_to_string('docs/schedules/schedule.html', context, request=request)
    return HttpResponse(html_content)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_instructing_view(request):
    """Просмотр инструктажа для инструктора (с JWT аутентификацией)"""
    try:
        staff = request.user.staff
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    context = {
        'is_instructor_view': True,
    }

    html_content = render_to_string('docs/instructing/instructing.html', context, request=request)
    return HttpResponse(html_content)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_journal_view(request, group_id):
    """Просмотр журнала оценок группы для инструктора (с JWT аутентификацией)"""
    try:
        staff = request.user.staff
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    group = get_object_or_404(Group, id=group_id)

    # Проверяем доступ
    has_access = ScheduleItem.objects.filter(group=group, instructor=staff).exists()
    if not has_access:
        return Response({'error': 'У вас нет доступа к журналу этой группы'}, status=status.HTTP_403_FORBIDDEN)

    from docs.views import get_journal_context

    context = get_journal_context(group)
    context['is_instructor_view'] = True
    context['logo_base64'] = get_logo_base64()

    template_name = 'docs/journal/journal_landscape.html' if context.get(
        'use_landscape') else 'docs/journal/journal.html'

    html_content = render_to_string(template_name, context, request=request)
    return HttpResponse(html_content)