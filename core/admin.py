from django.contrib import admin
from .models import Panel3XUI, Plan, UserService, PaymentSettings, PaymentReceipt


@admin.register(Panel3XUI)
class Panel3XUIAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "inbound_id", "is_active")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name_en", "duration_days", "traffic_gb", "price", "is_active")


@admin.register(UserService)
class UserServiceAdmin(admin.ModelAdmin):
    list_display = ("telegram_user_id", "email", "plan", "status", "expire_at")
    search_fields = ("telegram_user_id", "email")


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active")


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "telegram_user_id", "plan", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("telegram_user_id", "id")
