import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0004_backfill_academic_period"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lesson",
            name="academic_period",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lessons",
                to="scheduling.academicperiod",
                verbose_name="Academic period",
            ),
        ),
    ]
