from django.core.management.base import BaseCommand
from core.services.excel_import import import_students


class Command(BaseCommand):
    help = 'Импорт студентов из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Путь к Excel файлу')

    def handle(self, *args, **options):
        file_path = options['file_path']

        try:
            result = import_students(file_path)

            self.stdout.write(self.style.SUCCESS('Импорт студентов завершен успешно!'))
            self.stdout.write(f'Создано студентов: {result["students_created"]}')
            self.stdout.write(f'Обновлено студентов: {result["students_updated"]}')
            self.stdout.write(f'Создано профессий: {result["professions"]}')
            self.stdout.write(f'Создано гражданств: {result["citizenships"]}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка импорта: {str(e)}'))