from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_admin_policy_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="userservice",
            name="client_uuid",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
