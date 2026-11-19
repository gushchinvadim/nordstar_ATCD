"""Shared archival operation. Call while holding the group row lock."""
import shutil
from pathlib import Path
from django.conf import settings
from docs.services.document_storage import DocumentStorageService
from .models import Group


class ArchiveError(ValueError):
    pass


def remove_generated_files(group):
    folder = Path(DocumentStorageService(group).base_path)
    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        relative = folder.resolve().relative_to(media_root)
        if len(relative.parts) < 5 or relative.parts[:1] != ('documents',):
            raise ValueError()
        current = folder
        while current != Path(settings.MEDIA_ROOT) and current != current.parent:
            if current.is_symlink():
                raise ValueError()
            current = current.parent
        for other in Group.objects.filter(start_date__year=group.start_date.year).exclude(pk=group.pk).select_related('module'):
            if Path(DocumentStorageService(other).base_path).resolve() == folder.resolve():
                raise ArchiveError('Папка документов совпадает с другой группой. Требуется проверка администратором.')
        deleted = folder.exists()
        if deleted:
            shutil.rmtree(folder)
    except ArchiveError:
        raise
    except (OSError, ValueError):
        raise ArchiveError('Не удалось безопасно удалить файлы группы. Статус не изменён; обратитесь к администратору.')
    return deleted


def archive_training_group(group, user, audit):
    previous = group.status
    deleted = remove_generated_files(group)
    group.archived_from_status = previous
    group.status = 'archived'
    group.save(update_fields=['status', 'archived_from_status'])
    audit(user, group, {'operation': 'group_archived', 'previous_status': previous,
        'generated_files_removed': deleted})
    return deleted
