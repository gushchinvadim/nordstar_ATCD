from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from people.models import Student, Staff


class Command(BaseCommand):
    help = 'Создает Django-пользователей для всех существующих студентов и преподавателей без User'

    def handle(self, *args, **kwargs):
        created_count = 0

        # Обработка преподавателей
        self.stdout.write(' Обработка преподавателей...')
        for staff in Staff.objects.filter(user__isnull=True):
            email = staff.email or ''
            if email and '@' in email:
                username = email.split('@')[0].strip().lower()
                password = email
            else:
                username = f"staff_{staff.id}"
                password = "Nordstar2026!"

            if User.objects.filter(username=username).exists():
                username = f"{username}_{staff.id}"

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=staff.full_name.split()[0] if staff.full_name else '',
                last_name=staff.full_name.split()[-1] if staff.full_name else ''
            )
            staff.user = user
            staff.save(update_fields=['user'])
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f'  ✅ {staff.full_name} → {username}'))

        # Обработка студентов
        self.stdout.write('\n🔍 Обработка студентов...')
        for student in Student.objects.filter(user__isnull=True):
            email = student.email or ''
            if email and '@' in email:
                username = email.split('@')[0].strip().lower()
                password = email
            else:
                username = f"student_{student.id}"
                password = "Nordstar2026!"

            if User.objects.filter(username=username).exists():
                username = f"{username}_{student.id}"

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=student.name,
                last_name=student.surname
            )
            student.user = user
            student.save(update_fields=['user'])
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f'\n Готово! Создано аккаунтов: {created_count}'))