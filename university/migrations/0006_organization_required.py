import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("university", "0005_backfill_organization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="faculty",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="faculties",
                to="university.organization",
                verbose_name="Organization",
            ),
        ),
        migrations.AlterField(
            model_name="room",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rooms",
                to="university.organization",
                verbose_name="Organization",
            ),
        ),
        migrations.AlterField(
            model_name="timeslot",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="timeslots",
                to="university.organization",
                verbose_name="Organization",
            ),
        ),
    ]
