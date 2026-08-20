# references/models.py
from django.db import models



class AircraftType(models.Model):
    name = models.CharField("Тип ВС", max_length=100)
    code = models.CharField("Код", max_length=80, unique=True)
    class Meta:
        verbose_name = "Тип ВС"
        verbose_name_plural = "Типы ВС"
        ordering = ['name']
    def __str__(self): return self.name

class Citizenship(models.Model):
    name = models.CharField("Страна", max_length=100)
    code = models.PositiveIntegerField("Код страны по ОКСМ", unique=True)
    class Meta:
        verbose_name = "Гражданство"
        verbose_name_plural = "Гражданство"
        ordering = ['name']
    def __str__(self): return f"{self.name} ({self.code})"


class Position(models.Model):
    name = models.CharField("Название должности", max_length=200)
    code = models.CharField("Код", max_length=20, blank=True)
    description = models.TextField("Описание", blank=True)
    class Meta:
        verbose_name = "Должность сотрудника"
        verbose_name_plural = "Должности сотрудников"
        ordering = ['name']
    def __str__(self): return self.name

class StudentProfession(models.Model):
    name = models.CharField("Название профессии", max_length=100)
    code = models.CharField("Код", max_length=20, blank=True)
    description = models.TextField("Описание", blank=True)
    class Meta:
        verbose_name = "Профессия слушателя"
        verbose_name_plural = "Профессии слушателей"
        ordering = ['name']
    def __str__(self): return self.name

class Location(models.Model):
    name = models.CharField("Код города IATA", max_length=10, help_text="DME")
    full_name = models.CharField("Географическое название", max_length=50, help_text="Домодедово", null=True, blank=True)
    addr = models.CharField("Код РАУЦ (Место проведения)", max_length=10, null=True, blank=True, help_text="Например: 174")
    dept = models.CharField("Код РАУЦ (Филиал)", max_length=10, null=True, blank=True, help_text="Например: 37")

    class Meta:
        verbose_name = "Местоположение"
        verbose_name_plural = "Местоположения"
        ordering = ['name']

    def __str__(self):
        return self.full_name

class Organization(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, verbose_name="Местоположение", null=True, blank=True)
    company_name = models.CharField("Название компании", max_length=200)
    address = models.CharField("Адрес", max_length=300, blank=True)
    is_active = models.BooleanField("Активна", default=True)
    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ['company_name']
    def __str__(self): return self.company_name


class Classroom(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, verbose_name="Местоположение")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="Организация", null=True,
                                     blank=True)
    contact_name = models.ForeignKey('people.Staff', on_delete=models.SET_NULL, verbose_name="Ответственный сотрудник",
                                     null=True, blank=True)
    title = models.CharField("Название", max_length=200)
    address = models.CharField("Фактический адрес", max_length=300, blank=True, null=True,
                               help_text="Если не заполнен, используется адрес организации")  # ← Опционально
    audience = models.CharField("Аудитория", max_length=100, blank=True)

    @property
    def full_address(self):
        """Возвращает адрес аудитории или адрес организации"""
        if self.address:
            return self.address
        elif self.organization and self.organization.address:
            return self.organization.address
        return ""

    class Meta:
        verbose_name = "Аудитория/Тренажёр"
        verbose_name_plural = "Аудитории/Тренажёры"
        ordering = ['title']
    def __str__(self): return f"{self.title} ({self.audience})"

class License(models.Model):
    organ = models.CharField("Название органа", max_length=200)
    license_number = models.CharField("Номер лицензии", max_length=100)
    issue_date = models.DateField("Дата выдачи", null=True, blank=True)
    end_date = models.DateField("Дата окончания", null=True, blank=True)

    class Meta:
        verbose_name = "Государственная лицензия"
        verbose_name_plural = "Государственные лицензии"
        ordering = ['organ']

    def __str__(self):
        return f"{self.organ} - {self.license_number}"