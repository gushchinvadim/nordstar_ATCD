"""Document-based instructor permissions, without inferred expiry dates."""
from datetime import date
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from django.core.exceptions import ValidationError
from people.models import Staff
from .models import InstructorQualification

STATUS_LABELS = {'valid': 'Действует', 'warning': 'Истекает в течение 90 дней',
    'critical': 'Истекает в течение 30 дней', 'expires_today': 'Истекает сегодня',
    'expired': 'Просрочен', 'unconfirmed': 'Допуск не подтверждён', 'inactive': 'Неактивен',
    'revoked': 'Аннулирован', 'superseded': 'Заменён новым документом', 'continuing': 'Действует до вступления нового документа', 'scheduled': 'Начнёт действовать'}


def valid_qualifications(staff, section, on_date):
    if not staff or not staff.is_active or not section or not section.subject_id or not section.teaching_device_type or not on_date:
        return InstructorQualification.objects.none()
    return InstructorQualification.objects.filter(staff=staff, subject_id=section.subject_id,
        device_type=section.teaching_device_type, is_verified=True, effective_from__lte=on_date,
        valid_until__gte=on_date, subject__is_active=True).exclude(certificate_number__isnull=True).exclude(certificate_number='').filter(
            Q(revoked_on__isnull=True) | Q(revoked_on__gt=on_date)).filter(
            Q(is_active=True) | Q(superseded_by__effective_from__gt=on_date) | Q(revoked_on__gt=on_date))


def assignment_error(staff, section, on_date, deadline=None):
    if not staff or not staff.is_active:
        return 'Преподаватель неактивен.'
    if not section or not section.subject_id or not section.teaching_device_type:
        return 'У раздела не указаны предмет и формат преподавания для проверки допуска. Заполните их в справочнике разделов.'
    if not section.subject.is_active:
        return 'Предмет допуска неактивен.'
    if not on_date:
        return 'Укажите дату занятия для проверки допуска.'
    if not valid_qualifications(staff, section, on_date).exists():
        return 'Нет подтверждённого действующего допуска к этому предмету и формату на дату занятия.'
    if deadline and deadline > on_date:
        # Every date of an assigned SDO period must be covered; separate certificates may form continuous coverage.
        periods = InstructorQualification.objects.filter(staff=staff, subject_id=section.subject_id,
            device_type=section.teaching_device_type, is_verified=True, effective_from__lte=deadline,
            valid_until__gte=on_date).select_related('superseded_by').order_by('effective_from')
        from datetime import timedelta
        covered = on_date - timedelta(days=1)
        for row in periods:
            if not row.certificate_number or (not row.is_active and not row.superseded_by_id and not row.revoked_on):
                continue
            end = row.valid_until
            if row.revoked_on: end = min(end, row.revoked_on - timedelta(days=1))
            if row.superseded_by_id: end = min(end, row.superseded_by.effective_from - timedelta(days=1))
            if row.effective_from <= covered + timedelta(days=1) and end > covered: covered = end
            if covered >= deadline: return None
        return 'Допуск не покрывает весь период занятия до даты окончания.'
    return None


def audit_qualification(user, obj, operation, reason='', before=None):
    from execution.methodist_views import audit
    audit(user, obj, {'operation': operation, 'reason': reason, 'before': before,
        'after': {'certificate_number': obj.certificate_number, 'valid_until': str(obj.valid_until or ''),
            'effective_from': str(obj.effective_from), 'is_verified': obj.is_verified,
            'revoked_on': str(obj.revoked_on or '')}})


