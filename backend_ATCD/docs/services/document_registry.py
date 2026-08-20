    # docs/services/document_registry.py

from execution.models import ScheduleItem, Enrollment


class DocumentRegistry:
    """Реестр всех документов системы"""

    DOCUMENTS = {
        'enrollment_order': {
            'name': 'Приказ о зачислении',
            'icon': '📄',
            'view_name': 'docs:enrollment_order',
            'save_method': 'save_enrollment_order',
            'status': 'active',
            'visible_if': None,  # Всегда виден
        },
        'schedule': {
            'name': 'Расписание занятий',
            'icon': '📅',
            'view_name': 'docs:schedule',
            'save_method': 'save_schedule',
            'status': 'active',
            'visible_if': None,
        },
        'journal': {
            'name': 'Журнал подготовки',
            'icon': '📖',
            'view_name': 'docs:journal',
            'save_method': 'save_journal',
            'status': 'active',
            'visible_if': None,
        },
        'dismissal_ok': {
            'name': 'Приказ об окончании (ОК)',
            'icon': '✅',
            'view_name': 'docs:dismissal_ok',
            'save_method': 'save_dismissal_ok',
            'status': 'active',
            'visible_if': '_has_completed_students',  # Показываем только если есть завершившие
        },
        'dismissal_ot': {
            'name': 'Приказ об отчислении (ОТ)',
            'icon': '❌',
            'view_name': 'docs:dismissal_ot_list',
            'save_method': 'save_dismissal_ot',
            'status': 'active',
            'visible_if': '_has_dismissed_students',  # Показываем только если есть отчисленные
        },

        # === АСП: видны только если есть занятия ===
        'land_training_task': {
            'name': 'Задание на тренировку АСП Суша',
            'icon': '🔥',
            'view_name': 'docs:land_training_task',
            'save_method': 'save_land_training_task',
            'status': 'active',
            'visible_if': '_has_asp_land',
        },
        'water_training_task': {
            'name': 'Задание на тренировку АСП Вода',
            'icon': '💧',
            'view_name': 'docs:water_training_task',
            'save_method': 'save_water_training_task',
            'status': 'active',
            'visible_if': '_has_asp_water',
        },

        # === Сертификаты (универсальный, шаблон берется из модели Module) ===
        'certificate': {
            'name': 'Сертификат',
            'icon': '🎓',
            'view_name': 'docs:certificate_batch',  # Обновите view_name если нужно
            'save_method': 'save_certificate',
            'status': 'active',
            'visible_if': '_has_completed_students',  # Показываем только если есть завершившие
        },

        # --- ЗАГОТОВКИ для госотчетности ---
        'rauc_data': {
            'name': 'Данные для РАУЦ',
            'icon': '',
            'view_name': None,
            'save_method': None,  # Пока не реализовано
            'status': 'coming_soon',
            'visible_if': None,
        },
        'fis_frdo': {
            'name': 'Данные для ФИС ФРДО',
            'icon': '🇺',
            'view_name': None,
            'save_method': None,  # Пока не реализовано
            'status': 'coming_soon',
            'visible_if': None,
        },
    }

    @classmethod
    def get_all_documents(cls):
        return cls.DOCUMENTS

    @classmethod
    def get_active_documents(cls):
        return {k: v for k, v in cls.DOCUMENTS.items() if v['status'] == 'active'}

    @classmethod
    def get_documents_for_group(cls, group):
        """Возвращает документы, релевантные для конкретной группы"""
        result = {}
        for doc_key, doc_info in cls.DOCUMENTS.items():
            # Пропускаем неактивные
            if doc_info['status'] != 'active':
                continue

            # Проверяем условие видимости
            condition_method = doc_info.get('visible_if')
            if condition_method:
                # Вызываем метод проверки (например, _has_asp_land)
                checker = getattr(cls, condition_method, None)
                if checker and not checker(group):
                    continue  # Документ не показываем

            result[doc_key] = doc_info

        return result

    # === Методы проверки видимости ===

    @staticmethod
    def _has_asp_land(group):
        """Проверяет, есть ли в группе занятия АСП Суша"""
        return ScheduleItem.objects.filter(
            group=group,
            session_type='asp-l'
        ).exists()

    @staticmethod
    def _has_asp_water(group):
        """Проверяет, есть ли в группе занятия АСП Вода"""
        return ScheduleItem.objects.filter(
            group=group,
            session_type='asp-w'
        ).exists()

    @staticmethod
    def _has_completed_students(group):
        """Проверяет, есть ли в группе завершившие студенты"""
        return Enrollment.objects.filter(
            group=group,
            status='completed'
        ).exists()

    @staticmethod
    def _has_dismissed_students(group):
        """Проверяет, есть ли в группе отчисленные студенты"""
        return Enrollment.objects.filter(
            group=group,
            status='dismissed'
        ).exists()