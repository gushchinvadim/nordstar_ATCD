# execution/serializers.py
from .models import ScheduleItem, Assessment, Enrollment, ComplianceLog
from rest_framework import serializers
from .models import ScheduleItem


class InstructorScheduleSerializer(serializers.ModelSerializer):
    group_id = serializers.SerializerMethodField()
    group_number = serializers.SerializerMethodField()
    section_title = serializers.SerializerMethodField()
    subsection_title = serializers.SerializerMethodField()
    classroom_name = serializers.SerializerMethodField()
    instructor_name = serializers.SerializerMethodField()
    completion_signature = serializers.CharField(read_only=True)
    requires_grading = serializers.SerializerMethodField()

    def get_group_id(self, obj):
        return obj.group.id if obj.group else None

    def get_group_number(self, obj):
        return obj.group.assigned_number if obj.group else None

    def get_section_title(self, obj):
        return obj.section.title if obj.section else None

    def get_subsection_title(self, obj):
        return obj.subsection.title if obj.subsection else None

    def get_classroom_name(self, obj):
        """Используем __str__ модели Classroom для красивого отображения"""
        if not obj.classroom:
            return None
        return str(obj.classroom)  # Вернет "Тренажерный зал №2 (Аудитория 305)"

    def get_instructor_name(self, obj):
        return obj.instructor.full_name if obj.instructor else None

    def get_requires_grading(self, obj):
        """Проверяет, требует ли раздел этого занятия выставления оценки"""
        if obj.section:
            # Если тип оценки не 'none' (например, 'numeric' или 'binary'), возвращаем True
            return obj.section.grade_type != 'none'
        return False

    class Meta:
        model = ScheduleItem
        fields = [
            'id', 'group_id', 'group_number', 'section_title', 'subsection_title',
            'date', 'start_time', 'end_time', 'classroom_name',
            'instructor_name', 'session_type', 'status',
            'is_completed', 'completion_signature',
            'requires_grading',
        ]


class AssessmentSerializer(serializers.ModelSerializer):
    section_title = serializers.CharField(source='section.title', read_only=True)
    section_grade_type = serializers.CharField(source='section.grade_type', read_only=True)

    class Meta:
        model = Assessment
        fields = [
            'id', 'section', 'section_title', 'section_grade_type',
            'score', 'passed', 'attempt_number', 'notes'
        ]


class InstructorGradesSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    assessments = AssessmentSerializer(many=True, read_only=True)
    editable_sections = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = ['id', 'number_in_group', 'student_name', 'assessments', 'editable_sections']

    def get_editable_sections(self, obj):
        """Возвращает список ID разделов, которые может редактировать этот преподаватель"""
        return self.context.get('instructor_sections', [])


class StudentScheduleSerializer(serializers.ModelSerializer):
    group_number = serializers.CharField(source='group.assigned_number', read_only=True)
    section_title = serializers.CharField(source='section.title', read_only=True)
    subsection_title = serializers.CharField(source='subsection.title', read_only=True, default=None)
    classroom_name = serializers.SerializerMethodField()
    instructor_name = serializers.SerializerMethodField()

    # Проверяем, совершал ли студент уже действия
    has_attended = serializers.SerializerMethodField()
    has_safety_ack = serializers.SerializerMethodField()

    def get_classroom_name(self, obj):
        return str(obj.classroom) if obj.classroom else None

    def get_instructor_name(self, obj):
        return obj.instructor.full_name if obj.instructor else None

    def get_has_attended(self, obj):
        """Проверяем, подтвердил ли студент присутствие на этом занятии"""
        student = self.context.get('student')
        if not student:
            return False
        return ComplianceLog.objects.filter(
            schedule_item=obj,
            student=student,
            action_type='student_attendance_confirmed'
        ).exists()

    def get_has_safety_ack(self, obj):
        """Проверяем, ознакомился ли студент с ТБ (один раз на весь курс)"""
        student = self.context.get('student')
        if not student:
            return False
        return ComplianceLog.objects.filter(
            schedule_item__group=obj.group,
            student=student,
            action_type='student_safety_ack'
        ).exists()

    class Meta:
        model = ScheduleItem
        fields = [
            'id', 'group_number', 'section_title', 'subsection_title',
            'date', 'start_time', 'end_time', 'classroom_name',
            'instructor_name', 'session_type', 'status',
            'has_attended', 'has_safety_ack'
        ]

class DirectorScheduleSerializer(serializers.ModelSerializer):
    group_number = serializers.CharField(source='group.assigned_number', read_only=True)
    section_title = serializers.CharField(source='section.title', read_only=True)
    subsection_title = serializers.CharField(source='subsection.title', read_only=True, default=None)
    classroom_name = serializers.SerializerMethodField()
    instructor_name = serializers.SerializerMethodField()

    def get_classroom_name(self, obj):
        return str(obj.classroom) if obj.classroom else None

    def get_instructor_name(self, obj):
        return obj.instructor.full_name if obj.instructor else None

    class Meta:
        model = ScheduleItem
        fields = [
            'id', 'group_number', 'section_title', 'subsection_title',
            'date', 'start_time', 'end_time', 'classroom_name',
            'instructor_name', 'session_type', 'status'
        ]
