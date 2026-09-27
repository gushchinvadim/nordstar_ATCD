# people/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Student, Staff


@receiver(post_save, sender=Student)
def create_student_user(sender, instance, created, **kwargs):
    """Создает Django User при ручном создании Student (например, через админку)"""
    if created and not instance.user:
        email = getattr(instance, 'email', '')

        if email and '@' in email:
            username = email.split('@')[0].strip().lower()
            password = email
        else:
            # Если email нет, используем фамилию. ID добавляется только сигналом как крайняя мера.
            username = f"student_{instance.surname.lower().replace(' ', '_')}" if instance.surname else f"student_{instance.id}"
            password = "Nordstar2026!"

        # ЗАЩИТА ОТ ДУБЛИКАТОВ: Если логин занят, добавляем ID студента.
        # Это гарантирует, что два студента с одинаковым email не получат один логин.
        if User.objects.filter(username=username).exists():
            username = f"{username}_{instance.id}"

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=instance.name,
            last_name=instance.surname
        )

        instance.user = user
        instance.save(update_fields=['user'])


@receiver(post_save, sender=Staff)
def create_staff_user(sender, instance, created, **kwargs):
    """Создает Django User при ручном создании Staff"""
    if created and not instance.user:
        email = getattr(instance, 'email', '')

        if email and '@' in email:
            username = email.split('@')[0].strip().lower()
            password = email
        else:
            name_part = instance.full_name.split()[0].lower() if instance.full_name else 'staff'
            username = f"staff_{name_part}"
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