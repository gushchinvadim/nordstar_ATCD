# execution/management/commands/cleanup_media.py
import os
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from execution.models import Group


class Command(BaseCommand):
    help = 'Очистка медиа-файлов старых групп'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=180,
            help='Удалять файлы групп старше N дней (по умолчанию 180)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, но не удалять'
        )
        parser.add_argument(
            '--keep-reports',
            action='store_true',
            help='Сохранить папку reports (РАУЦ/ФРДО) даже при очистке'
        )
        parser.add_argument(
            '--group-ids',
            type=int,
            nargs='+',
            help='Очистить только указанные группы по ID (например: --group-ids 1 2 3)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод всех операций'
        )

    def find_group_folder(self, group, year):
        """
        Находит папку группы сканированием всех подпапок модулей.
        Возвращает путь или None.
        """
        groups_base = os.path.join(settings.MEDIA_ROOT, 'documents', year, 'groups')

        if not os.path.exists(groups_base):
            return None

        # Сканируем все подпапки модулей
        for module_folder in os.listdir(groups_base):
            module_path = os.path.join(groups_base, module_folder)
            if not os.path.isdir(module_path):
                continue

            # Ищем папку с номером группы
            group_path = os.path.join(module_path, group.assigned_number)
            if os.path.exists(group_path):
                return group_path

        return None

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        keep_reports = options['keep_reports']
        group_ids = options['group_ids']
        verbose = options['verbose']

        cutoff_date = timezone.now() - timedelta(days=days)

        # Если указаны конкретные ID групп
        if group_ids:
            groups = Group.objects.filter(id__in=group_ids)
            self.stdout.write(f'Очистка {len(groups)} выбранных групп по ID')
        else:
            # Иначе ищем старые завершённые группы
            groups = Group.objects.filter(
                status='completed',
                end_date__lt=cutoff_date
            )
            self.stdout.write(f'Найдено {len(groups)} групп старше {days} дней (до {cutoff_date.date()})')

        if not groups.exists():
            self.stdout.write(self.style.WARNING('Нет групп для очистки'))
            if verbose:
                all_groups = Group.objects.all()[:10]
                self.stdout.write('\nПервые 10 групп в БД:')
                for g in all_groups:
                    self.stdout.write(
                        f'  ID={g.id}, status={g.status}, end_date={g.end_date}, assigned_number={g.assigned_number}')
            return

        total_size = 0
        total_files = 0
        deleted_files = 0

        for group in groups:
            year = str(group.start_date.year) if group.start_date else 'unknown'

            # Ищем папку группы сканированием
            group_folder = self.find_group_folder(group, year)

            if not group_folder:
                self.stdout.write(
                    self.style.WARNING(f'Группа {group.assigned_number} (ID={group.id}): папка не найдена'))
                continue

            self.stdout.write(f'\nГруппа {group.assigned_number} (ID={group.id}): {group_folder}')

            # Считаем размер и файлы
            for root, dirs, files in os.walk(group_folder):
                # Если keep_reports=True, пропускаем папку reports
                if keep_reports and 'reports' in root:
                    if verbose:
                        self.stdout.write(f'  Пропускаем reports: {root}')
                    continue

                for file in files:
                    filepath = os.path.join(root, file)
                    file_size = os.path.getsize(filepath)
                    total_size += file_size
                    total_files += 1

                    if verbose:
                        self.stdout.write(f'  Файл: {filepath} ({file_size} байт)')

                    if not dry_run:
                        os.remove(filepath)
                        deleted_files += 1

            # Удаляем пустые папки
            if not dry_run:
                for root, dirs, files in os.walk(group_folder, topdown=False):
                    if not files and not dirs:
                        try:
                            os.rmdir(root)
                            if verbose:
                                self.stdout.write(f'  Удалена пустая папка: {root}')
                        except OSError as e:
                            self.stdout.write(self.style.WARNING(f'  Не удалось удалить папку {root}: {e}'))

        # Выводим результат
        size_mb = total_size / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 50}'))
        self.stdout.write(self.style.SUCCESS(f'Найдено файлов: {total_files}'))
        self.stdout.write(self.style.SUCCESS(f'Общий размер: {size_mb:.2f} MB'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: файлы не удалены'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Удалено файлов: {deleted_files}'))