@transaction.atomic
def register_qualification(user, staff_id, data, *, reason=''):
    # Serialize renewal and confirmation for all subjects of the same instructor.
    staff = Staff.objects.select_for_update().get(pk=staff_id)
    subject = data['subject']
    device = data.get('device_type', 'CLASS')
    if not subject.is_active:
        raise ValidationError('Предмет неактивен.')
    number = (data.get('certificate_number') or '').strip()
    until = data.get('valid_until')
    start = data.get('effective_from') or timezone.localdate()
    issue = data.get('issue_date')
    verified = bool(number and until)
    if (number or until) and not verified:
        raise ValidationError('Для подтверждения укажите и номер документа, и дату окончания.')
    if until and until < start:
        raise ValidationError('Дата окончания не может быть раньше даты начала действия.')
    if issue and until and issue > until:
        raise ValidationError('Дата выдачи документа не может быть позже даты окончания.')
    current = InstructorQualification.objects.select_for_update().filter(staff=staff, subject=subject,
        device_type=device, is_active=True).first()
    if current and not verified:
        raise ValidationError('По этому предмету и формату уже есть запись. Подтвердите её или зарегистрируйте новый документ.')
    if current and start < current.effective_from:
        raise ValidationError('Новый документ не может начинать действовать раньше предыдущей записи.')
    if current and not reason.strip():
        raise ValidationError('Укажите причину замены или продления документа.')
    if current:
        current.is_active = False
        current.save(update_fields=['is_active'])
    row = InstructorQualification.objects.create(staff=staff, subject=subject, device_type=device,
        certificate_number=number or None, valid_until=until, effective_from=start, issue_date=issue,
        waiver_notes=data.get('waiver_notes', ''), is_verified=verified,
        confirmed_at=timezone.now() if verified else None, confirmed_by=user if verified else None)
    if current:
        current.superseded_by = row
        current.save(update_fields=['superseded_by'])
        audit_qualification(user, current, 'qualification_replaced', reason)
    if not staff.is_instructor:
        staff.is_instructor = True; staff.save(update_fields=['is_instructor'])
    audit_qualification(user, row, 'qualification_registered', reason)
    return row


@transaction.atomic
def confirm_qualification(user, pk, data):
    original = InstructorQualification.objects.get(pk=pk)
    Staff.objects.select_for_update().get(pk=original.staff_id)
    row = InstructorQualification.objects.select_for_update().get(pk=pk)
    if row.is_verified or not row.is_active:
        raise ValidationError('Документ уже подтверждён или заменён. Используйте продление или замену с сохранением истории.')
    before = {'certificate_number': row.certificate_number, 'legacy_expiration_date': str(row.legacy_expiration_date or '')}
    number = (data.get('certificate_number') or '').strip()
    until = data.get('valid_until')
    start = data.get('effective_from') or row.effective_from
    if not number or not until: raise ValidationError('Укажите номер документа и дату окончания.')
    if until < start: raise ValidationError('Дата окончания не может быть раньше даты начала действия.')
    issue = data.get('issue_date', row.issue_date)
    if issue and issue > until: raise ValidationError('Дата выдачи не может быть позже даты окончания.')
    row.certificate_number = number; row.valid_until = until; row.effective_from = start; row.issue_date = issue
    row.waiver_notes = data.get('waiver_notes', row.waiver_notes)
    row.is_verified = True; row.confirmed_at = timezone.now(); row.confirmed_by = user
    row.save(update_fields=['certificate_number', 'valid_until', 'effective_from', 'issue_date', 'waiver_notes', 'is_verified', 'confirmed_at', 'confirmed_by'])
    audit_qualification(user, row, 'qualification_confirmed', data.get('reason', ''), before)
    return row


@transaction.atomic
def revoke_qualification(user, pk, reason):
    original = InstructorQualification.objects.get(pk=pk)
    Staff.objects.select_for_update().get(pk=original.staff_id)
    row = InstructorQualification.objects.select_for_update().get(pk=pk)
    if not reason or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Укажите причину аннулирования (до 2000 символов).')
    if row.revoked_on or not row.is_active:
        raise ValidationError('Допуск уже аннулирован или заменён.')
    row.revoked_on = timezone.localdate(); row.revocation_reason = reason.strip(); row.is_active = False
    row.save(update_fields=['revoked_on', 'revocation_reason', 'is_active'])
    audit_qualification(user, row, 'qualification_revoked', reason)
    return row
