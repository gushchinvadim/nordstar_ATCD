from django.core.management.base import BaseCommand
from core.services.excel_group_import import import_group_enroll


class Command(BaseCommand):
    help = 'Импорт групп и зачислений из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Путь к Excel файлу')

    def handle(self, *args, **options):
        file_path = options['file_path']

        try:
            result = import_group_enroll(file_path)

            self.stdout.write(self.style.SUCCESS('✅ Импорт групп и зачислений завершен!'))
            self.stdout.write(f'Создано групп: {result["groups_created"]}')
            self.stdout.write(f'Обновлено групп: {result["groups_updated"]}')
            self.stdout.write(f'Создано зачислений: {result["enrollments_created"]}')
            self.stdout.write(f'Обновлено зачислений: {result["enrollments_updated"]}')

            if result['skipped']:
                self.stdout.write(self.style.WARNING(f'\n⚠️ Пропущено строк: {len(result["skipped"])}'))
                for detail in result['skipped']:
                    self.stdout.write(self.style.WARNING(f'  - {detail}'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка импорта: {str(e)}'))