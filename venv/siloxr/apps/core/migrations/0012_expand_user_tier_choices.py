from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_user_country_currency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="tier",
            field=models.CharField(
                choices=[
                    ("free", "Free"),
                    ("core", "Core"),
                    ("pro", "Pro"),
                    ("enterprise", "Enterprise"),
                ],
                default="free",
                max_length=20,
            ),
        ),
    ]
