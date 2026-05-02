from django.conf import settings
from django.db import models


class Panel3XUI(models.Model):
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField()
    username = models.CharField(max_length=120)
    password = models.CharField(max_length=120)
    inbound_id = models.IntegerField(help_text="3x-ui inbound id used for new clients")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Plan(models.Model):
    name_fa = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField()
    traffic_gb = models.PositiveIntegerField()
    price = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name_en} ({self.duration_days}d/{self.traffic_gb}GB)"


class UserService(models.Model):
    STATUS_CHOICES = (
        ("pending", "pending"),
        ("active", "active"),
        ("suspended", "suspended"),
        ("expired", "expired"),
        ("revoked", "revoked"),
    )

    telegram_user_id = models.BigIntegerField(db_index=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    panel = models.ForeignKey(Panel3XUI, on_delete=models.PROTECT)
    email = models.CharField(max_length=120, unique=True)
    config_link = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    expire_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.telegram_user_id} - {self.email}"


class PaymentSettings(models.Model):
    title = models.CharField(max_length=30, default="default", unique=True)
    bank_transfer_text_fa = models.TextField(default="شماره کارت: ...\nبه نام: ...")
    bank_transfer_text_en = models.TextField(default="Card Number: ...\nHolder: ...")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class SystemConfig(models.Model):
    title = models.CharField(max_length=30, default="default", unique=True)
    telegram_bot_token = models.CharField(max_length=255, blank=True)
    service_api_name = models.CharField(max_length=120, default="bot-seller-api")
    service_bot_name = models.CharField(max_length=120, default="bot-seller-bot")
    allow_admin_restart = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class PaymentReceipt(models.Model):
    STATUS_CHOICES = (("pending", "pending"), ("approved", "approved"), ("rejected", "rejected"))
    telegram_user_id = models.BigIntegerField(db_index=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    amount = models.PositiveIntegerField()
    screenshot = models.ImageField(upload_to="receipts/")
    note = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"receipt:{self.id} user:{self.telegram_user_id} {self.status}"


class AdminProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_profile")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_username()


class AdminRole(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AdminRoleGrant(models.Model):
    role = models.ForeignKey(AdminRole, on_delete=models.CASCADE, related_name="grants")
    permission_code = models.CharField(max_length=100)

    class Meta:
        unique_together = ("role", "permission_code")

    def __str__(self):
        return f"{self.role.code}:{self.permission_code}"


class AdminRoleAssignment(models.Model):
    admin = models.ForeignKey(AdminProfile, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(AdminRole, on_delete=models.CASCADE, related_name="assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("admin", "role")

    def __str__(self):
        return f"{self.admin} -> {self.role.code}"


class AdminPanelScope(models.Model):
    admin = models.ForeignKey(AdminProfile, on_delete=models.CASCADE, related_name="panel_scopes")
    panel = models.ForeignKey(Panel3XUI, on_delete=models.CASCADE, related_name="admin_scopes")
    can_generate_configs = models.BooleanField(default=False)
    can_manage_services = models.BooleanField(default=False)
    can_manage_panel = models.BooleanField(default=False)
    daily_generation_limit = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("admin", "panel")

    def __str__(self):
        return f"{self.admin} @ {self.panel}"


class GenerationPolicy(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="generation_policies")
    panel = models.ForeignKey(
        Panel3XUI,
        on_delete=models.CASCADE,
        related_name="generation_policies",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    allow_manual_generation = models.BooleanField(default=True)
    allow_user_self_service = models.BooleanField(default=True)
    max_configs_per_day_per_admin = models.PositiveIntegerField(default=0)
    max_duration_days_override = models.PositiveIntegerField(null=True, blank=True)
    max_traffic_gb_override = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("plan", "panel")

    def __str__(self):
        panel_name = self.panel.name if self.panel else "default"
        return f"{self.plan.name_en} @ {panel_name}"


class GenerationQuotaLedger(models.Model):
    ACTION_CHOICES = (
        ("service_create", "service_create"),
        ("service_renew", "service_renew"),
        ("manual_override", "manual_override"),
    )

    actor_admin = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quota_events",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="quota_events")
    panel = models.ForeignKey(Panel3XUI, on_delete=models.PROTECT, related_name="quota_events")
    service = models.ForeignKey(
        UserService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quota_events",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action}:{self.quantity}"


class AuditLog(models.Model):
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    actor_admin = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    target_model = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.action
