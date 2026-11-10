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

        return attrs
