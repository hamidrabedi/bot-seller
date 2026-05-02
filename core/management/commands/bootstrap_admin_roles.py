from django.core.management.base import BaseCommand

from core.models import AdminRole, AdminRoleGrant

ROLE_DEFINITIONS = {
    "super_admin": {
        "name": "Super Admin",
        "description": "Full operational access across panels, plans, and admin tools.",
        "permissions": [
            "configs.generate",
            "configs.revoke",
            "services.manage",
            "plans.manage",
            "panels.manage",
            "payments.review",
            "admins.manage",
            "reports.view",
        ],
    },
    "ops_admin": {
        "name": "Operations Admin",
        "description": "Panel and service operations without top-level admin management.",
        "permissions": [
            "configs.generate",
            "configs.revoke",
            "services.manage",
            "plans.manage",
            "panels.manage",
            "reports.view",
        ],
    },
    "sales_admin": {
        "name": "Sales Admin",
        "description": "Sales and payment operations with controlled generation access.",
        "permissions": [
            "configs.generate",
            "payments.review",
            "reports.view",
        ],
    },
    "support_admin": {
        "name": "Support Admin",
        "description": "Read-heavy support role for customer follow-up and reporting.",
        "permissions": [
            "reports.view",
        ],
    },
}


class Command(BaseCommand):
    help = "Create or refresh the default admin roles and grants"

    def handle(self, *args, **options):
        for code, definition in ROLE_DEFINITIONS.items():
            role, _ = AdminRole.objects.update_or_create(
                code=code,
                defaults={
                    "name": definition["name"],
                    "description": definition["description"],
                    "is_system": True,
                },
            )
            existing = set(role.grants.values_list("permission_code", flat=True))
            desired = set(definition["permissions"])

            for permission_code in desired - existing:
                AdminRoleGrant.objects.create(role=role, permission_code=permission_code)

            role.grants.exclude(permission_code__in=desired).delete()
            self.stdout.write(self.style.SUCCESS(f"Synced role {code}"))
