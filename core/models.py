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
    telegram_user_id = models.BigIntegerField(db_index=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    panel = models.ForeignKey(Panel3XUI, on_delete=models.PROTECT)
    email = models.CharField(max_length=120, unique=True)
    config_link = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="active")
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
