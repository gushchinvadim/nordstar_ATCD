from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Count

from core.services.schedule_generator import generate_schedule_for_group
from execution.models import Group, Enrollment
from people.models import Staff, Student
from references.models import Location
from training.models import Course, Module


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def groups_list(request):
    """
    API для получения списка групп с фильтрацией и пагинацией.

    Query параметры:
    - status: фильтр по статусу (по умолчанию: in_progress,completed)
    - direction: фильтр по направлению (frdo_template_type)
    - year: фильтр по году начала
    - search: поиск по номеру группы или названию модуля
    - page: номер страницы (по умолчанию: 1)
    - page_size: размер страницы (по умолчанию: 15)
    """

    # Базовый queryset с оптимизацией
    queryset = Group.objects.select_related(
        'module',
        'module__course',
        'mentor',
        'curator'
    ).annotate(
        students_count=Count('enrollment')
    )

    # Фильтр по статусу
    status = request.query_params.get('status', 'in_progress,completed')
    if status:
        statuses = [s.strip() for s in status.split(',')]
        queryset = queryset.filter(status__in=statuses)

    # Фильтр по направлению (Course.frdo_template_type)
    direction = request.query_params.get('direction')
    if direction and direction != 'all':
        queryset = queryset.filter(module__course__frdo_template_type=direction)

    # Фильтр по году начала
    year = request.query_params.get('year')
    if year:
        try:
            queryset = queryset.filter(start_date__year=int(year))
        except ValueError:
            pass

    # Поиск по номеру группы или названию модуля
    search = request.query_params.get('search')
    if search:
        queryset = queryset.filter(
            Q(assigned_number__icontains=search) |
            Q(module__title__icontains=search) |
            Q(module__code__icontains=search)
        )

    # Сортировка по дате создания (новые сверху)
    queryset = queryset.order_by('-assigned_at')

    # Пагинация
    try:
        page = int(request.query_params.get('page', 1))
    except ValueError:
        page = 1

    try:
        page_size = int(request.query_params.get('page_size', 15))
    except ValueError:
        page_size = 15

    # Ограничиваем размер страницы
    page_size = min(page_size, 50)

    # Общее количество
    total = queryset.count()

    # Получаем группы для текущей страницы
    start = (page - 1) * page_size
    end = start + page_size
    groups = queryset[start:end]

    # Сериализация данных
    data = []
    for group in groups:
        data.append({
            'id': group.id,
            'assigned_number': group.assigned_number,
            'module_code': group.module.code if group.module else '',
            'module_title': group.module.title if group.module else '',
            'direction': group.module.course.frdo_template_type if group.module and group.module.course else '',
            'direction_display': group.module.course.get_frdo_template_type_display() if group.module and group.module.course else '',
            'start_date': group.start_date.strftime('%d.%m.%Y') if group.start_date else None,
            'end_date': group.end_date.strftime('%d.%m.%Y') if group.end_date else None,
            'status': group.status,
            'status_display': group.get_status_display(),
            'students_count': group.students_count,
            'curator': group.curator.full_name if group.curator else None,
            'mentor': group.mentor.full_name if group.mentor else None,
        })

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'results': data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def directions_list(request):
    """
    API для получения списка направлений.
    Безопасный вариант: если в базе пусто или ошибка, вернет варианты из модели.
    """
    try:
        # Пытаемся получить реальные направления, которые уже используются в группах
        courses = Course.objects.exclude(
            frdo_template_type__isnull=True
        ).exclude(
            frdo_template_type=''
        ).values_list('frdo_template_type', flat=True).distinct()

        directions = []
        for code in courses:
            directions.append({
                'code': code,
                'title': dict(Course.FRDO_TEMPLATE_CHOICES).get(code, code),
            })

        # Если в базе пока нет таких записей, берем все возможные варианты из модели
        if not directions:
            for code, title in Course.FRDO_TEMPLATE_CHOICES:
                directions.append({'code': code, 'title': title})

        # Сортируем по алфавиту для красоты
        directions.sort(key=lambda x: x['title'])
        return Response(directions)

    except Exception as e:
        # Если произошла любая ошибка (например, опечатка в имени поля),
        # мы всё равно вернем корректный список из choices, чтобы фронтенд работал
        fallback_directions = [
            {'code': code, 'title': title}
            for code, title in Course.FRDO_TEMPLATE_CHOICES
        ]
        return Response(fallback_directions)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_detail(request, group_id):
    """
    API для получения детальной информации о группе.
    """
    try:
        group = Group.objects.select_related(
            'module',
            'module__course',
            'mentor',
            'curator',
            'location'
        ).get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Группа не найдена'}, status=404)

    # Подсчёт студентов по статусам
    enrollments = Enrollment.objects.filter(group=group)
    students_by_status = enrollments.values('status').annotate(count=Count('id'))

    data = {
        'id': group.id,
        'assigned_number': group.assigned_number,
        'module': {
            'code': group.module.code if group.module else '',
            'title': group.module.title if group.module else '',
            'direction': group.module.course.frdo_template_type if group.module and group.module.course else '',
            'direction_display': group.module.course.get_frdo_template_type_display() if group.module and group.module.course else '',
        },
        'start_date': group.start_date.strftime('%d.%m.%Y') if group.start_date else None,
        'start_face_to_face': group.start_face_to_face.strftime('%d.%m.%Y') if group.start_face_to_face else None,
        'end_date': group.end_date.strftime('%d.%m.%Y') if group.end_date else None,
        'status': group.status,
        'status_display': group.get_status_display(),
        'location': group.location.full_name if group.location else None,
        'mentor': group.mentor.full_name if group.mentor else None,
        'curator': group.curator.full_name if group.curator else None,
        'director': group.director.full_name if group.director else None,
        'students_count': enrollments.count(),
        'students_by_status': {item['status']: item['count'] for item in students_by_status},
        'is_sdo': group.is_sdo,
    }

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_info(request):
    """Возвращает информацию о текущем авторизованном пользователе"""
    user = request.user

    # Пытаемся получить полное имя.
    # Если у вас кастомная модель Staff с полем full_name, сработает оно.
    # Иначе собираем из first_name и last_name стандартной модели User.
    full_name = getattr(user, 'full_name', None) or f"{user.first_name}".strip() or user.username

    return Response({
        'username': user.username,
        'full_name': full_name,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    })


