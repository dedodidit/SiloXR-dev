from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_user_terms_acceptance"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="country",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="user",
            name="currency",
            field=models.CharField(blank=True, default="USD", max_length=10),
        ),
    ]
