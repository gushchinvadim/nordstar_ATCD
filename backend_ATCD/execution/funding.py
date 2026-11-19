"""Financing belongs to an individual enrollment, independent of teaching and payment settlement."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from references.models import Organization
from .models import Group, Enrollment, Assessment, Certificate, ComplianceLog, IndividualStudyPlan
from .methodist_views import IsMethodist, audit
from django.db.models import Q

FUNDING_FIELDS = ('funding_source', 'payer_organization', 'funding_reference')
CORPORATE_SOURCES = ('company_internal', 'company_external')


class FundingData(serializers.Serializer):
    funding_source = serializers.ChoiceField(choices=Enrollment.FUNDING_CHOICES, required=False)
    payer_organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), required=False, allow_null=True)
    funding_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def to_internal_value(self, data):
        if set(data) - set(self.fields):
            raise serializers.ValidationError({'non_field_errors': ['Можно изменять только источник финансирования, плательщика и договор.']})
        return super().to_internal_value(data)


class FundingRow(FundingData):
    id = serializers.IntegerField(min_value=1)


def funding_values(data, instance=None):
    values = {key: getattr(instance, key) if instance else default for key, default in (
        ('funding_source', 'unspecified'), ('payer_organization', None), ('funding_reference', ''))}
    values.update({key: data[key] for key in FUNDING_FIELDS if key in data})
    serializer = FundingData(data={key: value.pk if key == 'payer_organization' and isinstance(value, Organization) else value
        for key, value in values.items()})
    serializer.is_valid(raise_exception=True)
    values = dict(serializer.validated_data)
    source = values['funding_source']; payer = values['payer_organization']
    if source in CORPORATE_SOURCES:
        if not payer: raise serializers.ValidationError({'payer_organization': 'Укажите компанию-плательщика.'})
        if not payer.is_active and (instance is None or instance.payer_organization_id != payer.pk):
            raise serializers.ValidationError({'payer_organization': 'Нельзя выбрать неактивную компанию для нового назначения.'})
    elif payer is not None:
        raise serializers.ValidationError({'payer_organization': 'Компания указывается только при финансировании юрлицом.'})
    return values


def financing_snapshot(row):
    return {'funding_source': row.funding_source, 'payer_organization': row.payer_organization_id,
        'payer_name': row.payer_name_snapshot, 'funding_reference': row.funding_reference}


def apply_funding(user, row, values, reason=''):
    changed = row.funding_source != values['funding_source'] or row.payer_organization_id != (
        values['payer_organization'].pk if values['payer_organization'] else None) or row.funding_reference != values['funding_reference']
    if not changed: return False
    from types import SimpleNamespace
    from rest_framework.exceptions import PermissionDenied
    if not IsMethodist().has_permission(SimpleNamespace(user=user), None):
        raise PermissionDenied('Финансирование заполняет методист.')
    if (row.status == 'completed' or row.group.status in ('completed', 'archived', 'cancelled')) and not reason.strip():
        raise serializers.ValidationError({'reason': 'Для изменения финансирования завершённого обучения или закрытой группы укажите причину.'})
    before = financing_snapshot(row)
    for key, value in values.items(): setattr(row, key, value)
    row.save(update_fields=FUNDING_FIELDS)
    audit(user, row, {'operation': 'enrollment_funding_changed', 'reason': reason.strip(),
        'before': before, 'after': financing_snapshot(row), 'group_id': row.group_id})
    return True


def funding_references():
    return {'funding_choices': [{'code': code, 'title': title} for code, title in Enrollment.FUNDING_CHOICES],
        'organizations': list(Organization.objects.order_by('company_name', 'pk').values('id', 'company_name', 'is_active'))}


@api_view(['GET'])
@permission_classes([IsMethodist])
def methodist_funding_references(request):
    return Response(funding_references())


@api_view(['GET', 'POST'])
@permission_classes([IsMethodist])
@transaction.atomic
def group_funding(request, group_id):
    # Historical funding corrections are allowed without reopening archived/cancelled teaching records.
    group = get_object_or_404(Group.objects.select_for_update(), pk=group_id)
    if request.method == 'POST':
        class Updates(serializers.Serializer):
            enrollments = FundingRow(many=True, allow_empty=False, max_length=1000)
            reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)
        data = Updates(data=request.data); data.is_valid(raise_exception=True)
        updates = data.validated_data['enrollments']
        ids = [row['id'] for row in updates]
        if len(set(ids)) != len(ids): raise serializers.ValidationError({'enrollments': 'Назначение повторяется в запросе.'})
        records = {row.pk: row for row in Enrollment.objects.select_for_update().filter(group=group, pk__in=ids)}
        if len(records) != len(ids): raise serializers.ValidationError({'enrollments': 'Назначение не найдено в этой группе.'})
        pending = [(records[row['id']], funding_values(row, records[row['id']])) for row in updates]
        count = sum(apply_funding(request.user, row, values, data.validated_data.get('reason', '')) for row, values in pending)
        return Response({'message': f'Финансирование сохранено. Изменено назначений: {count}.', 'updated': count})
    records = Enrollment.objects.filter(group=group).select_related('student', 'payer_organization').order_by('number_in_group')
    return Response({'id': group.pk, 'assigned_number': group.assigned_number, 'status': group.status,
        'status_display': group.get_status_display(), 'module': group.module.title, **funding_references(),
        'enrollments': [{'id': row.pk, 'student_name': str(row.student).strip(), 'status': row.status,
            'status_display': row.get_status_display(), 'number_in_group': row.number_in_group, **financing_snapshot(row)} for row in records]})


def enrollment_has_history(row):
    return (Assessment.objects.filter(enrollment=row).exists() or Certificate.objects.filter(enrollment=row).exists()
        or ComplianceLog.objects.filter(Q(enrollment=row) | Q(assessment__enrollment=row) | Q(certificate__enrollment=row)).exists()
        or IndividualStudyPlan.objects.filter(student_id=row.student_id, group_id=row.group_id).exists()
        or row.status in ('completed', 'failed', 'dismissed', 'partial') or row.completed_at or row.dismissal_date
        or row.total_hours_completed or row.order_out_number or row.order_out_date)


def sync_group_enrollments(group, payload, user, funding_reason=''):
    """Keep stable enrollment IDs and their evidence; never delete/recreate an unchanged assignment."""
    from people.models import Student
    if not isinstance(payload, list) or len(payload) > 1000 or any(not isinstance(item, dict) for item in payload):
        raise serializers.ValidationError('Некорректный список назначений.')
    existing = list(Enrollment.objects.select_for_update().filter(group=group))
    by_id = {row.pk: row for row in existing}
    used = set(); plan = []; numbers = set()
    for item in payload:
        if not item.get('student_id'): continue
        try:
            student_id = int(item['student_id']); number = int(item.get('number_in_group', 1))
        except (TypeError, ValueError): raise serializers.ValidationError('Некорректное назначение слушателя.')
        if number < 1 or number in numbers: raise serializers.ValidationError('Номера слушателей в группе должны быть положительными и уникальными.')
        numbers.add(number)
        if not Student.objects.filter(pk=student_id).exists(): raise serializers.ValidationError('Слушатель не найден.')
        row = None
        if item.get('id'):
            try: row = by_id.get(int(item['id']))
            except (ValueError, TypeError): pass
            if not row: raise serializers.ValidationError('Назначение не принадлежит группе.')
        else:
            matches = [row for row in existing if row.student_id == student_id and row.pk not in used]
            if len(matches) > 1: raise serializers.ValidationError('Укажите идентификатор существующего назначения.')
            if matches: row = matches[0]
        if row:
            if row.pk in used: raise serializers.ValidationError('Назначение повторяется.')
            if row.student_id != student_id: raise serializers.ValidationError('Нельзя заменить слушателя в существующем назначении. Добавьте отдельное назначение.')
            used.add(row.pk)
        state = item.get('status', row.status if row else 'enrolled')
        if state not in dict(Enrollment.STATUS_CHOICES): raise serializers.ValidationError('Недопустимый статус назначения.')
        if row and enrollment_has_history(row) and row.status != state:
            raise serializers.ValidationError('Статус назначения с историей изменяется через журнал обучения.')
        plan.append((row, student_id, number, state, funding_values(item, row)))
    removed = [row for row in existing if row.pk not in used]
    if any(enrollment_has_history(row) for row in removed):
        raise serializers.ValidationError('Нельзя удалить назначение с историей обучения или финансирования. Используйте предусмотренные действия в журнале.')
    from types import SimpleNamespace
    from rest_framework.exceptions import PermissionDenied
    for row in removed:
        if (row.funding_source != 'unspecified' or row.payer_organization_id or row.funding_reference) and not IsMethodist().has_permission(SimpleNamespace(user=user), None):
            raise PermissionDenied('Финансирование заполняет методист.')
    for row in removed:
        audit(user, row, {'operation': 'unused_enrollment_removed', 'before': financing_snapshot(row), 'group_id': group.pk, 'student_id': row.student_id})
        row.delete()
    # Free unique positions before reordering, without changing IDs or related records.
    offset = max([row.number_in_group for row in existing] + list(numbers) + [0]) + 1
    for index, row in enumerate(existing):
        if row.pk in used: Enrollment.objects.filter(pk=row.pk).update(number_in_group=offset + index)
    for row, student_id, number, state, finance in plan:
        if row:
            row.number_in_group = number; row.status = state
            row.save(update_fields=['number_in_group', 'status'])
            apply_funding(user, row, finance, funding_reason)
        else:
            from types import SimpleNamespace
            from rest_framework.exceptions import PermissionDenied
            if (finance['funding_source'] != 'unspecified' or finance['funding_reference']) and not IsMethodist().has_permission(SimpleNamespace(user=user), None):
                raise PermissionDenied('Финансирование заполняет методист.')
            Enrollment.objects.create(group=group, student_id=student_id, number_in_group=number, status=state, **finance)
