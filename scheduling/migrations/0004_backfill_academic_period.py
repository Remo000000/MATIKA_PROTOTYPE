from django.db import migrations


def forwards(apps, schema_editor):
    Organization = apps.get_model("university", "Organization")
    AcademicPeriod = apps.get_model("scheduling", "AcademicPeriod")
    Lesson = apps.get_model("scheduling", "Lesson")

    for org in Organization.objects.all():
        period, _ = AcademicPeriod.objects.get_or_create(
            organization_id=org.id,
            slug="default",
            defaults={
                "name": "Default period",
                "is_current": True,
            },
        )
        AcademicPeriod.objects.filter(organization_id=org.id).exclude(pk=period.pk).update(is_current=False)
        period.is_current = True
        period.save(update_fields=["is_current"])
        Lesson.objects.filter(academic_period__isnull=True).filter(
            group__department__faculty__organization_id=org.id
        ).update(academic_period_id=period.pk)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0003_academic_period_and_accounts"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