from training.models import Module
from people.models import Staff, Student
from references.models import Location


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def modules_list(request):
    """Список модулей для выпадающего списка"""
    modules = Module.objects.select_related('course').all().order_by('code')

    data = [
        {
            'id': module.id,
            'code': module.code,
            'title': module.title,
            'course_title': module.course.title if module.course else '',
        }
        for module in modules
    ]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_list(request):
    """Список сотрудников для выпадающего списка"""
    staff = Staff.objects.filter(is_active=True).order_by('full_name')

    data = [
        {
            'id': s.id,
            'full_name': s.full_name,
            'position': s.position.name if s.position else '',
        }
        for s in staff
    ]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def students_list(request):
    """Список студентов для выпадающего списка"""
    students = Student.objects.filter(is_active=True).order_by('surname', 'name')

    data = [
        {
            'id': s.id,
            'full_name': f"{s.surname} {s.name} {s.patronymic}".strip(),
            'profession': s.profession.name if s.profession else '',
        }
        for s in students
    ]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def locations_list(request):
    """Список мест проведения"""
    locations = Location.objects.all().order_by('name')

    data = [
        {
            'id': loc.id,
            'title': f"{loc.name} - {loc.full_name}" if loc.full_name else loc.name,
            'code': loc.name,
            'full_name': loc.full_name or '',
        }
        for loc in locations
    ]

    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_group(request):
    """Создание новой группы"""
    from execution.models import Group, Enrollment
    from django.utils import timezone

    data = request.data

    try:
        # Генерируем номер группы
        serial_number = data.get('serial_number', '')
        application = data.get('application', '')
        assigned_number = f"{serial_number}-{application}" if serial_number and application else ''

        # Генерируем номер приказа о зачислении
        order_in_date = data.get('order_in_date')
        order_in_number = f"{assigned_number}-З" if assigned_number else ''

        # Создаем группу
        group = Group.objects.create(
            serial_number=serial_number,
            application=application,
            assigned_number=assigned_number,
            module_id=data.get('module_id'),
            status=data.get('status', 'enrolling'),
            location_id=data.get('location_id') if data.get('location_id') else None,
            start_date=data.get('start_date'),
            start_face_to_face=data.get('start_face_to_face') if data.get('start_face_to_face') else None,
            end_date=data.get('end_date') if data.get('end_date') else None,
            is_sdo=data.get('is_sdo', False),
            start_time_default=data.get('start_time_default', '09:00:00'),
            mentor_id=data.get('mentor_id') if data.get('mentor_id') else None,
            curator_id=data.get('curator_id') if data.get('curator_id') else None,
            director_id=data.get('director_id') if data.get('director_id') else None,
            order_in_number=order_in_number,
            order_in_date=order_in_date,
            assigned_by=request.user.staff if hasattr(request.user, 'staff') else None,
            assigned_at=timezone.now(),
        )

        # Создаем назначения (enrollments)
        enrollments_data = data.get('enrollments', [])
        for enrollment_data in enrollments_data:
            Enrollment.objects.create(
                group=group,
                student_id=enrollment_data.get('student_id'),
                number_in_group=enrollment_data.get('number_in_group'),
                status=enrollment_data.get('status', 'enrolled'),
            )

        return Response({
            'success': True,
            'group_id': group.id,
            'assigned_number': group.assigned_number,
            'message': f'Группа {group.assigned_number} успешно создана'
        }, status=201)

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_detail_edit(request, group_id):
    """Получение полных данных группы для формы редактирования"""
    try:
        group = Group.objects.select_related(
            'module', 'module__course', 'location',
            'mentor', 'curator', 'director'
        ).get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Группа не найдена'}, status=404)

    # Получаем назначения
    enrollments_qs = Enrollment.objects.select_related('student', 'student__profession').filter(
        group=group
    ).order_by('number_in_group')

    enrollments_data = []
    for e in enrollments_qs:
        enrollments_data.append({
            'id': e.id,
            'student_id': e.student.id,
            'student_name': f"{e.student.surname} {e.student.name} {e.student.patronymic}".strip(),
            'profession': e.student.profession.name if e.student.profession else '',
            'number_in_group': e.number_in_group,
            'status': e.status,
        })

    # Вспомогательные функции для безопасного форматирования
    def safe_date(d):
        return d.strftime('%Y-%m-%d') if d else ''

    def safe_time(t):
        return str(t)[:5] if t else '09:00'

    data = {
        'id': group.id,
        'serial_number': group.serial_number or '',
        'application': group.application or '',
        'assigned_number': group.assigned_number or '',
        'module_id': group.module.id if group.module else None,
        'status': group.status,

        'location_id': group.location.id if group.location else None,
        'start_date': safe_date(group.start_date),
        'start_face_to_face': safe_date(group.start_face_to_face),
        'end_date': safe_date(group.end_date),
        'is_sdo': group.is_sdo,
        'start_time_default': safe_time(group.start_time_default),

        'mentor_id': group.mentor.id if group.mentor else None,
        'curator_id': group.curator.id if group.curator else None,
        'director_id': group.director.id if group.director else None,

        'order_in_date': safe_date(group.order_in_date),

        'enrollments': enrollments_data,  # <-- ОБЯЗАТЕЛЬНО МАССИВ
    }

    return Response(data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_group(request, group_id):
    """Обновление данных группы"""
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Группа не найдена'}, status=404)

    data = request.data

    # Обновляем основные поля
    if 'serial_number' in data:
        group.serial_number = data['serial_number']
    if 'application' in data:
        group.application = data['application']
    if 'module_id' in data:
        group.module_id = data['module_id']
    if 'status' in data:
        group.status = data['status']

    # Время и место
    if 'location_id' in data:
        group.location_id = data['location_id'] if data['location_id'] else None
    if 'start_date' in data:
        group.start_date = data['start_date']
    if 'start_face_to_face' in data:
        group.start_face_to_face = data['start_face_to_face'] if data['start_face_to_face'] else None
    if 'end_date' in data:
        group.end_date = data['end_date'] if data['end_date'] else None
    if 'is_sdo' in data:
        group.is_sdo = data['is_sdo']
    if 'start_time_default' in data:
        group.start_time_default = data['start_time_default']

    # Преподавательский состав
    if 'mentor_id' in data:
        group.mentor_id = data['mentor_id'] if data['mentor_id'] else None
    if 'curator_id' in data:
        group.curator_id = data['curator_id'] if data['curator_id'] else None
    if 'director_id' in data:
        group.director_id = data['director_id'] if data['director_id'] else None

    # Приказ о зачислении
    if 'order_in_date' in data:
        group.order_in_date = data['order_in_date'] if data['order_in_date'] else None
        # Автоматически обновляем номер приказа
        if group.assigned_number:
            group.order_in_number = f"{group.assigned_number}-З"

    # Автоматически обновляем номер группы если изменились serial_number или application
    if group.serial_number and group.application:
        group.assigned_number = f"{group.serial_number}-{group.application}"

    group.save()

    # Обновляем назначения (enrollments)
    if 'enrollments' in data:
        # Удаляем старые назначения
        Enrollment.objects.filter(group=group).delete()

        # Создаем новые
        for enrollment_data in data['enrollments']:
            if enrollment_data.get('student_id'):
                Enrollment.objects.create(
                    group=group,
                    student_id=enrollment_data['student_id'],
                    number_in_group=enrollment_data.get('number_in_group', 1),
                    status=enrollment_data.get('status', 'enrolled'),
                )

    return Response({
        'success': True,
        'message': f'Группа {group.assigned_number} успешно обновлена',
        'group_id': group.id
    })




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_group_schedule(request, group_id):
    """Генерирует расписание для группы, вызывая существующий Python-сервис"""
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'success': False, 'error': 'Группа не найдена'}, status=404)

    try:
        # Вызываем вашу существующую функцию!
        # Она сама удалит старое расписание и создаст новое
        created_count = generate_schedule_for_group(group)

        return Response({
            'success': True,
            'message': f'Расписание успешно сгенерировано. Создано занятий: {created_count}'
        })

    except ValueError as e:
        # Ловим ваши кастомные ошибки, например "У группы не выбран модуль"
        return Response({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return Response({'success': False, 'error': f'Ошибка генерации: {str(e)}'}, status=500)