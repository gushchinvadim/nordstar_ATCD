"""Methodist maintenance actions, separate from training assignments."""
import json
import secrets
import shutil
import string
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from people.models import Student
from .models import Group, ComplianceLog


class IsMethodist(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        staff = getattr(user, 'staff', None)
        return bool(user.is_authenticated and user.is_active and (
            user.is_superuser or (staff is not None and staff.is_active and staff.fptitle)
            or (user.is_staff and staff is None)))


def audit(user, obj, details):
    LogEntry.objects.create(user=user, content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk), object_repr=str(obj)[:200], action_flag=CHANGE,
        change_message=json.dumps(details, ensure_ascii=False))


def reset_allowed(student):
    user = student.user
    return bool(user and not user.is_superuser and not user.is_staff and not hasattr(user, 'staff'))


class StudentEditSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, default=None)
    can_reset_password = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ['id', 'surname', 'name', 'patronymic', 'name_latin', 'surname_latin', 'email', 'employee_id', 'username', 'can_reset_password']
        read_only_fields = ['id', 'username', 'can_reset_password']

    def get_can_reset_password(self, obj):
        return reset_allowed(obj)

    def validate_email(self, value):
        others = Student.objects.filter(email__iexact=value).exclude(pk=self.instance.pk if self.instance else None)
        if value and others.exists():
            raise serializers.ValidationError('Этот email указан у другого слушателя.')
        return value

    def validate(self, attrs):
        allowed = set(self.fields) - set(self.Meta.read_only_fields)
        if set(self.initial_data) - allowed:
            raise serializers.ValidationError('Можно изменять только личные данные слушателя. Назначения, логин и права не редактируются.')
        return attrs


class StudentList(generics.ListAPIView):
    permission_classes = [IsMethodist]
    serializer_class = StudentEditSerializer

    def get_queryset(self):
        rows = Student.objects.select_related('user', 'user__staff').order_by('surname', 'name', 'pk')
        search = self.request.query_params.get('search', '').strip()
        if search:
            for term in search.split()[:6]:
                rows = rows.filter(Q(surname__icontains=term) | Q(name__icontains=term) | Q(patronymic__icontains=term)
                    | Q(email__icontains=term) | Q(employee_id__icontains=term) | Q(user__username__icontains=term))
        return rows


class StudentDetail(generics.RetrieveUpdateAPIView):
    permission_classes = [IsMethodist]
    serializer_class = StudentEditSerializer
    queryset = Student.objects.select_related('user', 'user__staff')
    http_method_names = ['get', 'patch', 'head', 'options']

    @transaction.atomic
    def perform_update(self, serializer):
        student = Student.objects.select_for_update().get(pk=serializer.instance.pk)
        before = {key: getattr(student, key) for key in serializer.validated_data}
        # Freeze legacy listener signatures before changing the live profile.
        ComplianceLog.objects.filter(student=student, staff__isnull=True, actor_name_snapshot='').update(
            actor_name_snapshot=str(student).strip())
        serializer.instance = student
        saved = serializer.save()
        user = saved.user
        if user and reset_allowed(saved):
            user.first_name = saved.name
            user.last_name = saved.surname
            user.email = saved.email
            user.save(update_fields=['first_name', 'last_name', 'email'])
        audit(self.request.user, saved, {'operation': 'student_personal_data_changed', 'before': before,
            'after': {key: getattr(saved, key) for key in before}})


@api_view(['POST'])
@permission_classes([IsMethodist])
@transaction.atomic
def reset_student_password(request, pk):
    student = get_object_or_404(Student.objects.select_for_update(of=('self',)).select_related('user', 'user__staff'), pk=pk)
    if request.data.get('confirm') is not True:
        return Response({'error': 'Подтвердите сброс пароля.'}, status=400)
    if not reset_allowed(student):
        return Response({'error': 'Сброс доступен только обычной учётной записи слушателя, связанной с карточкой.'}, status=400)
    user = get_user_model().objects.select_for_update().get(pk=student.user_id)
    student.user = user
    if not reset_allowed(student):
        return Response({'error': 'Учётная запись получила служебные права. Сброс выполняет администратор.'}, status=400)
    if not user.is_active:
        return Response({'error': 'Учётная запись отключена. Обратитесь к администратору.'}, status=400)
    alphabet = string.ascii_letters + string.digits + '-_!'
    temporary = ''.join(secrets.choice(alphabet) for _ in range(18))
    user.set_password(temporary)
    user.last_login = None  # Existing first-login flow prompts for a personal password.
    user.save(update_fields=['password', 'last_login'])
    audit(request.user, student, {'operation': 'student_password_reset', 'user_id': user.pk})
    response = Response({'username': user.username, 'temporary_password': temporary,
        'message': 'Передайте временный пароль лично. При входе слушателю будет предложено сменить его.'})
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['POST'])
@permission_classes([IsMethodist])
@transaction.atomic
def archive_group(request, group_id):
    group = get_object_or_404(Group.objects.select_for_update().select_related('module'), pk=group_id)
    if request.data.get('confirm_delete_files') is not True:
        return Response({'error': 'Подтвердите архивирование с удалением сформированных файлов.'}, status=400)
    if group.status == 'archived':
        return Response({'message': 'Группа уже находится в архиве.'})
    if group.status != 'completed':
        return Response({'error': 'Архивировать можно только завершённую группу.'}, status=400)
    from .group_archive import archive_training_group, ArchiveError
    try:
        archive_training_group(group, request.user, audit)
    except ArchiveError as error:
        return Response({'error': str(error)}, status=400)
    return Response({'message': 'Группа архивирована, сформированные файлы удалены. Данные обучения сохранены в БД.'})


class CancellationSerializer(serializers.Serializer):
    cancellation_date = serializers.DateField()
    cancellation_reason = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


@api_view(['GET', 'POST'])
@permission_classes([IsMethodist])
@transaction.atomic
def cancel_group(request, group_id):
    from django.utils import timezone
    from .local_time import group_today, group_timezone
    group = get_object_or_404(Group.objects.select_for_update(), pk=group_id)
    today = group_today(group)
    if request.method == 'GET':
        return Response({'cancellation_date': group.cancellation_date or today,
            'cancellation_reason': group.cancellation_reason, 'maximum_date': today,
            'timezone': str(group_timezone(group)), 'status': group.status})
    if group.status not in ('draft', 'enrolling', 'in_progress'):
        return Response({'error': 'Отменить можно только черновик, набор или обучающуюся группу. Уже закрытая или отменённая группа не изменена.'}, status=409)
    serializer = CancellationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if data['cancellation_date'] > today:
        return Response({'error': 'Дата отмены не может быть позже сегодняшнего дня по местному времени группы.'}, status=400)
    previous_status = group.status
    group.status = 'cancelled'
    group.cancellation_date = data['cancellation_date']
    group.cancellation_reason = data['cancellation_reason']
    group.cancelled_at = timezone.now()
    group.cancelled_by = request.user
    group.save(update_fields=['status', 'cancellation_date', 'cancellation_reason', 'cancelled_at', 'cancelled_by'])
    # Schedule rows, enrollments, signatures and generated files remain untouched.
    audit(request.user, group, {'operation': 'group_cancelled', 'previous_status': previous_status,
        'cancellation_date': group.cancellation_date.isoformat(), 'reason': group.cancellation_reason,
        'recorded_at': group.cancelled_at.isoformat()})
    return Response({'message': 'Группа отменена. История обучения и документы сохранены.'})
