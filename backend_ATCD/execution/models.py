
from django.db import models
from django.utils import timezone
from datetime import time, date
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from people.models import Staff, Student
from references.models import Location, Classroom
from training.models import Module, Section


def _fmt(minutes):
    """Форматирует минуты в ЧЧ:ММ"""
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


class Group(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('enrolling', 'Набор'),
        ('in_progress', 'Обучение'),
        ('completed', 'Завершена'),
        ('archived', 'Архив'),
        ('cancelled', 'Отменена'),
    ]

    assigned_number = models.CharField(max_length=30, verbose_name="Номер группы", help_text="123.2026")
    application = models.CharField(max_length=30, verbose_name="Номер заявки", help_text="СЗ/3-123")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, verbose_name="Модуль")
    order_in_number = models.CharField(max_length=50, blank=True, verbose_name="Номер приказа о зачислении")
    order_in_date = models.DateField(null=True, blank=True, verbose_name="Дата приказа о зачислении")
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Место проведения")
    start_date = models.DateField(verbose_name="Дата начала СДО")
    start_face_to_face = models.DateField(null=True, blank=True, verbose_name="Дата начала очных занятий")
    end_date = models.DateField(null=True, blank=True, verbose_name="Плановая дата окончания")

    mentor = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Наставник группы",
                                related_name='mentor_groups')
    curator = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Специалист 1 категории",
                                related_name='curated_groups')
    director = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Подписывающий руководитель",
                                related_name='signing_executive')
    is_sdo = models.BooleanField(default=False, verbose_name="Только СДО (без очных занятий)")
    start_time_default = models.TimeField(
        "Время начала очных занятий",
        default=time(9, 0),
        help_text="Время начала первого занятия в день (например, 09:00 или 14:00)"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Статус")
    assigned_at = models.DateTimeField(default=timezone.now, verbose_name="Дата создания")
    assigned_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name="Создал сотрудник", related_name='created_groups')

    class Meta:
        verbose_name = "Группа"
        verbose_name_plural = "Группы"
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.assigned_number} ({self.module.code})"


class Enrollment(models.Model):
    STATUS_CHOICES = [
        ("enrolled", "Зачислен"),
        ("in_progress", "Обучается"),  # ← НОВОЕ
        ("completed", "Успешно завершен"),
        ("failed", "Не завершен"),
        ("dismissed", "Отчислен"),
        ("academic_leave", "Академический отпуск"),
        ("partial", "Частично прослушал"),  # ← НОВОЕ
        ("absent", "Не явился"),  # ← НОВОЕ
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name="Группа")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="Слушатель")
    number_in_group = models.PositiveIntegerField(verbose_name="Порядковый номер в группе")


    order_out_number = models.CharField(max_length=50, blank=True,
                                        verbose_name="Номер приказа об отчислении. Если завершен успешно в конце 'ОК', если нет - 'ОТ'")
    order_out_date = models.DateField(null=True, blank=True, verbose_name="Дата приказа об отчислении")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="enrolled", verbose_name="Статус")
    completed_at = models.DateField(null=True, blank=True, verbose_name="Дата завершения")
    dismissal_date = models.DateField(null=True, blank=True, verbose_name="Дата отчисления")
    dismissal_reason = models.TextField(blank=True, verbose_name="Причина отчисления")

    # === НОВЫЕ ПОЛЯ ===
    final_result = models.CharField(
        "Итоговый результат",
        max_length=20,
        blank=True,
        help_text="Заполняется автоматически: passed/failed"
    )

    total_hours_completed = models.DecimalField(
        "Освоено часов",
        max_digits=6,
        decimal_places=1,
        default=0,
        help_text="Сумма часов по сданным разделам"
    )

    class Meta:
        verbose_name = "Назначение"
        verbose_name_plural = "Назначения"
        ordering = ['group', 'number_in_group']
        unique_together = ['group', 'number_in_group']

    def __str__(self):
        return f"{self.student} → {self.group} ({self.get_status_display()})"

    # === НОВЫЕ МЕТОДЫ ===

    def get_total_hours_plan(self):
        """Плановое количество часов по модулю"""
        from training.models import Module
        if self.group and self.group.module:
            return self.group.module.duration
        return 0

    def get_completion_percentage(self):
        """Процент освоения программы"""
        plan = self.get_total_hours_plan()
        if plan == 0:
            return 0
        return round((self.total_hours_completed / plan) * 100, 1)

    def check_all_sections_passed(self):
        """Проверяет, сданы ли все оцениваемые разделы.
        Принудительно пересчитывает passed для каждой оценки."""
        from training.models import Section

        if not self.group or not self.group.module:
            return False

        # Получаем все разделы модуля, которые подлежат оцениванию
        sections_to_assess = Section.objects.filter(
            stage__module=self.group.module,
            grade_type__in=['numeric', 'binary']
        )

        if not sections_to_assess.exists():
            return True

        for section in sections_to_assess:
            # Берем последнюю попытку
            assessment = self.assessments.filter(
                section=section
            ).order_by('-attempt_number').first()

            # Если оценки нет — не сдано
            if not assessment:
                return False

            # ПРИНУДИТЕЛЬНО пересчитываем passed (на случай рассинхрона с БД)
            if not assessment.passed:
                assessment.passed = assessment.calculate_passed()
                assessment.save(update_fields=['passed'])

            if not assessment.passed:
                return False

        return True

    def generate_order_out_number(self, order_type='completed', is_individual=False):
        """
        Генерирует номер приказа об отчислении/завершении.

        Args:
            order_type: 'completed' или 'dismissed'
            is_individual: True если индивидуальный приказ, False если групповой

        Returns:
            Номер приказа
        """
        group = self.group
        base_number = f"{group.assigned_number}-{group.application}"

        if order_type == 'completed':
            suffix = 'ОК'
        elif order_type == 'dismissed':
            suffix = 'ОТ'
        else:
            suffix = order_type

        if is_individual:
            # Индивидуальный приказ - добавляем номер студента
            return f"{base_number}-{suffix}-{self.number_in_group}"
        else:
            # Групповой приказ - один номер для всех
            return f"{base_number}-{suffix}"

    def calculate_total_hours(self):
        """Пересчитывает общее количество освоенных часов"""
        total = 0
        for assessment in self.assessments.filter(passed=True):
            if assessment.section:
                total += assessment.section.duration_hours
        self.total_hours_completed = total
        self.save(update_fields=['total_hours_completed'])
        return total



    def calculate_module_score(self):
        """Рассчитывает общую оценку модуля по правилу АУЦ"""
        from django.db.models import Avg

        # Берём только numeric оценки
        assessments = self.assessments.filter(
            passed=True,
            section__grade_type='numeric'
        )

        if not assessments.exists():
            return None

        # Считаем среднее
        scores = [a.score for a in assessments if a.score is not None]

        if not scores:
            return None

        avg = sum(scores) / len(scores)

        # Применяем правило округления АУЦ: 4.5 → 4, >4.5 → 5
        if avg < 4.5:
            final = 4
        else:
            final = 5

        self.final_score = final
        self.save(update_fields=['final_score'])
        return final

