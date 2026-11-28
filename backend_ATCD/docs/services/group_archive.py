import os
import re
from pathlib import Path
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.http import FileResponse, Http404

from docs.services.document_storage import DocumentStorageService


def make_safe_filename(text):
    """Транслитерация + замена всех спецсимволов на подчёркивания"""
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    # Транслитерируем
    text = ''.join(mapping.get(c, c) for c in text)
    # Заменяем всё, что не буква/цифра, на подчёркивание
    text = re.sub(r'[^a-zA-Z0-9]', '_', text)
    # Убираем множественные подчёркивания
    text = re.sub(r'_+', '_', text).strip('_')
    return text


def group_archive_response(group):
    """Собрать сохранённые документы и отчёты группы в один ZIP."""
    folder = Path(DocumentStorageService(group).base_path)
    media = Path(settings.MEDIA_ROOT)
    expected_folder = media.resolve() / folder.relative_to(media)
    if folder.resolve() != expected_folder or not folder.is_dir():
        raise Http404('У группы пока нет сохранённых документов.')

    archive = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    try:
        has_files = False
        with ZipFile(archive, 'w', ZIP_DEFLATED) as output:
            for directory, folders, names in os.walk(folder):
                folders.sort()
                for name in sorted(names):
                    path = Path(directory) / name
                    if path.is_symlink() or not path.is_file():
                        continue
                    try:
                        output.write(path, path.relative_to(folder).as_posix())
                    except FileNotFoundError:
                        # A document may be removed by a concurrent update.
                        continue
                    has_files = True
        if not has_files:
            raise Http404('У группы пока нет сохранённых документов.')
        archive.seek(0)
        safe_name = make_safe_filename(group.assigned_number) or str(group.pk)
        response = FileResponse(archive, as_attachment=True, filename=f'group_{safe_name}.zip',
                                content_type='application/zip')
        response['Cache-Control'] = 'private, no-store'
        return response
    except Exception:
        archive.close()
        raise
