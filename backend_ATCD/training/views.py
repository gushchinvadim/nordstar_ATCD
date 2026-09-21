# training/views.py
import os
import tempfile
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import FileResponse
from core.services.excel_import import import_instructor_qualifications
from training.models import InstructorQualification
import pandas as pd


@staff_member_required
def import_qualifications_view(request):
    """View для импорта допусков инструкторов из Excel"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')

        if not excel_file:
            messages.error(request, 'Файл не выбран!')
            return redirect('import_qualifications')

        # Проверяем расширение файла
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'Допустимы только файлы Excel (.xlsx, .xls)!')
            return redirect('import_qualifications')

        try:
            # Сохраняем файл во временную папку
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                for chunk in excel_file.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name

            # Запускаем импорт
            result = import_instructor_qualifications(tmp_file_path)

            # Удаляем временный файл
            os.unlink(tmp_file_path)

            # Показываем результаты
            messages.success(request, f'✅ Импорт завершен успешно!')
            messages.info(request, f'Создано допусков: {result["qualifications_created"]}')
            messages.info(request, f'Обновлено допусков: {result["qualifications_updated"]}')
            messages.info(request, f'Создано новых предметов: {result["subjects_created"]}')

            if result['subjects_updated'] > 0:
                messages.info(request, f'Обновлено названий предметов: {result["subjects_updated"]}')

            if result['warnings']:
                messages.warning(request, f'️ Предупреждений: {len(result["warnings"])}')
                for warning in result['warnings'][:10]:  # Показываем первые 10
                    messages.warning(request, f'  - {warning}')
                if len(result['warnings']) > 10:
                    messages.warning(request, f'  ... и еще {len(result["warnings"]) - 10} предупреждений')

            return redirect('admin:training_instructorqualification_changelist')

        except ValueError as e:
            messages.error(request, f' Ошибка валидации: {str(e)}')
        except Exception as e:
            messages.error(request, f'❌ Ошибка импорта: {str(e)}')

        return redirect('import_qualifications')

    return render(request, 'admin/import_qualifications.html')


@staff_member_required
def export_qualifications_template_view(request):
    """View для экспорта шаблона допусков"""
    return render(request, 'admin/export_qualifications_template.html')


@staff_member_required
def download_qualifications_template_view(request):
    """View для скачивания Excel-файла с текущими допусками"""
    try:
        # Получаем все допуски
        qualifications = InstructorQualification.objects.select_related('staff', 'subject').all()

        # Формируем данные
        data = []
        for q in qualifications:
            data.append({
                'full_name': q.staff.full_name,
                'subject_code': q.subject.code,
                'subject_name': q.subject.name,
                'device_type': q.device_type,
                'certificate_number': q.certificate_number or '',
                'issue_date': q.issue_date.strftime('%d.%m.%Y'),
                'validity_months': q.validity_months,
                'waiver_notes': q.waiver_notes or '',
            })

        # Создаем DataFrame
        df = pd.DataFrame(data)

        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file_path = tmp_file.name

        df.to_excel(tmp_file_path, index=False)

        # Отправляем файл
        response = FileResponse(
            open(tmp_file_path, 'rb'),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="instructor_qualifications_export.xlsx"'

        # Удаляем временный файл после отправки
        os.unlink(tmp_file_path)

        return response

    except Exception as e:
        messages.error(request, f'Ошибка экспорта: {str(e)}')
        return redirect('export_qualifications_template')