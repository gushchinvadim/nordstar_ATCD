# people/models.py
from django.db import models
from django.contrib.auth.models import User
from references.models import Organization, Position, StudentProfession, Citizenship, AircraftType

class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, verbose_name="Пользователь Django", null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="Организация", null=True, blank=True)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, verbose_name="Должность", null=True, blank=True)
    full_name = models.CharField("ФИО", max_length=200)
    is_active = models.BooleanField("Активен", default=True)
    rauts_id = models.CharField("ID персонала в РАУЦ", max_length=50, blank=True)
    fptitle = models.BooleanField(default=False, verbose_name="Может оформлять документы")
    tptitle = models.BooleanField(default=False, verbose_name="Может подписывать документы")
    phone = models.CharField("Телефон", max_length=50, blank=True)
    email = models.EmailField("Email", blank=True)
    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ['full_name']
    def __str__(self): return self.full_name

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, verbose_name="Пользователь Django", null=True, blank=True)
    citizenship = models.ForeignKey(Citizenship, on_delete=models.SET_NULL, verbose_name="Гражданство", null=True, blank=True)
    aircraft_type = models.ForeignKey(AircraftType, on_delete=models.SET_NULL, verbose_name="Тип ВС", null=True, blank=True)
    profession = models.ForeignKey(StudentProfession, on_delete=models.SET_NULL, verbose_name="Профессия", null=True, blank=True)
    surname = models.CharField("Фамилия", max_length=100)
    name = models.CharField("Имя", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    sex = models.CharField("Пол", max_length=1, choices=[('M', 'Мужской'), ('F', 'Женский')], default='M')
    dob = models.DateField("Дата рождения", null=True, blank=True)
    snils = models.CharField("СНИЛС", max_length=20, blank=True)
    name_latin = models.CharField("Имя (латиницей)", max_length=100, blank=True)
    surname_latin = models.CharField("Фамилия (латиницей)", max_length=100, blank=True)
    employee_id = models.CharField("ID сотрудника", max_length=50, blank=True)
    # dcat_id = models.CharField("Код сертификата РАУЦ", max_length=50, blank=True)
    email = models.EmailField("Email", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    class Meta:
        verbose_name = "Слушатель"
        verbose_name_plural = "Слушатели"
        ordering = ['surname', 'name']
    def __str__(self): return f"{self.surname} {self.name} {self.patronymic}"

class StaffPosition(models.Model):
    """История должностей сотрудника"""
    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        verbose_name="Сотрудник",
        related_name='position_history'
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        verbose_name="Должность"
    )
    start_date = models.DateField("Дата начала")
    end_date = models.DateField("Дата окончания", null=True, blank=True)

    class Meta:
        verbose_name = "История должности"
        verbose_name_plural = "История должностей"
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.staff.full_name} - {self.position.name} ({self.start_date})"
