import subprocess

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path

from .models import (
    AdminPanelScope,
    AdminProfile,
    AdminRole,
    AdminRoleAssignment,
    AdminRoleGrant,
    AuditLog,
    GenerationPolicy,
    GenerationQuotaLedger,
    Panel3XUI,
    PaymentReceipt,
    PaymentSettings,
    Plan,
    SystemConfig,
    UserService,
)


class AdminRoleGrantInline(admin.TabularInline):
    model = AdminRoleGrant
    extra = 1


class AdminRoleAssignmentInline(admin.TabularInline):
    model = AdminRoleAssignment
    extra = 1


class AdminPanelScopeInline(admin.TabularInline):
    model = AdminPanelScope
    extra = 1


@admin.register(Panel3XUI)
class Panel3XUIAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "inbound_id", "is_active")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name_en", "duration_days", "traffic_gb", "price", "is_active")


@admin.register(UserService)
class UserServiceAdmin(admin.ModelAdmin):
    list_display = ("telegram_user_id", "email", "plan", "panel", "status", "expire_at")
    search_fields = ("telegram_user_id", "email")
    list_filter = ("status", "panel", "plan")


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


@admin.register(AdminRole)
class AdminRoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_system", "created_at")
    search_fields = ("code", "name")
    inlines = (AdminRoleGrantInline,)


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "created_at")
    search_fields = ("user__username", "user__email")
    inlines = (AdminRoleAssignmentInline, AdminPanelScopeInline)


@admin.register(GenerationPolicy)
class GenerationPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "plan",
        "panel",
        "is_active",
        "allow_manual_generation",
        "allow_user_self_service",
        "max_configs_per_day_per_admin",
    )
    list_filter = ("is_active", "allow_manual_generation", "allow_user_self_service")


@admin.register(GenerationQuotaLedger)
class GenerationQuotaLedgerAdmin(admin.ModelAdmin):
    list_display = ("actor_admin", "plan", "panel", "action", "quantity", "created_at")
    list_filter = ("action", "panel", "plan")
    search_fields = ("actor_admin__user__username",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor_user", "actor_admin", "target_model", "target_id", "created_at")
    list_filter = ("action", "target_model")
    search_fields = ("message", "target_id", "actor_user__username", "actor_admin__user__username")
