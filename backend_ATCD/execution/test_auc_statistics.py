from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from people.models import Staff, Student
from training.models import Course, Module
from .models import Group, Enrollment, Certificate


class AUCStatisticsTests(APITestCase):
    def setUp(self):
        self.director = get_user_model().objects.create_user(username='synthetic-statistics-director')
        self.staff = Staff.objects.create(user=self.director, full_name='Synthetic Director', tptitle=True)
        self.client.force_authenticate(self.director)
        self.url = reverse('execution:director_auc_statistics')
        self.start = date(2026, 11, 1); self.end = date(2026, 11, 30)
        self.params = {'date_from': str(self.start), 'date_to': str(self.end)}
        self.sequence = 0

    def module(self, direction='pilot', title='Synthetic module', code='SYNTHETIC'):
        return Module.objects.create(course=Course.objects.create(title='Synthetic course', frdo_template_type=direction),
            title=title, code=code, duration=2)

    def student(self, sex='M', active=True):
        return Student.objects.create(name='Synthetic', surname='Listener', sex=sex, is_active=active)

    def completion(self, module=None, student=None, day=None, status='completed', group_status='completed', actual_date=None):
        self.sequence += 1
        group = Group.objects.create(module=module or self.module(), assigned_number=f'SYNTHETIC-STAT-{self.sequence}',
            start_date=self.start, end_date=self.end, status=group_status, actual_completion_date=actual_date)
        return Enrollment.objects.create(group=group, student=student or self.student(), number_in_group=1,
            status=status, completed_at=self.start if day is None else day)

    def result(self):
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.status_code, 200, response.data)
        result = response.data
        summary = result['summary']
        self.assertEqual(summary['total'], summary['men'] + summary['women'] + summary['sex_not_specified'])
        self.assertEqual(summary['total'], sum(row['total'] for row in result['by_direction']))
        for direction in result['by_direction']:
            self.assertEqual(direction['total'], sum(row['total'] for row in direction['modules']))
        self.assertEqual(response['Cache-Control'], 'no-store')
        return result

    def test_each_module_completion_counts_even_for_same_person_repeating_a_module(self):
        male = self.student(); female = self.student('F')
        first = self.module(code='MODULE-ONE'); second = self.module(code='MODULE-TWO')
        self.completion(first, male)
        self.completion(first, male, day=self.end)
        self.completion(second, male)
        self.completion(first, female)
        result = self.result()
        self.assertEqual(result['counting_unit'], 'completed_module')
        self.assertEqual(result['summary']['total'], 4)
        self.assertEqual(result['summary']['men'], 3); self.assertEqual(result['summary']['women'], 1)
        pilot = next(row for row in result['by_direction'] if row['code'] == 'pilot')
        self.assertEqual({row['id']: row['total'] for row in pilot['modules']}, {first.pk: 3, second.pk: 1})

    def test_archiving_and_inactive_students_do_not_erase_training_facts(self):
        row = self.completion(student=self.student('F', active=False))
        before = self.result()
        row.group.status = 'archived'; row.group.archived_from_status = 'completed'; row.group.save()
        after = self.result()
        self.assertEqual(after['summary']['total'], before['summary']['total'])
        self.assertEqual(after['summary']['archived'], 1)
        self.assertEqual(after['by_direction'], before['by_direction'])

    def test_period_boundaries_are_inclusive_and_individual_date_takes_priority(self):
        self.completion(day=self.start)
        self.completion(day=self.end)
        self.completion(day=self.start - timedelta(days=1), actual_date=self.start)
        self.completion(day=self.end + timedelta(days=1), actual_date=self.end)
        self.completion(day=self.start, actual_date=self.end + timedelta(days=10))
        result = self.result()
        self.assertEqual(result['summary']['total'], 3)
        self.assertEqual(result['summary']['used_group_date'], 0)

    def test_missing_individual_date_uses_only_actual_group_date_not_plan_or_document_issue(self):
        fallback = self.completion(actual_date=self.end)
        missing = self.completion()
        Enrollment.objects.filter(pk__in=[fallback.pk, missing.pk]).update(completed_at=None)
        Certificate.objects.create(enrollment=missing, number='SYNTHETIC-UNDATED', total_hours=2,
            student_full_name='Synthetic Listener', module_title='Synthetic', issue_date=self.start)
        result = self.result()
        self.assertEqual(result['summary']['total'], 1)
        self.assertEqual(result['summary']['used_group_date'], 1)
        self.assertEqual(result['data_quality']['completed_without_date'], 1)

    def test_only_completed_enrollments_count_while_group_status_does_not_remove_existing_completion(self):
        for state in ('enrolled', 'in_progress', 'failed', 'dismissed', 'partial', 'absent'):
            self.completion(status=state)
        # Cancellation after a completed training does not rewrite the recorded completion.
        self.completion(group_status='cancelled')
        self.completion(group_status='in_progress')
        self.completion(status='enrolled', group_status='archived')
        self.assertEqual(self.result()['summary']['total'], 2)

    def test_module_grouping_separates_all_four_directions_and_distinct_module_ids(self):
        for direction in ('flight_attendant', 'pilot', 'engineer', 'representative'):
            self.completion(module=self.module(direction, title='Same module title', code='SAME-CODE'))
        self.completion(module=self.module('pilot', title='Same module title', code='SAME-CODE'))
        result = self.result()
        directions = {row['code']: row for row in result['by_direction']}
        self.assertEqual(set(directions), {'flight_attendant', 'pilot', 'engineer', 'representative'})
        self.assertEqual(directions['pilot']['total'], 2)
        self.assertEqual(len(directions['pilot']['modules']), 2)
        self.assertEqual(result['summary']['total'], 5)

    def test_unknown_gender_is_reported_and_legacy_single_character_values_are_supported(self):
        for sex in ('M', 'm', 'М', 'F', 'f', 'Ж', ''):
            self.completion(student=self.student(sex))
        summary = self.result()['summary']
        self.assertEqual(summary['men'], 3); self.assertEqual(summary['women'], 3)
        self.assertEqual(summary['sex_not_specified'], 1)

    def test_additional_certificates_do_not_multiply_training_counts(self):
        row = self.completion()
        for number in ('SYNTHETIC-FIRST', 'SYNTHETIC-SECOND'):
            Certificate.objects.create(enrollment=row, number=number, total_hours=2,
                student_full_name='Synthetic Listener', module_title='Synthetic', issue_date=self.start)
        self.assertEqual(self.result()['summary']['total'], 1)

    def test_director_has_auc_wide_aggregates_not_only_personally_assigned_groups(self):
        other = get_user_model().objects.create_user(username='synthetic-other-director')
        other_staff = Staff.objects.create(user=other, full_name='Other Director', tptitle=True)
        row = self.completion(); row.group.director = other_staff; row.group.save()
        self.assertEqual(self.result()['summary']['total'], 1)

    def test_invalid_periods_and_unauthorized_access_are_rejected(self):
        for params in ({}, {'date_from': str(self.start)}, {'date_from': 'bad', 'date_to': str(self.end)},
            {'date_from': str(self.end), 'date_to': str(self.start)}):
            self.assertEqual(self.client.get(self.url, params).status_code, 400)
        ordinary = get_user_model().objects.create_user(username='synthetic-ordinary')
        self.client.force_authenticate(ordinary)
        self.assertEqual(self.client.get(self.url, self.params).status_code, 403)
        Staff.objects.create(user=ordinary, full_name='Methodist', fptitle=True)
        self.client.force_authenticate(get_user_model().objects.get(pk=ordinary.pk))
        self.assertEqual(self.client.get(self.url, self.params).status_code, 403)
        self.staff.is_active = False; self.staff.save()
        self.client.force_authenticate(get_user_model().objects.get(pk=self.director.pk))
        self.assertEqual(self.client.get(self.url, self.params).status_code, 403)
        root = get_user_model().objects.create_superuser(username='synthetic-stats-admin', password='Synthetic-42')
        self.client.force_authenticate(root)
        self.assertEqual(self.client.get(self.url, self.params).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.params).status_code, 405)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url, self.params).status_code, 401)

    def test_empty_period_returns_zeroes_and_all_directions(self):
        result = self.result()
        self.assertEqual(result['summary']['total'], 0)
        self.assertEqual(len(result['by_direction']), 4)
        self.assertEqual(result['data_quality']['completed_without_date'], 0)

    def test_unrecognized_direction_is_not_silently_lost(self):
        for _ in range(2):
            self.completion(module=self.module('unclassified'))
        result = self.result()
        self.assertEqual(result['summary']['total'], 2)
        self.assertEqual(result['data_quality']['unclassified_in_period'], 2)
        self.assertEqual(next(row for row in result['by_direction'] if row['code'] == 'unclassified')['total'], 2)
