from django.core.management.base import BaseCommand
from execution.models import Group
from docs.services.document_storage import DocumentStorageService


class Command(BaseCommand):
    help = 'Сохраняет все документы группы в папку media/documents/'

    def add_arguments(self, parser):
        parser.add_argument('group_number', type=str, help='Номер группы (например, 001.2026)')

    def handle(self, *args, **options):
        group_number = options['group_number']

        try:
            group = Group.objects.get(assigned_number=group_number)
        except Group.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Группа {group_number} не найдена'))
            return

        self.stdout.write(f'📁 Сохранение документов для группы {group.assigned_number}...')

        service = DocumentStorageService(group)
        results = service.save_all_documents()

        self.stdout.write(self.style.SUCCESS('\n✅ Документы сохранены:'))

        if results['enrollment_order'] and not results['enrollment_order'].startswith('Ошибка'):
            html_path, pdf_path = results['enrollment_order']
            self.stdout.write(f'   Приказ о зачислении:')
            self.stdout.write(f'     HTML: {html_path}')
            self.stdout.write(f'     PDF:  {pdf_path}')

        if results['schedule'] and not results['schedule'].startswith('Ошибка'):
            html_path, pdf_path = results['schedule']
            self.stdout.write(f'  📅 Расписание:')
            self.stdout.write(f'     HTML: {html_path}')
            self.stdout.write(f'     PDF:  {pdf_path}')