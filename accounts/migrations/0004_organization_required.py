import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_organization_multitenant"),
        ("university", "0006_organization_required"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="users",
                to="university.organization",
                verbose_name="Organization",
            ),
        ),
    ]
