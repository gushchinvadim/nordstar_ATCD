"""Methodist instructor cards. Identity, qualification evidence and account access are separate."""
import secrets
import string
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q, Count, Min
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from people.models import Staff
from references.models import Organization, Position
from training.models import InstructorQualification, Subject
from training.qualification_services import (STATUS_LABELS, register_qualification, confirm_qualification,
    audit_qualification, assignment_error)
from .models import ScheduleItem
from .methodist_views import IsMethodist, audit
from .local_time import group_today


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown: raise serializers.ValidationError({'non_field_errors': ['Недоступные поля: ' + ', '.join(sorted(unknown))]})
        return super().to_internal_value(data)


class InstructorData(StrictSerializer):
    full_name = serializers.CharField(max_length=200, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    rauts_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all(), required=False, allow_null=True)
    position = serializers.PrimaryKeyRelatedField(queryset=Position.objects.all(), required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    existing_staff_id = serializers.IntegerField(required=False, min_value=1)


def account_allowed(staff):
    user = staff.user
    return not staff.fptitle and not staff.tptitle and not (user and (user.is_staff or user.is_superuser))


def staff_card(staff):
    return {'id': staff.pk, 'full_name': staff.full_name, 'email': staff.email, 'phone': staff.phone,
        'rauts_id': staff.rauts_id, 'is_active': staff.is_active, 'organization': staff.organization_id,
        'organization_name': str(staff.organization) if staff.organization_id else '',
        'position': staff.position_id, 'position_name': str(staff.position) if staff.position_id else '',
        'username': staff.user.username if staff.user_id else None, 'can_manage_account': staff.is_active and account_allowed(staff),
        'qualification_count': getattr(staff, 'qualification_count', None),
        'unconfirmed_count': getattr(staff, 'unconfirmed_count', None),
        'nearest_expiry': getattr(staff, 'nearest_expiry', None)}


def qualification_card(row, today):
    state = row.status_on(today)
    return {'id': row.pk, 'subject': row.subject_id, 'subject_name': row.subject.name,
        'device_type': row.device_type, 'device_display': row.get_device_type_display(),
        'certificate_number': row.certificate_number or '', 'issue_date': row.issue_date,
        'effective_from': row.effective_from, 'valid_until': row.valid_until,
        'legacy_expiration_date': row.legacy_expiration_date if not row.is_verified else None,
        'days_left': row.days_left_on(today), 'status': state, 'status_display': STATUS_LABELS[state],
        'is_active': row.is_active, 'is_verified': row.is_verified, 'waiver_notes': row.waiver_notes or '',
        'revoked_on': row.revoked_on, 'revocation_reason': row.revocation_reason,
        'superseded_by': row.superseded_by_id}


def upcoming_issues(staff):
    rows = ScheduleItem.objects.filter(instructor=staff).exclude(group__status__in=['cancelled', 'archived', 'completed']).filter(
        date__gte=timezone.localdate() - timedelta(days=1)).select_related('group__location', 'section__subject').order_by('date', 'pk')
    issues = []
    for row in rows:
        if row.date < group_today(row.group) or row.is_completed or row.status in ('completed', 'cancelled'): continue
        error = assignment_error(staff, row.section, row.date, row.deadline if row.session_type == 'sdo' else None)
        if error:
            issues.append({'id': row.pk, 'group': row.group.assigned_number, 'group_id': row.group_id,
                'date': row.date, 'section': row.section.title, 'reason': error})
    return issues


def instructor_queryset():
    return Staff.objects.filter(is_instructor=True).select_related('user', 'organization', 'position')


@api_view(['GET', 'POST'])
@permission_classes([IsMethodist])
def instructors(request):
    if request.method == 'GET':
        rows = instructor_queryset()
        search = request.query_params.get('search', '').strip()
        for term in search.split()[:6]:
            rows = rows.filter(Q(full_name__icontains=term) | Q(email__icontains=term) | Q(rauts_id__icontains=term))
        active = request.query_params.get('active', 'all')
        if active in ('true', 'false'): rows = rows.filter(is_active=active == 'true')
        subject = request.query_params.get('subject')
        qualifications = InstructorQualification.objects.filter(is_active=True)
        if subject:
            if not subject.isdigit(): return Response({'error': 'Некорректный предмет.'}, status=400)
            qualifications = qualifications.filter(subject_id=int(subject))
        state = request.query_params.get('state', 'all')
        today = timezone.localdate()
        if state == 'unconfirmed': qualifications = qualifications.filter(is_verified=False)
        elif state == 'expired': qualifications = qualifications.filter(is_verified=True, valid_until__lt=today)
        elif state in ('30', '90'): qualifications = qualifications.filter(is_verified=True, valid_until__range=(today, today + timedelta(days=int(state))))
        elif state != 'all': return Response({'error': 'Неизвестный фильтр допуска.'}, status=400)
        if state != 'all' or subject: rows = rows.filter(pk__in=qualifications.values('staff_id'))
        rows = rows.annotate(qualification_count=Count('qualifications', filter=Q(qualifications__is_active=True)),
            unconfirmed_count=Count('qualifications', filter=Q(qualifications__is_active=True, qualifications__is_verified=False)),
            nearest_expiry=Min('qualifications__valid_until', filter=Q(qualifications__is_active=True, qualifications__is_verified=True))).order_by('full_name', 'pk')
        paginator = PageNumberPagination(); paginator.page_size = 15
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response([staff_card(row) for row in page])
    serializer = InstructorData(data=request.data); serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    existing = data.pop('existing_staff_id', None)
    with transaction.atomic():
        if existing:
            if data: return Response({'error': 'Для подключения существующего сотрудника передайте только его идентификатор.'}, status=400)
            staff = get_object_or_404(Staff.objects.select_for_update(), pk=existing)
            staff.is_instructor = True; staff.save(update_fields=['is_instructor'])
        else:
            if not data.get('full_name'): return Response({'error': 'Укажите ФИО преподавателя.'}, status=400)
            if Staff.objects.filter(full_name__iexact=data['full_name']).exists():
                return Response({'error': 'Сотрудник с таким ФИО уже есть. Подключите существующего сотрудника.'}, status=409)
            staff = Staff.objects.create(is_instructor=True, **data)
        audit(request.user, staff, {'operation': 'instructor_registered'})
    return Response(staff_card(staff), status=201)


@api_view(['GET', 'PATCH'])
@permission_classes([IsMethodist])
def instructor_detail(request, pk):
    staff = get_object_or_404(instructor_queryset(), pk=pk)
    if request.method == 'PATCH':
        serializer = InstructorData(data=request.data); serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'existing_staff_id' in data: return Response({'error': 'Связь с сотрудником не изменяется.'}, status=400)
        with transaction.atomic():
            staff = Staff.objects.select_for_update().get(pk=pk)
            if 'is_active' in data and data['is_active'] != staff.is_active and not account_allowed(staff):
                return Response({'error': 'Активность сотрудника с руководящими или административными полномочиями изменяет администратор.'}, status=400)
            before = {key: str(getattr(staff, key)) for key in data}
            # Freeze legacy signatures before changing the instructor's name.
            from .models import ComplianceLog
            ComplianceLog.objects.filter(staff=staff, actor_name_snapshot='').update(actor_name_snapshot=staff.full_name)
            for key, value in data.items(): setattr(staff, key, value)
            staff.save(update_fields=list(data))
            audit(request.user, staff, {'operation': 'instructor_changed', 'before': before,
                'after': {key: str(getattr(staff, key)) for key in data}})
    result = staff_card(staff)
    result['today'] = timezone.localdate()
    result['qualifications'] = [qualification_card(row, result['today']) for row in staff.qualifications.select_related('subject', 'superseded_by').order_by('-is_active', 'subject__name', '-effective_from', '-pk')]
    result['upcoming_issues'] = upcoming_issues(staff)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsMethodist])
