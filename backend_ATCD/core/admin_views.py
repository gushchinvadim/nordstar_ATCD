
from django.urls import path
from core.services.excel_import import import_training_program, import_staff, import_students
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from core.services.excel_group_import import import_group_enroll
from core.services.excel_organization_import import import_organizations


@staff_member_required
def import_organizations_view(request):
    """View для импорта организаций и аудиторий из Excel"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if excel_file:
            try:
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    for chunk in excel_file.chunks():
                        tmp_file.write(chunk)
                    tmp_path = tmp_file.name

                result = import_organizations(tmp_path)
                os.unlink(tmp_path)

                msg = f'✅ Импорт организаций завершен! Создано: {result["locations_created"]} локаций, {result["organizations_created"]} организаций, {result["classrooms_created"]} аудиторий'
                messages.success(request, msg)
                return redirect('admin:references_classroom_changelist')
            except Exception as e:
                messages.error(request, f'Ошибка при импорте: {str(e)}')
        else:
            messages.error(request, 'Файл не выбран!')

    return render(request, 'admin/import_organizations.html', {
        'title': 'Импорт организаций и аудиторий',
    })

@staff_member_required
def import_group_enroll_view(request):
    """View для импорта групп и зачислений из Excel"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if excel_file:
            try:
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    for chunk in excel_file.chunks():
                        tmp_file.write(chunk)
                    tmp_path = tmp_file.name

                result = import_group_enroll(tmp_path)
                os.unlink(tmp_path)

                msg = f'✅ Импорт групп и зачислений завершен! Создано: {result["groups_created"]}, Обновлено: {result["groups_updated"]}'
                messages.success(request, msg)
                return redirect('admin:execution_group_changelist')
            except Exception as e:
                messages.error(request, f'Ошибка при импорте: {str(e)}')
        else:
            messages.error(request, 'Файл не выбран!')

    return render(request, 'admin/import_group_enroll.html', {
        'title': 'Импорт групп и зачислений',
    })

@staff_member_required
def import_program_view(request):
    """View для импорта программы подготовки из Excel"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if excel_file:
            try:
                # Сохраняем файл временно
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    for chunk in excel_file.chunks():
                        tmp_file.write(chunk)
                    tmp_path = tmp_file.name

                # Запускаем импорт
                result = import_training_program(tmp_path)

                # Удаляем временный файл
                os.unlink(tmp_path)

                msg = f'✅ Импорт программы завершен! Создано: {result["courses_created"]}, Обновлено: {result["courses_updated"]}'
                messages.success(request, msg)
                return redirect('admin:training_course_changelist')
            except Exception as e:
                messages.error(request, f'Ошибка при импорте: {str(e)}')
        else:
            messages.error(request, 'Файл не выбран!')

    return render(request, 'admin/import_program.html', {
        'title': 'Импорт программы подготовки',
    })


@staff_member_required
def import_staff_view(request):
    """View для импорта персонала из Excel"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if excel_file:
            try:
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    for chunk in excel_file.chunks():
                        tmp_file.write(chunk)
                    tmp_path = tmp_file.name

                result = import_staff(tmp_path)

                os.unlink(tmp_path)

                msg = f'✅ Импорт персонала завершен! Создано: {result["staff_created"]}, Обновлено: {result["staff_updated"]}'
                messages.success(request, msg)
                return redirect('admin:people_staff_changelist')
            except Exception as e:
                messages.error(request, f'Ошибка при импорте: {str(e)}')
        else:
            messages.error(request, 'Файл не выбран!')

    return render(request, 'admin/import_staff.html', {
        'title': 'Импорт персонала',
    })


@staff_member_required
def import_students_view(request):
    """View для импорта слушателей из Excel"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if excel_file:
            try:
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    for chunk in excel_file.chunks():
                        tmp_file.write(chunk)
                    tmp_path = tmp_file.name

                result = import_students(tmp_path)

                os.unlink(tmp_path)

                msg = f'✅ Импорт слушателей завершен! Создано: {result["students_created"]}, Обновлено: {result["students_updated"]}'
                messages.success(request, msg)
                return redirect('admin:people_student_changelist')
            except Exception as e:
                messages.error(request, f'Ошибка при импорте: {str(e)}')
        else:
            messages.error(request, 'Файл не выбран!')

    return render(request, 'admin/import_students.html', {
        'title': 'Импорт слушателей',
    })