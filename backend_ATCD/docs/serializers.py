# docs/serializers.py
from rest_framework import serializers
from execution.models import ScheduleItem

class ScheduleItemUpdateSerializer(serializers.ModelSerializer):
    """Сериалайзер для частичного обновления занятия расписания"""
    class Meta:
        model = ScheduleItem
        fields = ['date', 'deadline', 'start_time', 'end_time', 'section', 'classroom', 'instructor', 'status', 'notes']
        extra_kwargs = {
            'date': {'required': False},
            'deadline': {'required': False, 'allow_null': True},
            'start_time': {'required': False, 'allow_null': True},
            'end_time': {'required': False, 'allow_null': True},
            'section': {'required': False},
            'classroom': {'required': False, 'allow_null': True},
            'instructor': {'required': False, 'allow_null': True},
            'status': {'required': False},
            'notes': {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        section = attrs.get('section')
        if section is not None:
            if section.stage.module_id != self.context['group'].module_id:
                raise serializers.ValidationError({'section': 'Раздел относится к другому модулю.'})
            if self.instance is None or section.pk != self.instance.section_id:
                attrs['session_type'] = section.detail or 'none'
                if self.instance is not None:
                    attrs['subsection'] = None

        instance = self.instance
        changed = instance is None or any(
            key in attrs and attrs[key] != getattr(instance, key) for key in ('instructor', 'section', 'date', 'deadline'))
        instructor = attrs.get('instructor', getattr(instance, 'instructor', None))
        if changed and instructor:
            from training.qualification_services import assignment_error
            from people.models import Staff
            from django.db import connection
            if connection.in_atomic_block:
                instructor = Staff.objects.select_for_update().get(pk=instructor.pk)
            target_section = attrs.get('section', getattr(instance, 'section', None))
            target_date = attrs.get('date', getattr(instance, 'date', None))
            deadline = attrs.get('deadline', getattr(instance, 'deadline', None))
            detail = attrs.get('session_type', getattr(instance, 'session_type', None))
            error = assignment_error(instructor, target_section, target_date, deadline if detail == 'sdo' else None)
            if error: raise serializers.ValidationError({'instructor': error})
        return attrs
