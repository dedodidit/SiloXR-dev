from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0005_decisionlog_original_action_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReorderRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("suggested_quantity", models.PositiveIntegerField(default=0)),
                ("suggested_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("placed", "Placed"), ("received", "Received")], default="pending", max_length=20)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("decision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reorder_records", to="inventory.decisionlog")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reorder_records", to="inventory.product")),
            ],
            options={
                "db_table": "inventory_reorder_record",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="reorderrecord",
            index=models.Index(fields=["product", "status", "created_at"], name="inventory_r_product_c21cd4_idx"),
        ),
    ]
