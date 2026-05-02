import subprocess

from django.contrib import admin, messages
from django.db import transaction
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
from .services.provisioning import (
    ProvisioningError,
    create_user_service,
    renew_user_service,
    revoke_user_service,
    suspend_user_service,
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
    actions = ("renew_services", "suspend_services", "revoke_services")

    @admin.action(description="Renew selected services by their plan duration")
    def renew_services(self, request, queryset):
        renewed_count = 0
        failed_count = 0
        for service in queryset.select_related("plan", "panel"):
            try:
                renew_user_service(service=service, admin_user=request.user)
                renewed_count += 1
            except ProvisioningError as exc:
                failed_count += 1
                self.message_user(request, f"Service {service.pk} failed to renew: {exc}", level=messages.ERROR)
        if renewed_count:
            self.message_user(request, f"Renewed {renewed_count} service(s).", level=messages.SUCCESS)
        if failed_count and not renewed_count:
            self.message_user(request, f"Failed to renew {failed_count} service(s).", level=messages.ERROR)

    @admin.action(description="Suspend selected services")
    def suspend_services(self, request, queryset):
        suspended_count = 0
        failed_count = 0
        for service in queryset.select_related("panel"):
            try:
                suspend_user_service(service=service, admin_user=request.user)
                suspended_count += 1
            except ProvisioningError as exc:
                failed_count += 1
                self.message_user(request, f"Service {service.pk} failed to suspend: {exc}", level=messages.ERROR)
        if suspended_count:
            self.message_user(request, f"Suspended {suspended_count} service(s).", level=messages.SUCCESS)
        if failed_count and not suspended_count:
            self.message_user(request, f"Failed to suspend {failed_count} service(s).", level=messages.ERROR)

    @admin.action(description="Revoke selected services")
    def revoke_services(self, request, queryset):
        revoked_count = 0
        failed_count = 0
        for service in queryset.select_related("panel"):
            try:
                revoke_user_service(service=service, admin_user=request.user)
                revoked_count += 1
            except ProvisioningError as exc:
                failed_count += 1
                self.message_user(request, f"Service {service.pk} failed to revoke: {exc}", level=messages.ERROR)
        if revoked_count:
            self.message_user(request, f"Revoked {revoked_count} service(s).", level=messages.SUCCESS)
        if failed_count and not revoked_count:
            self.message_user(request, f"Failed to revoke {failed_count} service(s).", level=messages.ERROR)


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
    actions = ("approve_receipts", "reject_receipts")

    @admin.action(description="Approve selected receipts and provision services")
    def approve_receipts(self, request, queryset):
        approved_count = 0
        skipped_count = 0
        failed_count = 0

        for receipt in queryset.select_related("plan"):
            if receipt.status != "pending":
                skipped_count += 1
                continue

            with transaction.atomic():
                try:
                    create_user_service(
                        telegram_user_id=receipt.telegram_user_id,
                        plan=receipt.plan,
                        admin_user=request.user,
                        reason="receipt_approved",
                    )
                    receipt.status = "approved"
                    receipt.save(update_fields=["status"])
                    approved_count += 1
                except ProvisioningError as exc:
                    failed_count += 1
                    self.message_user(
                        request,
                        f"Receipt {receipt.pk} failed: {exc}",
                        level=messages.ERROR,
                    )

        if approved_count:
            self.message_user(
                request,
                f"Approved and provisioned {approved_count} receipt(s).",
                level=messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                f"Skipped {skipped_count} non-pending receipt(s).",
                level=messages.WARNING,
            )
        if failed_count and not approved_count:
            self.message_user(
                request,
                f"Provisioning failed for {failed_count} receipt(s).",
                level=messages.ERROR,
            )

    @admin.action(description="Reject selected receipts")
    def reject_receipts(self, request, queryset):
        updated = queryset.filter(status="pending").update(status="rejected")
        self.message_user(request, f"Rejected {updated} pending receipt(s).", level=messages.SUCCESS)


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
