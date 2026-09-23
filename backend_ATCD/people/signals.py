# people/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Student, Staff


@receiver(post_save, sender=Student)
def create_student_user(sender, instance, created, **kwargs):
    """Автоматически создает Django User при создании Student"""
    if created:
        email = getattr(instance, 'email', '')

        # Логика логина и пароля
        if email and '@' in email:
            username = email.split('@')[0].strip().lower()
            password = email  # Пароль = полный email
        else:
            username = f"student_{instance.id}"
            password = "Nordstar2026!"  # Fallback

        # Проверка на уникальность логина
        if User.objects.filter(username=username).exists():
            username = f"{username}_{instance.id}"

        # Создаем пользователя
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=instance.name,
            last_name=instance.surname
        )

        # Привязываем User к Student
        instance.user = user
        instance.save(update_fields=['user'])


@receiver(post_save, sender=Staff)
def create_staff_user(sender, instance, created, **kwargs):
    """Автоматически создает Django User при создании Staff"""
    if created:
        email = getattr(instance, 'email', '')

        if email and '@' in email:
            username = email.split('@')[0].strip().lower()
            password = email
        else:
            username = f"staff_{instance.id}"
            password = "Nordstar2026!"

        if User.objects.filter(username=username).exists():
            username = f"{username}_{instance.id}"

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=instance.full_name.split()[0] if instance.full_name else '',
            last_name=instance.full_name.split()[-1] if instance.full_name else ''
        )

        instance.user = user
        instance.save(update_fields=['user'])