import subprocess
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path
from .models import Panel3XUI, Plan, UserService, PaymentSettings, PaymentReceipt, SystemConfig


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


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ("title", "allow_admin_restart", "service_api_name", "service_bot_name")
    change_list_template = "admin/systemconfig_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("restart-services/", self.admin_site.admin_view(self.restart_services), name="core_systemconfig_restart"),
        ]
        return custom + urls

    def restart_services(self, request):
        cfg = SystemConfig.objects.filter(title="default").first()
        if not cfg or not cfg.allow_admin_restart:
            self.message_user(request, "Restart is disabled in SystemConfig.", level=messages.ERROR)
            return HttpResponseRedirect("../")

        try:
            subprocess.run(["sudo", "systemctl", "restart", cfg.service_api_name], check=True)
            subprocess.run(["sudo", "systemctl", "restart", cfg.service_bot_name], check=True)
            self.message_user(request, "Services restarted successfully.", level=messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"Failed to restart: {exc}", level=messages.ERROR)

        return HttpResponseRedirect("../")


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "telegram_user_id", "plan", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("telegram_user_id", "id")
