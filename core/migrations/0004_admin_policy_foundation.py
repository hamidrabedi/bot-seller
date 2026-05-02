from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0003_systemconfig"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userservice",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "pending"),
                    ("active", "active"),
                    ("suspended", "suspended"),
                    ("expired", "expired"),
                    ("revoked", "revoked"),
                ],
                default="active",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="AdminProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="admin_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="AdminRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("is_system", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=100)),
                ("target_model", models.CharField(blank=True, max_length=100)),
                ("target_id", models.CharField(blank=True, max_length=100)),
                ("message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor_admin", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to="core.adminprofile")),
                ("actor_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="AdminPanelScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("can_generate_configs", models.BooleanField(default=False)),
                ("can_manage_services", models.BooleanField(default=False)),
                ("can_manage_panel", models.BooleanField(default=False)),
                ("daily_generation_limit", models.PositiveIntegerField(blank=True, null=True)),
                ("admin", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="panel_scopes", to="core.adminprofile")),
                ("panel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="admin_scopes", to="core.panel3xui")),
            ],
            options={"unique_together": {("admin", "panel")}},
        ),
        migrations.CreateModel(
            name="AdminRoleAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("admin", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_assignments", to="core.adminprofile")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="core.adminrole")),
            ],
            options={"unique_together": {("admin", "role")}},
        ),
        migrations.CreateModel(
            name="AdminRoleGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permission_code", models.CharField(max_length=100)),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="grants", to="core.adminrole")),
            ],
            options={"unique_together": {("role", "permission_code")}},
        ),
        migrations.CreateModel(
            name="GenerationPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("allow_manual_generation", models.BooleanField(default=True)),
                ("allow_user_self_service", models.BooleanField(default=True)),
                ("max_configs_per_day_per_admin", models.PositiveIntegerField(default=0)),
                ("max_duration_days_override", models.PositiveIntegerField(blank=True, null=True)),
                ("max_traffic_gb_override", models.PositiveIntegerField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("panel", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="generation_policies", to="core.panel3xui")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="generation_policies", to="core.plan")),
            ],
            options={"unique_together": {("plan", "panel")}},
        ),
        migrations.CreateModel(
            name="GenerationQuotaLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("service_create", "service_create"), ("service_renew", "service_renew"), ("manual_override", "manual_override")], max_length=30)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor_admin", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quota_events", to="core.adminprofile")),
                ("panel", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quota_events", to="core.panel3xui")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quota_events", to="core.plan")),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quota_events", to="core.userservice")),
            ],
        ),
    ]
