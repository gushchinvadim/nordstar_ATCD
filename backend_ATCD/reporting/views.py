# reporting/views.py
import os
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST

from execution.models import Group
from reporting.services.frdo_export import FRDOExportService
from reporting.services.rauc_export import RAUCExportService


@staff_member_required
@require_POST
def save_rauc_excel(request, group_id):
    """AJAX: Сохраняет Excel РАУЦ в папку группы и БД"""
    group = get_object_or_404(Group, id=group_id)
    try:
        service = RAUCExportService(group, user=request.user)
        filepath, rel_path, errors = service.generate_excel()

        # Сохраняем в БД с указанием формата
        report = service.save_to_database(excel_path=filepath, file_format='excel')

        return JsonResponse({
            'success': True,
            'file_path': rel_path,
            'report_id': report.id,
            'warnings': [str(e) for e in errors] if errors else []
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def save_rauc_xml(request, group_id):
    """AJAX: Сохраняет XML РАУЦ в папку группы и БД"""
    group = get_object_or_404(Group, id=group_id)
    try:
        service = RAUCExportService(group, user=request.user)
        filepath, rel_path, errors = service.generate_xml()

        # Сохраняем в БД с указанием формата
        report = service.save_to_database(xml_path=filepath, file_format='xml')

        return JsonResponse({
            'success': True,
            'file_path': rel_path,
            'report_id': report.id,
            'warnings': [str(e) for e in errors] if errors else []
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@staff_member_required
def preview_rauc_xml(request, file_path):
    """Предварительный просмотр XML файла в браузере"""
    if not file_path.startswith('documents/'):
        raise Http404("Недопустимый путь к файлу")

    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    if not os.path.exists(full_path):
        raise Http404("Файл не найден")

    response = FileResponse(
        open(full_path, 'rb'),
        content_type='application/xml',
        as_attachment=False
    )
    return response


@staff_member_required
def download_rauc_file(request, file_path):
    """Скачивание файла РАУЦ (Excel или XML)"""
    if not file_path.startswith('documents/'):
        raise Http404("Недопустимый путь к файлу")

    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    if not os.path.exists(full_path):
        raise Http404("Файл не найден")

    filename = os.path.basename(file_path)
    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if filename.endswith(
        '.xlsx') else 'application/xml'

    response = FileResponse(
        open(full_path, 'rb'),
        content_type=content_type,
        as_attachment=True,
        filename=filename
    )
    return response


@staff_member_required
@require_POST
def save_frdo_excel(request, group_id):
    """AJAX: Сохраняет Excel ФРДО в папку группы и БД"""
    group = get_object_or_404(Group, id=group_id)
    try:
        service = FRDOExportService(group, user=request.user)
        filepath, rel_path, errors = service.generate_excel()

        # Сохраняем в БД
        report = service.save_to_database(excel_path=filepath, file_format='excel')

        return JsonResponse({
            'success': True,
            'file_path': rel_path,
            'report_id': report.id,
            'warnings': [str(e) for e in errors] if errors else []
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def download_frdo_file(request, file_path):
    """Скачивание файла ФРДО"""
    if not file_path.startswith('documents/'):
        raise Http404("Недопустимый путь к файлу")

    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    if not os.path.exists(full_path):
        raise Http404("Файл не найден")

    filename = os.path.basename(file_path)

    response = FileResponse(
        open(full_path, 'rb'),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        filename=filename
    )
    return response