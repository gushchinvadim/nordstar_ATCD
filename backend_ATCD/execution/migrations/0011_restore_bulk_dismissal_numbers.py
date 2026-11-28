from django.db import migrations


def restore_order_numbers(apps, schema_editor):
    Enrollment = apps.get_model('execution', 'Enrollment')
    enrollments = Enrollment.objects.using(schema_editor.connection.alias)
    affected = enrollments.filter(
        status='dismissed',
        dismissal_reason='Неуспеваемость (не сданы все оцениваемые разделы)',
        dismissal_date__isnull=False,
        order_out_number='',
    ).select_related('group')
    max_length = Enrollment._meta.get_field('order_out_number').max_length

    for row in affected.iterator():
        group = row.group
        if group.status == 'cancelled' or (
            group.status == 'archived' and (
                group.archived_from_status == 'cancelled'
                or group.cancellation_date or group.cancellation_reason
            )
        ):
            continue
        number = f'{group.assigned_number}-ОТ'
        if not group.assigned_number or len(number) > max_length:
            continue
        # Match the group order format used for new dismissals.
        enrollments.filter(pk=row.pk, order_out_number='').update(
            order_out_number=number,
            order_out_date=row.order_out_date or row.dismissal_date,
        )


class Migration(migrations.Migration):
    dependencies = [('execution', '0010_enrollment_funding')]
    operations = [migrations.RunPython(restore_order_numbers, migrations.RunPython.noop)]
