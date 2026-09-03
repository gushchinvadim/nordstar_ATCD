# core/management/commands/generate_schedule.py
from django.core.management.base import BaseCommand
from core.services.schedule_generator import generate_schedule_for_group


class Command(BaseCommand):
    help = 'Генерирует расписание для всех активных групп'

    def add_arguments(self, parser):
        parser.add_argument(
            '--offset',
            type=int,
            default=0,
            help='Сдвиг даты начала в днях (для тестирования)'
        )

    def handle(self, *args, **options):
        offset = options['offset']

        try:
            results = generate_schedule_for_group(start_date_offset=offset)

            self.stdout.write(self.style.SUCCESS('✅ Генерация расписания завершена!'))

            for group_number, count in results.items():
                if isinstance(count, int):
                    self.stdout.write(f'  Группа {group_number}: создано {count} занятий')
                else:
                    self.stdout.write(self.style.ERROR(f'  Группа {group_number}: {count}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f' Ошибка: {str(e)}'))