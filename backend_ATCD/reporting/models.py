from django.db import models
from django.conf import settings
from execution.models import Group, Enrollment, Certificate
from people.models import Student


class RegulatoryReport(models.Model):
    """Шапка отчёта. Создаётся автоматически при генерации из карточки группы."""

    REPORT_TYPES = [
        ('rauc', 'РАУЦ'),
        ('frdo', 'ФИС ФРДО'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Черновик (есть ошибки)'),
        ('generated', 'Сформирован (готов к скачиванию)'),
        ('downloaded', 'Скачан методистом'),
        ('sent', 'Отправлен в госорган'),
        ('accepted', 'Принят'),
        ('rejected', 'Отклонён'),
    ]

    report_type = models.CharField("Тип отчёта", max_length=10, choices=REPORT_TYPES)
    title = models.CharField("Название", max_length=200, blank=True)  # Генерируется авто

    # Файлы
    excel_file = models.FileField("Excel (для проверки)", upload_to='reports/excel/', blank=True)
    xml_file = models.FileField("XML (для отправки)", upload_to='reports/xml/', blank=True)
    xml_file_hash = models.CharField("SHA-256 хеш XML", max_length=64, blank=True)

    # Статус и жизненный цикл
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='draft')
    downloaded_at = models.DateTimeField("Дата скачивания", null=True, blank=True)
    sent_at = models.DateTimeField("Дата отправки", null=True, blank=True)
    rejection_reason = models.TextField("Причина отклонения", blank=True)
    rejection_date = models.DateField("Дата отклонения", null=True, blank=True)
    comment = models.TextField("Комментарий", blank=True)

    # Связи
    groups = models.ManyToManyField(Group, blank=True, verbose_name="Группы", related_name='regulatory_reports')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="Создал")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Отчёт для госоргана"
        verbose_name_plural = "Отчёты для госорганов"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title or 'Без названия'} ({self.get_report_type_display()})"


class RegulatoryReportItem(models.Model):
    """Строка отчёта (один слушатель). Хранит готовые данные для выгрузки."""

    report = models.ForeignKey(RegulatoryReport, on_delete=models.CASCADE, related_name='items')
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    certificate = models.ForeignKey(Certificate, on_delete=models.PROTECT, null=True, blank=True)

    is_valid = models.BooleanField("Валидна", default=True)
    validation_error = models.TextField("Ошибка", blank=True)

    # Словарь с данными строго по колонкам из ваших Excel-шаблонов
    payload = models.JSONField("Данные (Payload)", default=dict)

    class Meta:
        verbose_name = "Строка отчёта"
        verbose_name_plural = "Строки отчётов"
        ordering = ['id']

    def __str__(self):
        return f"Строка {self.id} ({self.student})"