from django.core.management.base import BaseCommand
from core.services.excel_import import import_staff


class Command(BaseCommand):
    help = 'Импорт персонала из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Путь к Excel файлу')

    def handle(self, *args, **options):
        file_path = options['file_path']

        try:
            result = import_staff(file_path)

            self.stdout.write(self.style.SUCCESS('Импорт персонала завершен успешно!'))
            self.stdout.write(f'Создано сотрудников: {result["staff_created"]}')
            self.stdout.write(f'Обновлено сотрудников: {result["staff_updated"]}')
            self.stdout.write(f'Создано должностей: {result["positions"]}')
            self.stdout.write(f'Создано организаций: {result["organizations"]}')
            self.stdout.write(f'Создано местоположений: {result["locations"]}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка импорта: {str(e)}'))