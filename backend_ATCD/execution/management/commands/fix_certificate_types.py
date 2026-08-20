from django.core.management.base import BaseCommand
from execution.models import Certificate


class Command(BaseCommand):
    help = 'Заполняет certificate_type для существующих сертификатов на основе программы'

    def handle(self, *args, **options):
        updated_count = 0
        skipped_count = 0

        self.stdout.write("Начинаю обновление сертификатов...")

        for cert in Certificate.objects.all():
            if cert.enrollment and cert.enrollment.group.module.course:
                course = cert.enrollment.group.module.course
                cert.certificate_type = course.default_certificate_type
                cert.save(update_fields=['certificate_type'])
                updated_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'✅ Готово!')
        )
        self.stdout.write(f'   Обновлено: {updated_count}')
        self.stdout.write(f'   Пропущено: {skipped_count}')