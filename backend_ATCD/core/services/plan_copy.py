from execution.models import Group, GroupModule, GroupStage, GroupSection
from training.models import Module, Stage, Section


def copy_module_plan_to_group(group, module=None):
    """
    Копирует структуру модуля в группу.
    Если module не указан, берется из group.module.
    """
    if not module:
        module = group.module

    if not module:
        raise ValueError("У группы не выбран модуль")

    # Создаем GroupModule
    group_module, created = GroupModule.objects.get_or_create(
        group=group,
        module=module,
        defaults={
            'start_date': group.start_date,
            'end_date': group.end_date,
        }
    )

    if not created:
        # Если уже существует, очищаем старые данные
        group_module.group_stages.all().delete()

    # Копируем этапы
    stages = Stage.objects.filter(module=module).order_by('order')
    for stage in stages:
        group_stage = GroupStage.objects.create(
            group_module=group_module,
            stage=stage,
        )

        # Копируем разделы
        sections = Section.objects.filter(stage=stage).order_by('order')
        for section in sections:
            GroupSection.objects.create(
                group_stage=group_stage,
                section=section,
                duration_hours=section.duration_hours,
            )

    return group_module


def copy_all_modules_to_group(group):
    """Копирует все модули из программы в группу"""
    course = group.module.course if group.module else None
    if not course:
        raise ValueError("У группы не выбран модуль или программа")

    modules = Module.objects.filter(course=course).order_by('mod_id')
    group_modules = []

    for module in modules:
        gm = copy_module_plan_to_group(group, module)
        group_modules.append(gm)

    return group_modules