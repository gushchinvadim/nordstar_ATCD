# training/models.py
from django.db import models
from references.models import AircraftType


class Course(models.Model):

    FORM_OF_EDUCATION_CHOICES = [
        ('Очная', 'Очная'),
        ('Заочная', 'Заочная'),
        ('Очно-заочная (вечерняя)', 'Очно-заочная (вечерняя)'),
        ('Экстернат', 'Экстернат'),
    ]


    FRDO_TEMPLATE_CHOICES = [
        ('flight_attendant', 'Бортпроводники (Проф. обучение)'),
        ('pilot_engineer', 'Пилоты и инженеры (Доп. проф. программа)'),
    ]

    frdo_template_type = models.CharField(
        "Шаблон отчёта ФРДО",
        max_length=20,
        choices=FRDO_TEMPLATE_CHOICES,
        default='flight_attendant',
        help_text="Определяет структуру колонок и названия полей в отчёте ФРДО"
    )
    form_of_education = models.CharField(
        "Форма обучения",
        max_length=50,
        choices=FORM_OF_EDUCATION_CHOICES,
        blank=True,
        help_text="Форма обучения для отчётов ФРДО и сертификатов"
    )
    title = models.TextField("Название программы")
    prog_id = models.CharField("ID программы", max_length=50, blank=True)
    company_code = models.CharField("Код программы", max_length=50, blank=True)
    approved = models.CharField("Утверждена государственным органом", max_length=300, null=True, blank=True)
    approved_date = models.DateField("Дата утверждения", null=True, blank=True)
    default_certificate_type = models.CharField(
        "Тип документа по умолчанию",
        max_length=20,
        choices=[
            ('certificate', 'Сертификат'),
            ('witness', 'Свидетельство'),
            ('diploma', 'Диплом'),
            ('reference', 'Справка'),
            ('credential', 'Удостоверение'),
        ],
        default='credential',
        help_text="Тип документа, который будет автоматически присваиваться при выдаче сертификата для этой программы"
    )
    class Meta:
        verbose_name = "Программа обучения"
        verbose_name_plural = "Программы обучения"
        ordering = ['title']
    def __str__(self): return self.title


class Module(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        verbose_name="Программа",
        related_name='modules'
    )
    aircraft_type = models.ForeignKey(
        AircraftType,
        on_delete=models.SET_NULL,
        verbose_name="Тип ВС",
        null=True,
        blank=True
    )
    title = models.TextField("Название модуля")

    # === Идентификаторы для РАУЦ и ФРДО ===
    mod_id = models.CharField(
        "ID модуля РАУЦ",
        max_length=50,
        blank=True,
        help_text="Например: 8304 или 8886 (из справочника РАУЦ)"
    )

    code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Код модуля",
        help_text="Например: ППП.АУЦ.02-М.1"
    )
    duration = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="Плановые часы"
    )
    attachment_number = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
        verbose_name="Номер приложения для выписки сертификата"
    )

    # === Настройки для генерации документов ===
    certificate_template = models.CharField(
        "Шаблон сертификата",
        max_length=255,
        blank=True,
        help_text="Путь к шаблону, напр.: docs/certificate/course_1/certificate_c1_m1_batch.html"
    )
    validity_period = models.IntegerField(
        "Срок действия (месяцев)",
        null=True,
        blank=True,
        help_text="Период повторения подготовки в месяцах. Например: 12 (1 год), 24 (2 года), 36 (3 года). Оставьте пустым, если срок не ограничен."
    )

    class Meta:
        verbose_name = "Модуль"
        verbose_name_plural = "Модули"
        ordering = ['course', 'mod_id']

    def __str__(self):
        return self.code if self.code else self.title[:70]

class Stage(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, verbose_name="Модуль", related_name='stages')
    title = models.CharField("Название этапа", max_length=200)
    order = models.IntegerField("Порядковый номер", default=0)
    description = models.TextField("Описание", blank=True)
    class Meta:
        verbose_name = "Этап"
        verbose_name_plural = "Этапы"
        ordering = ['module', 'order']
    def __str__(self): return f"{self.module.title[:30]} - {self.title}"

class Section(models.Model):
    GRADE_TYPE_CHOICES = [('numeric', 'Числовая'), ('binary', 'Зачтено/Не зачтено'), ('none', 'Без оценки')]
    DETAIL_CHOICES = [
        ('sdo', 'СДО'), ('sim', 'Тренажер'), ('base-1', '1 урок'), ('base-2', '2 урока'),
        ('base-3', '3 урока'), ('base-4', '4 урока'), ('base-5', '5 уроков'),
        ('base-6', '6 уроков'), ('base-7', '7 уроков'), ('base-8', '8 уроков'), ('base-9', '9 уроков'), ('none', 'Не задано'),
    ]
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, verbose_name="Этап", related_name='sections')
    title = models.CharField("Название раздела/дисциплины", max_length=300)
    duration_hours = models.DecimalField("Продолжительность (часов)", max_digits=5, decimal_places=1, default=0)
    grade_type = models.CharField(max_length=10, choices=GRADE_TYPE_CHOICES, default='none', verbose_name="Тип оценки")
    min_score = models.IntegerField("Минимальный балл", null=True, blank=True)
    order = models.IntegerField("Порядковый номер", default=0)
    detail = models.CharField(max_length=50, choices=DETAIL_CHOICES, null=True, blank=True, verbose_name="Тип расписания")
    class Meta:
        verbose_name = "Раздел/Дисциплина"
        verbose_name_plural = "Разделы/Дисциплины"
        ordering = ['stage', 'order']
    def __str__(self): return f"{self.stage.title[:30]} - {self.title}"

class Subsection(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, verbose_name="Раздел", related_name='subsections')
    title = models.CharField("Название подраздела/сессии", max_length=300)
    detail = models.CharField(max_length=50, blank=True, null=True, verbose_name="Тип детализации")
    duration_hours = models.DecimalField("Продолжительность (часов)", max_digits=5, decimal_places=1, default=0)
    order = models.IntegerField("Порядковый номер", default=0)
    class Meta:
        verbose_name = "Подраздел/Сессия"
        verbose_name_plural = "Подразделы/Сессии"
        ordering = ['section', 'order']
    def __str__(self): return f"{self.section.title[:30]} - {self.title}"