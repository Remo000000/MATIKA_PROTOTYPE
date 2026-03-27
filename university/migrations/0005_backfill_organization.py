# Generated manually for multi-tenant backfill

from django.db import migrations


def forwards(apps, schema_editor):
    Organization = apps.get_model("university", "Organization")
    Faculty = apps.get_model("university", "Faculty")
    Room = apps.get_model("university", "Room")
    TimeSlot = apps.get_model("university", "TimeSlot")
    User = apps.get_model("accounts", "User")

    org, _ = Organization.objects.get_or_create(
        slug="default",
        defaults={"name": "Default organization"},
    )
    Faculty.objects.filter(organization__isnull=True).update(organization_id=org.id)
    Room.objects.filter(organization__isnull=True).update(organization_id=org.id)
    TimeSlot.objects.filter(organization__isnull=True).update(organization_id=org.id)
    User.objects.filter(organization__isnull=True).update(organization_id=org.id)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("university", "0004_organization_multitenant"),
        ("accounts", "0003_organization_multitenant"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
