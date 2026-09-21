# execution/director_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.db.models import Exists, OuterRef
from .models import ScheduleItem, ComplianceLog, Group, Enrollment
from people.models import Staff
from .serializers import DirectorScheduleSerializer




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def director_groups(request):
    try:
        director = request.user.staff
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    # Подзапрос для проверки наличия утверждения
    approval_exists = ComplianceLog.objects.filter(
        group=OuterRef('pk'),
        staff=director,
        action_type='director_schedule_approved'
    )

    # Получаем только неутвержденные группы
    groups = Group.objects.filter(
        director=director
    ).exclude(
        Exists(approval_exists)
    ).prefetch_related(
        'schedule__section',
        'schedule__subsection',
        'schedule__classroom',
        'schedule__instructor'
    ).order_by('-assigned_at')

    groups_data = []
    for group in groups:
        schedule_items = group.schedule.all().order_by('date', 'start_time')
        serializer = DirectorScheduleSerializer(schedule_items, many=True,
                                                context={'request': request, 'director': director})

        groups_data.append({
            'id': group.id,
            'assigned_number': group.assigned_number,
            'module_title': group.module.title if group.module else None,
            'module_code': group.module.code if group.module else None,
            'start_date': group.start_date,
            'end_date': group.end_date,
            'status': group.get_status_display(),
            'schedule': serializer.data,
        })

    return Response(groups_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def director_approve_schedule(request, group_id):
    """
    POST /api/director/groups/<group_id>/approve/
    Директор утверждает расписание группы
    """
    try:
        director = request.user.staff
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    try:
        group = Group.objects.get(pk=group_id, director=director)
    except Group.DoesNotExist:
        return Response({'error': 'Группа не найдена или вы не являетесь её директором'},
                        status=status.HTTP_404_NOT_FOUND)

    # Проверяем, не утверждено ли уже
    if ComplianceLog.objects.filter(
            group=group,
            staff=director,
            action_type='director_schedule_approved'
    ).exists():
        return Response({'error': 'Расписание уже утверждено'}, status=status.HTTP_400_BAD_REQUEST)

    # Определяем IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')

    # Создаем запись в логе
    log = ComplianceLog.objects.create(
        group=group,
        staff=director,
        action_type='director_schedule_approved',
        ip_address=ip,
        notes=request.data.get('notes', '')
    )

    return Response({
        'message': 'Расписание успешно утверждено',
        'signature': log.signature_string,
        'timestamp': log.timestamp.isoformat()
    }, status=status.HTTP_200_OK)