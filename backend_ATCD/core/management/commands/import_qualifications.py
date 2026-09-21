# core/management/commands/import_qualifications.py
from django.core.management.base import BaseCommand
from core.services.excel_import import import_instructor_qualifications


class Command(BaseCommand):
    help = 'Импорт допусков инструкторов из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Путь к Excel файлу с допусками')

    def handle(self, *args, **options):
        file_path = options['file_path']

        try:
            result = import_instructor_qualifications(file_path)

            self.stdout.write(self.style.SUCCESS('Импорт допусков инструкторов завершен успешно!'))
            self.stdout.write(f'Создано допусков: {result["qualifications_created"]}')
            self.stdout.write(f'Обновлено допусков: {result["qualifications_updated"]}')
            self.stdout.write(f'Создано новых предметов: {result["subjects_created"]}')
            self.stdout.write(f'Обновлено названий предметов: {result["subjects_updated"]}')

            if result['warnings']:
                self.stdout.write(self.style.WARNING(f'\n️ Предупреждений: {len(result["warnings"])}'))
                for warning in result['warnings']:
                    self.stdout.write(self.style.WARNING(f'  - {warning}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка импорта: {str(e)}'))