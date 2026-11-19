"""Internal AUC statistics: completed enrollments are training events, not unique people."""
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from training.models import Course
from .models import Enrollment

MALE_VALUES = ('M', 'm', 'М', 'м')
FEMALE_VALUES = ('F', 'f', 'Ж', 'ж')


def completion_rows():
    # Do not filter group status or current student activity: archiving must not erase training facts.
    # Never substitute planned end dates or later document issue dates.
    return Enrollment.objects.filter(status='completed').annotate(
        statistics_date=Coalesce('completed_at', 'group__actual_completion_date'))


def build_auc_statistics(date_from, date_to, funding_source=None, payer_organization=None):
    completed = completion_rows()
    if funding_source and funding_source != 'all': completed = completed.filter(funding_source=funding_source)
    if payer_organization is not None: completed = completed.filter(payer_organization=payer_organization)
    funding_totals = {code: 0 for code, title in Enrollment.FUNDING_CHOICES}
    companies = {}
    module_maps = {}
    rows = completed.filter(statistics_date__range=(date_from, date_to))
    summary = dict.fromkeys(('total', 'men', 'women', 'archived', 'used_group_date'), 0)
    by_direction = {code: {'code': code, 'title': title, 'total': 0, 'modules': [], **dict.fromkeys(funding_totals, 0)}
        for code, title in Course.FRDO_TEMPLATE_CHOICES}
    groups = rows.order_by().values('group__module__course__frdo_template_type',
        'group__module_id', 'group__module__code', 'group__module__title', 'funding_source',
        'payer_organization_id', 'payer_organization__company_name').annotate(total=Count('pk'),
        men=Count('pk', filter=Q(student__sex__in=MALE_VALUES)),
        women=Count('pk', filter=Q(student__sex__in=FEMALE_VALUES)),
        archived=Count('pk', filter=Q(group__status='archived')),
        used_group_date=Count('pk', filter=Q(completed_at__isnull=True))).order_by(
            'group__module__code', 'group__module__title', 'group__module_id')
    known_codes = set(by_direction)
    unclassified = 0
    # Derive both blocks from the same SQL result so concurrent completions cannot split their totals.
    for row in groups:
        for key in summary:
            summary[key] += row[key]
        code = row['group__module__course__frdo_template_type']
        if code not in known_codes:
            unclassified += row['total']
            code = 'unclassified'
            if code not in by_direction:
                by_direction[code] = {'code': code, 'title': 'Направление не задано', 'total': 0, 'modules': [], **dict.fromkeys(funding_totals, 0)}
        category = by_direction[code]
        category['total'] += row['total']
        source = row['funding_source'] if row['funding_source'] in funding_totals else 'unspecified'
        funding_totals[source] += row['total']
        category[source] += row['total']
        key = (code, row['group__module_id'])
        if key not in module_maps:
            module_maps[key] = {'id': row['group__module_id'], 'code': row['group__module__code'],
                'title': row['group__module__title'], 'total': 0, **dict.fromkeys(funding_totals, 0)}
            category['modules'].append(module_maps[key])
        module_maps[key]['total'] += row['total']
        module_maps[key][source] += row['total']
        if source in ('company_internal', 'company_external'):
            payer_id = row['payer_organization_id']
            if payer_id not in companies:
                companies[payer_id] = {'id': payer_id, 'name': row['payer_organization__company_name'] or 'Компания не указана',
                    'total': 0, 'company_internal': 0, 'company_external': 0}
            companies[payer_id]['total'] += row['total']
            companies[payer_id][source] += row['total']
    summary['sex_not_specified'] = summary['total'] - summary['men'] - summary['women']
    return {'period': {'date_from': date_from, 'date_to': date_to},
        'filters': {'funding_source': funding_source or 'all', 'payer_organization': payer_organization.pk if payer_organization else None, 'payer_name': payer_organization.company_name if payer_organization else None},
        'funding': {'by_source': [{'code': code, 'title': title, 'total': funding_totals[code]} for code, title in Enrollment.FUNDING_CHOICES],
            'companies': sorted(companies.values(), key=lambda row: row['name'])},
        'counting_unit': 'completed_module', 'summary': summary, 'by_direction': list(by_direction.values()),
        'data_quality': {'completed_without_date': completed.filter(statistics_date__isnull=True).count(),
            'unclassified_in_period': unclassified}}