def instructor_references(request):
    from training.models import Module
    return Response({'subjects': list(Subject.objects.filter(is_active=True).values('id', 'name', 'code')),
        'modules': list(Module.objects.order_by('code').values('id', 'code', 'title')),
        'devices': [{'code': code, 'name': label} for code, label in InstructorQualification.DEVICE_CHOICES],
        'organizations': [{'id': row.pk, 'name': str(row)} for row in Organization.objects.all()],
        'positions': list(Position.objects.values('id', 'name')),
        'existing_staff': list(Staff.objects.filter(is_instructor=False).order_by('full_name').values('id', 'full_name'))})


class QualificationData(StrictSerializer):
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all(), required=False)
    device_type = serializers.ChoiceField(choices=InstructorQualification.DEVICE_CHOICES, default='CLASS')
    certificate_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    valid_until = serializers.DateField(required=False, allow_null=True)
    effective_from = serializers.DateField(required=False)
    issue_date = serializers.DateField(required=False, allow_null=True)
    waiver_notes = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)


@api_view(['POST'])
@permission_classes([IsMethodist])
def add_instructor_qualification(request, pk):
    get_object_or_404(instructor_queryset(), pk=pk)
    serializer = QualificationData(data=request.data); serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    if 'subject' not in data: return Response({'error': 'Укажите предмет.'}, status=400)
    try: row = register_qualification(request.user, pk, data, reason=data.pop('reason', ''))
    except DjangoValidationError as error: return Response({'error': ' '.join(error.messages)}, status=400)
    return Response(qualification_card(row, timezone.localdate()), status=201)


