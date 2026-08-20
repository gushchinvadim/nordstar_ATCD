# core/management/commands/import_program.py
from django.core.management.base import BaseCommand
from core.services.excel_import import import_training_program


class Command(BaseCommand):
    help = 'Импорт программы подготовки из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Путь к Excel файлу')

    def handle(self, *args, **options):
        file_path = options['file_path']

        try:
            result = import_training_program(file_path)

            self.stdout.write(self.style.SUCCESS('Импорт программы завершен успешно!'))
            self.stdout.write(f'Создано программ: {result["courses_created"]}')
            self.stdout.write(f'Обновлено программ: {result["courses_updated"]}')
            self.stdout.write(f'Создано модулей: {result["modules"]}')
            self.stdout.write(f'Создано этапов: {result["stages"]}')
            self.stdout.write(f'Создано разделов: {result["sections"]}')
            self.stdout.write(f'Создано подразделов: {result["subsections"]}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка импорта: {str(e)}'))