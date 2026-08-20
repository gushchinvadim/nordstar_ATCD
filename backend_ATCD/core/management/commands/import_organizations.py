# core/management/commands/import_organizations.py
from django.core.management.base import BaseCommand
from core.services.excel_organization_import import import_organizations


class Command(BaseCommand):
    help = 'Импорт локаций, организаций и аудиторий из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Путь к Excel файлу')

    def handle(self, *args, **options):
        file_path = options['file_path']

        try:
            result = import_organizations(file_path)

            self.stdout.write(self.style.SUCCESS('✅ Импорт организаций завершен!'))
            self.stdout.write(f'Создано локаций: {result["locations_created"]}')
            self.stdout.write(f'Обновлено локаций: {result["locations_updated"]}')
            self.stdout.write(f'Создано организаций: {result["organizations_created"]}')
            self.stdout.write(f'Обновлено организаций: {result["organizations_updated"]}')
            self.stdout.write(f'Создано аудиторий: {result["classrooms_created"]}')
            self.stdout.write(f'Обновлено аудиторий: {result["classrooms_updated"]}')

            if result['skipped']:
                self.stdout.write(self.style.WARNING(f'\n⚠️ Пропущено: {len(result["skipped"])}'))
                for detail in result['skipped']:
                    self.stdout.write(self.style.WARNING(f'  - {detail}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка импорта: {str(e)}'))