@api_view(['POST'])
@permission_classes([IsMethodist])
def confirm_instructor_qualification(request, pk):
    row = get_object_or_404(InstructorQualification, pk=pk, staff__is_instructor=True)
    serializer = QualificationData(data=request.data); serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if ('subject' in data and data['subject'].pk != row.subject_id) or ('device_type' in request.data and data['device_type'] != row.device_type):
        return Response({'error': 'Предмет и формат существующего допуска не изменяются.'}, status=400)
    try: row = confirm_qualification(request.user, pk, data)
    except DjangoValidationError as error: return Response({'error': ' '.join(error.messages)}, status=400)
    return Response(qualification_card(row, timezone.localdate()))


@api_view(['POST'])
@permission_classes([IsMethodist])
@transaction.atomic
def revoke_instructor_qualification(request, pk):
    original = get_object_or_404(InstructorQualification, pk=pk, staff__is_instructor=True)
    Staff.objects.select_for_update().get(pk=original.staff_id)
    row = InstructorQualification.objects.select_for_update().get(pk=pk)
    reason = request.data.get('reason', '')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        return Response({'error': 'Укажите причину аннулирования (до 2000 символов).'}, status=400)
    if row.revoked_on or not row.is_active: return Response({'error': 'Допуск уже аннулирован или заменён.'}, status=409)
    # Revocation is an action from today; historical signatures and lessons are not changed.
    row.revoked_on = timezone.localdate(); row.revocation_reason = reason.strip(); row.is_active = False
    row.save(update_fields=['revoked_on', 'revocation_reason', 'is_active'])
    audit_qualification(request.user, row, 'qualification_revoked', reason)
    return Response({'message': 'Допуск аннулирован. История и существующие назначения сохранены.'})


