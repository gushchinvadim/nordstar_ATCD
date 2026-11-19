"""Serialize training writes with group cancellation, preserving cancelled history."""
from functools import wraps
from django.db import transaction
from django.http import JsonResponse
from rest_framework.response import Response
from .models import Group, ScheduleItem, Enrollment, Assessment, Certificate


def group_write_guard(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return view(request, *args, **kwargs)
        with transaction.atomic():
            data = getattr(request, 'data', request.POST)
            group_ids = set()
            direct = kwargs.get('group_id') or data.get('group_id')
            if direct:
                group_ids.add(direct)
            targets = [
                (ScheduleItem, kwargs.get('item_id') or kwargs.get('pk') or data.get('schedule_item_id'), 'group_id'),
                (Enrollment, kwargs.get('enrollment_id') or data.get('enrollment_id'), 'group_id'),
                (Assessment, data.get('assessment_id'), 'enrollment__group_id'),
                (Certificate, data.get('certificate_id'), 'enrollment__group_id'),
            ]
            for model, pk, path in targets:
                if pk:
                    group_id = model.objects.filter(pk=pk).values_list(path, flat=True).first()
                    if group_id:
                        group_ids.add(group_id)
            # Do not let an unrelated active group_id bypass a cancelled target.
            if data.get('grades') and isinstance(data['grades'], list):
                enrollment_ids = [row.get('enrollment_id') for row in data['grades'] if isinstance(row, dict) and row.get('enrollment_id')]
                group_ids.update(Enrollment.objects.filter(pk__in=enrollment_ids).values_list('group_id', flat=True))
            for group in Group.objects.select_for_update().filter(pk__in=group_ids).order_by('pk'):
                if group.was_cancelled:
                    response_class = Response if hasattr(request, 'data') else JsonResponse
                    return response_class({'error': 'Группа отменена. История доступна для просмотра; новые изменения и ПЭП не принимаются.'}, status=409)
            return view(request, *args, **kwargs)
    return guarded