class ScheduleItem(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Запланировано'),
        ('in_progress', 'Идет'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name="Группа", related_name='schedule')
    section = models.ForeignKey('training.Section', on_delete=models.CASCADE, verbose_name="Дисциплина",
                                related_name='schedule_items')

    # НОВОЕ ПОЛЕ: Связь с конкретной сессией/темой (может быть пустым, если детализации нет)
    subsection = models.ForeignKey('training.Subsection', on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Тема/Сессия", related_name='schedule_items')

    date = models.DateField("Дата занятия")
    deadline = models.DateField("Дедлайн выполнения", null=True, blank=True, help_text="Для СДО: крайняя дата")
    start_time = models.TimeField("Время начала", null=True, blank=True)
    end_time = models.TimeField("Время окончания", null=True, blank=True)

    classroom = models.ForeignKey('references.Classroom', on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name="Аудитория/Тренажёр")
    instructor = models.ForeignKey('people.Staff', on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Преподаватель/Инструктор")

    session_type = models.CharField(max_length=50, verbose_name="Тип занятия", help_text="sdo, sim, base-N")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned', verbose_name="Статус")
    notes = models.TextField("Детализация времени / Примечание", null=True, blank=True)

    class Meta:
        verbose_name = "Занятие расписания"
        verbose_name_plural = "Расписание"
        ordering = ['date', 'start_time', 'section__order', 'subsection__order']  # Сортируем по дате, времени и порядку сессии

    def __str__(self):
        time_str = f"{self.start_time}-{self.end_time}" if self.start_time else "СДО"
        sub_title = f" ({self.subsection.title})" if self.subsection else ""
        return f"{self.date} {time_str} | {self.section.title[:30]}{sub_title}"


class Assessment(models.Model):
    """Оценка по разделу программы обучения"""

    ASSESSMENT_TYPES = [
        ('test', 'Тестирование'),
        ('practice', 'Практическое задание'),
        ('oral', 'Устный опрос'),
        ('exam', 'Итоговый экзамен'),
        ('attendance', 'Посещаемость'),
    ]

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='assessments',
        verbose_name="Зачисление"
    )

    section = models.ForeignKey(
        'training.Section',  # Используем строку, чтобы избежать циклического импорта
        on_delete=models.PROTECT,
        related_name='assessments',
        verbose_name="Раздел"
    )

    assessment_type = models.CharField(
        "Тип аттестации",
        max_length=20,
        choices=ASSESSMENT_TYPES,
        default='test'
    )

    score = models.IntegerField(
        "Балл",
        null=True,
        blank=True,
        help_text="Для numeric: 4 или 5. Для binary: 0 или 1"
    )

    passed = models.BooleanField(
        "Зачтено",
        default=False,
        help_text="Вычисляется автоматически на основе требований раздела"
    )

    attempt_number = models.PositiveSmallIntegerField(
        "Номер попытки",
        default=1,
        help_text="1 — первая сдача, 2 — пересдача и т.д."
    )

    assessment_date = models.DateField(
        "Дата аттестации",
        null=True,
        blank=True
    )

    instructor = models.ForeignKey(
        'people.Staff',  # Используем строку
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='given_assessments',
        verbose_name="Принял аттестацию"
    )

    notes = models.TextField(
        "Комментарий",
        blank=True,
        help_text="Например: 'пересдача', 'апелляция', 'досрочно'"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Оценка"
        verbose_name_plural = "Оценки"
        ordering = ['enrollment', 'section__stage__order', 'section__order', 'attempt_number']
        unique_together = ['enrollment', 'section', 'attempt_number']

    def __str__(self):
        return f"{self.enrollment.student} — {self.section.title}: {self.get_result_display()}"

    def get_result_display(self):
        """Человекочитаемое отображение результата"""
        if self.section.grade_type == 'none':
            return "Без оценки"
        if self.passed:
            return f"Сдано ({self.score})"
        return f"Не сдано ({self.score})"

    def calculate_passed(self):
        """Определяет, сдана ли аттестация на основе требований раздела"""
        if not self.section:
            return True

        grade_type = self.section.grade_type

        # Раздел не оценивается — всегда считаем сданным
        if grade_type == 'none':
            return True

        # Нет балла — не сдано
        if self.score is None:
            return False

        min_score = self.section.min_score
        if min_score is None:
            return True

        return self.score >= min_score

    def save(self, *args, **kwargs):
        """Автоматически вычисляем passed при сохранении"""
        self.passed = self.calculate_passed()
        super().save(*args, **kwargs)

        # После сохранения оценки — пересчитываем часы у студента
        self.enrollment.calculate_total_hours()


class Certificate(models.Model):
    """Свидетельство/сертификат о прохождении подготовки"""

    CERTIFICATE_TYPES = [
        ('certificate', 'Сертификат'),
        ('witness', 'Свидетельство'),
        ('diploma', 'Диплом'),
        ('reference', 'Справка'),
        ('credential', 'Удостоверение'),
    ]

    # Маппинг типов сертификатов на коды РАУЦ
    DCAT_ID_MAPPING = {
        'diploma': '1',        # Диплом о профессиональной переподготовке
        'witness': '2',        # Свидетельство о профессии рабочего, должности служащего
        'credential': '3',     # Удостоверение о повышении квалификации
        'certificate': '4',    # Сертификат
        'reference': '5',      # Справка об обучении или о периоде обучения
    }

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.PROTECT,
        related_name='certificates',
        verbose_name="Зачисление"
    )

    license = models.ForeignKey(
        'references.License',
        on_delete=models.PROTECT,
        related_name='certificates',
        verbose_name="Лицензия АУЦ",
        null=True,
        blank=True,
        help_text="Государственная лицензия, на основании которой выдан документ"
    )

    certificate_type = models.CharField(
        "Тип документа",
        max_length=20,
        choices=CERTIFICATE_TYPES,
        default='credential'
    )

    number = models.CharField(
        "Номер",
        max_length=50,
        unique=True,
        help_text="Например: 001.2026-СЗ/3-001-1"
    )
    issue_date = models.DateField("Дата выдачи", null=True, blank=True)

    # === Данные для печати (дублируются для стабильности) ===
    student_full_name = models.CharField("ФИО слушателя", max_length=200)
    student_profession = models.CharField("Специальность", max_length=200, blank=True)
    module_title = models.CharField("Название модуля", max_length=300)
    module_code = models.CharField("Код модуля", max_length=50)
    aircraft_type = models.CharField("Тип ВС", max_length=100, blank=True)
    total_hours = models.DecimalField("Всего часов", max_digits=6, decimal_places=1)
    qualification = models.CharField(
        "Квалификация",
        max_length=200,
        blank=True,
        help_text="Например: 'Пилот' или 'Бортпроводник'"
    )

    pdf_file = models.FileField(
        "PDF файл",
        upload_to='certificates/%Y/%m/',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def dcat_id(self):
        """
        Возвращает код вида документа РАУЦ на основе типа сертификата.
        Используется в отчёте РАУЦ.
        """
        return self.DCAT_ID_MAPPING.get(self.certificate_type, '')

    def get_expiry_date(self):
        """
        Возвращает дату окончания действия сертификата.
        Рассчитывается на основе validity_period модуля.
        """
        if not self.issue_date:
            return None

        module = self.enrollment.group.module if self.enrollment and self.enrollment.group else None

        if module and module.validity_period:
            from dateutil.relativedelta import relativedelta
            return self.issue_date + relativedelta(months=module.validity_period)

        # Fallback: +1 год
        from datetime import timedelta
        return self.issue_date + timedelta(days=365)

    @staticmethod
    def generate_number(enrollment):
        """
        Генерирует номер сертификата по формуле:
        group.assigned_number - group.application - enrollment.number_in_group

        Пример: 001.2026-СЗ/3-001-1
        """
        group = enrollment.group

        assigned_number = group.assigned_number  # "001.2026"
        application = group.application or ""  # "СЗ/3-001"
        number_in_group = enrollment.number_in_group  # 1 (без форматирования!)

        # Собираем базовый номер
        if application:
            base_number = f"{assigned_number}-{application}-{number_in_group}"
        else:
            base_number = f"{assigned_number}-{number_in_group}"

        # Проверяем уникальность и добавляем суффикс при необходимости
        counter = 1
        cert_number = f"{base_number}-{counter}"

        # Если номер без суффикса ещё не существует, используем его
        if not Certificate.objects.filter(number=base_number).exists():
            return base_number

        # Иначе добавляем суффикс -1, -2, -3...
        while Certificate.objects.filter(number=cert_number).exists():
            counter += 1
            cert_number = f"{base_number}-{counter}"

        return cert_number

    @classmethod
    def create_for_enrollment(cls, enrollment, **kwargs):
        """
        Создаёт сертификат для зачисления с автоматически определённым типом документа.
        """
        cert_number = cls.generate_number(enrollment)

        # === АВТООПРЕДЕЛЕНИЕ ТИПА ДОКУМЕНТА ===
        module = enrollment.group.module
        course = module.course if module else None

        # Берём тип из программы, если не передан явно
        certificate_type = kwargs.pop('certificate_type', None)
        if not certificate_type and course:
            certificate_type = course.default_certificate_type
        if not certificate_type:
            certificate_type = 'credential'  # fallback
        # ==========================================

        cert = cls.objects.create(
            number=cert_number,
            enrollment=enrollment,
            student_full_name=f"{enrollment.student.surname} {enrollment.student.name} {enrollment.student.patronymic}",
            student_profession=enrollment.student.profession,
            module_code=enrollment.group.module.code if enrollment.group.module else "",
            module_title=enrollment.group.module.title if enrollment.group.module else "",
            issue_date=enrollment.completed_at or date.today(),
            certificate_type=certificate_type,
            **kwargs
        )

        return cert

    class Meta:
        verbose_name = "Свидетельство/Сертификат"
        verbose_name_plural = "Свидетельства/Сертификаты"
        ordering = ['-issue_date', '-number']

    def __str__(self):
        return f"{self.number} — {self.student_full_name}"


class IndividualStudyPlan(models.Model):
    """Индивидуальный учебный план для студента"""

    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('active', 'Активен'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ]

    REASON_CHOICES = [
        ('business', 'Производственная необходимость'),
        ('disease', 'Болезнь'),
        ('vacation', 'Отпуск'),
        ('family', 'Семейные обстоятельства'),
    ]


    student = models.ForeignKey(
        'people.Student',
        on_delete=models.CASCADE,
        verbose_name="Студент"
    )
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        verbose_name="Группа"
    )

    # Основные даты
    start_date = models.DateField("Дата начала ИУП")
    end_date = models.DateField("Дата окончания ИУП")
    start_face_to_face = models.DateField(
        "Дата начала очных занятий ИУП",
        null=True, blank=True
    )

    # JSON с полным расписанием ИУП
    schedule_data = models.JSONField(
        "Расписание ИУП (JSON)",
        blank=True, null=True,
        help_text="Массив занятий с индивидуальными датами, инструкторами и аудиториями"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Статус"
    )

    reason = models.TextField(
        "Причина назначения ИУП",
        blank=True,
        choices=REASON_CHOICES
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'people.Staff',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Создал"
    )

    class Meta:
        verbose_name = "Индивидуальный учебный план"
        verbose_name_plural = "Индивидуальные учебные планы"
        ordering = ['-created_at']

    def __str__(self):
        return f"ИУП: {self.student} (группа {self.group.assigned_number})"