@api_view(['POST'])
@permission_classes([IsMethodist])
@transaction.atomic
def instructor_account(request, pk):
    staff = get_object_or_404(Staff.objects.select_for_update(), pk=pk, is_instructor=True)
    if request.data.get('confirm') is not True: return Response({'error': 'Подтвердите действие с учётной записью.'}, status=400)
    if not staff.is_active or not account_allowed(staff):
        return Response({'error': 'Учётную запись сотрудника с административными полномочиями изменяет администратор.'}, status=400)
    User = get_user_model()
    if staff.user_id:
        user = User.objects.select_for_update().get(pk=staff.user_id)
        staff.user = user
        if not account_allowed(staff):
            return Response({'error': 'Сотрудник получил административные полномочия. Обратитесь к администратору.'}, status=400)
        if not user.is_active: return Response({'error': 'Учётная запись отключена администратором.'}, status=400)
    else:
        username = request.data.get('username', '')
        if not isinstance(username, str) or not username.strip(): return Response({'error': 'Укажите логин.'}, status=400)
        username = username.strip()
        try: User._meta.get_field('username').clean(username, None)
        except DjangoValidationError: return Response({'error': 'Некорректный логин.'}, status=400)
        if User.objects.filter(username__iexact=username).exists(): return Response({'error': 'Логин уже занят.'}, status=400)
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=username, email=staff.email)
        except IntegrityError:
            return Response({'error': 'Логин уже занят. Выберите другой.'}, status=400)
        staff.user = user; staff.save(update_fields=['user'])
    password = ''.join(secrets.choice(string.ascii_letters + string.digits + '-_!') for _ in range(18))
    user.set_password(password); user.last_login = None; user.save(update_fields=['password', 'last_login'])
    audit(request.user, staff, {'operation': 'instructor_account_reset', 'user_id': user.pk})
    response = Response({'username': user.username, 'temporary_password': password})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@permission_classes([IsMethodist])
@transaction.atomic
def add_instructor_subject(request):
    class SubjectData(StrictSerializer):
        name = serializers.CharField(max_length=200)
        code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    data = SubjectData(data=request.data); data.is_valid(raise_exception=True)
    values = data.validated_data
    if Subject.objects.filter(name__iexact=values['name']).exists() or (values['code'] and Subject.objects.filter(code__iexact=values['code']).exists()):
        return Response({'error': 'Предмет с таким названием или кодом уже есть. Выберите существующий.'}, status=409)
    row = Subject.objects.create(**values)
    audit(request.user, row, {'operation': 'instructor_subject_created'})
    return Response({'id': row.pk, 'name': row.name, 'code': row.code}, status=201)


@api_view(['GET'])
@permission_classes([IsMethodist])
def instructor_section_mappings(request):
    from training.models import Section
    rows = Section.objects.select_related('stage__module', 'subject').order_by('stage__module__code', 'stage__order', 'order', 'pk')
    module = request.query_params.get('module')
    if module:
        if not module.isdigit(): return Response({'error': 'Некорректный модуль.'}, status=400)
        rows = rows.filter(stage__module_id=int(module))
    search = request.query_params.get('search', '').strip()
    if search: rows = rows.filter(title__icontains=search)
    paginator = PageNumberPagination(); paginator.page_size = 15
    page = paginator.paginate_queryset(rows, request)
    return paginator.get_paginated_response([{'id': row.pk, 'title': row.title,
        'module': row.stage.module.code, 'module_title': row.stage.module.title,
        'subject': row.subject_id, 'teaching_device_type': row.teaching_device_type} for row in page])


@api_view(['PATCH'])
@permission_classes([IsMethodist])
@transaction.atomic
def update_instructor_section_mapping(request, pk):
    from training.models import Section
    class MappingData(StrictSerializer):
        subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.filter(is_active=True))
        teaching_device_type = serializers.ChoiceField(choices=InstructorQualification.DEVICE_CHOICES)
    data = MappingData(data=request.data); data.is_valid(raise_exception=True)
    row = get_object_or_404(Section.objects.select_for_update(), pk=pk)
    before = {'subject': row.subject_id, 'teaching_device_type': row.teaching_device_type}
    row.subject = data.validated_data['subject']; row.teaching_device_type = data.validated_data['teaching_device_type']
    row.save(update_fields=['subject', 'teaching_device_type'])
    audit(request.user, row, {'operation': 'instructor_section_mapping_changed', 'before': before,
        'after': {'subject': row.subject_id, 'teaching_device_type': row.teaching_device_type}})
    count = ScheduleItem.objects.filter(section=row, instructor__isnull=False, date__gte=timezone.localdate(),
        is_completed=False).exclude(status='cancelled').exclude(group__status__in=['cancelled', 'archived', 'completed']).count()
    return Response({'message': 'Связь сохранена. Содержание программы и существующие назначения сохранены.',
        'upcoming_assignments_to_review': count})
