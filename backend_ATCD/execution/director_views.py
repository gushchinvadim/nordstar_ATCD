from execution.group_lifecycle import group_write_guard
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
    ).exclude(status__in=['cancelled', 'archived']).exclude(
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

        approval = ComplianceLog.objects.filter(group=group, action_type='director_schedule_approved').order_by('-timestamp').first()
        groups_data.append({
            'id': group.id,
            'assigned_number': group.assigned_number,
            'module_title': group.module.title if group.module else None,
            'module_code': group.module.code if group.module else None,
            'start_date': group.start_date,
            'end_date': group.end_date,
            'status': group.get_status_display(),
            'schedule': serializer.data,
            'has_director_approval': approval is not None,
            'director_approval_date': approval.timestamp if approval else None,
            'director_approval_signature': approval.signature_string if approval else None,
        })

    return Response(groups_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
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

# Cancellation management follows the same group assignment as schedule approval.
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from .methodist_views import audit
from .group_archive import archive_training_group, ArchiveError
from .group_history import group_history, training_delete_blockers


class IsDirector(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        staff = getattr(user, 'staff', None)
        return bool(user.is_authenticated and user.is_active and (user.is_superuser or (
            staff and staff.is_active and staff.tptitle)))


def cancelled_queryset(user):
    rows = Group.objects.filter(Q(status='cancelled') | Q(status='archived', archived_from_status='cancelled') |
        (Q(status='archived') & (Q(cancellation_date__isnull=False) | ~Q(cancellation_reason=''))))
    if not user.is_superuser:
        rows = rows.filter(director__user=user)
    return rows


def cancellation_card(group):
    from .local_time import local_datetime
    actor = group.cancelled_by
    staff = getattr(actor, 'staff', None) if actor else None
    return {'id': group.pk, 'assigned_number': group.assigned_number,
        'module_title': group.module.title, 'status': group.status, 'status_display': group.get_status_display(),
        'start_date': group.start_date, 'end_date': group.end_date, 'cancellation_date': group.cancellation_date,
        'cancellation_reason': group.cancellation_reason,
        'cancelled_at': local_datetime(group.cancelled_at, group).isoformat() if group.cancelled_at else None,
        'cancelled_by': staff.full_name if staff else (actor.get_full_name() or actor.username if actor else None),
        'students_count': getattr(group, 'students_count', None)}


class CancelledFilters(serializers.Serializer):
    status = serializers.ChoiceField(choices=['cancelled', 'archived', 'all'], default='cancelled')
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, allow_blank=True, max_length=150)
    page = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        if attrs.get('date_from') and attrs.get('date_to') and attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError('Начало периода не может быть позже конца.')
        return attrs


@api_view(['GET'])
@permission_classes([IsDirector])
def director_cancelled_groups(request):
    filters = CancelledFilters(data=request.query_params)
    filters.is_valid(raise_exception=True)
    data = filters.validated_data
    rows = cancelled_queryset(request.user)
    if data['status'] != 'all':
        rows = rows.filter(status=data['status'])
    if data.get('date_from'):
        rows = rows.filter(cancellation_date__gte=data['date_from'])
    if data.get('date_to'):
        rows = rows.filter(cancellation_date__lte=data['date_to'])
    if data.get('search'):
        rows = rows.filter(Q(assigned_number__icontains=data['search']) | Q(module__title__icontains=data['search']))
    rows = rows.select_related('module', 'location', 'cancelled_by__staff').annotate(
        students_count=Count('enrollment')).order_by('-cancellation_date', '-pk')
    pages = Paginator(rows, 15)
    page = pages.get_page(data['page'])
    return Response({'count': pages.count, 'page': page.number, 'total_pages': pages.num_pages,
        'results': [cancellation_card(group) for group in page]})


@api_view(['GET'])
@permission_classes([IsDirector])
def director_cancelled_detail(request, group_id):
    group = get_object_or_404(cancelled_queryset(request.user).select_related(
        'module', 'location', 'cancelled_by__staff'), pk=group_id)
    data = cancellation_card(group)
    data['history'] = group_history(group)
    data['deletion_blockers'] = training_delete_blockers(group)
    return Response(data)


@api_view(['POST'])
@permission_classes([IsDirector])
@transaction.atomic
def director_archive_cancelled(request, group_id):
    group = get_object_or_404(cancelled_queryset(request.user).select_for_update(), pk=group_id)
    if request.data.get('confirm_delete_files') is not True:
        return Response({'error': 'Подтвердите архивирование с удалением сформированных файлов.'}, status=400)
    if group.status == 'archived':
        return Response({'message': 'Заявка уже в архиве.'})
    try:
        archive_training_group(group, request.user, audit)
    except ArchiveError as error:
        return Response({'error': str(error)}, status=400)
    return Response({'message': 'Отменённая заявка архивирована. История и причина отмены сохранены; сформированные файлы удалены.'})


class AUCStatisticsPeriod(serializers.Serializer):
    from references.models import Organization
    funding_source = serializers.ChoiceField(choices=[('all', 'Все источники')] + Enrollment.FUNDING_CHOICES, required=False, default='all')
    payer_organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), required=False, allow_null=True)
    date_from = serializers.DateField(required=True)
    date_to = serializers.DateField(required=True)

    def validate(self, attrs):
        if attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError('Дата начала периода не может быть позже даты окончания.')
        return attrs


@api_view(['GET'])
@permission_classes([IsDirector])
def director_auc_statistics(request):
    # AUC-wide aggregate figures, regardless of who approved each group's schedule.
    period = AUCStatisticsPeriod(data=request.query_params)
    period.is_valid(raise_exception=True)
    from .auc_statistics import build_auc_statistics
    response = Response(build_auc_statistics(**period.validated_data))
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET'])
@permission_classes([IsDirector])
def director_statistics_filters(request):
    from .funding import funding_references
    return Response(funding_references())
