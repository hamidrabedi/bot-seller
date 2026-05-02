from dataclasses import dataclass
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from core.models import (
    AdminPanelScope,
    AdminProfile,
    AuditLog,
    GenerationPolicy,
    GenerationQuotaLedger,
    Panel3XUI,
    Plan,
)

User = get_user_model()

GENERATE_PERMISSION = "configs.generate"


class PolicyError(Exception):
    pass


@dataclass
class GenerationAuthorization:
    admin_profile: Optional[AdminProfile]
    policy: Optional[GenerationPolicy]


def _get_admin_profile(user: User) -> AdminProfile:
    profile = (
        AdminProfile.objects.select_related("user")
        .filter(user=user, is_active=True)
        .first()
    )
    if not profile:
        raise PolicyError("Admin profile is not active or does not exist.")
    return profile


def _has_permission(profile: AdminProfile, permission_code: str) -> bool:
    return profile.role_assignments.filter(role__grants__permission_code=permission_code).exists()


def _resolve_policy(plan: Plan, panel: Panel3XUI) -> Optional[GenerationPolicy]:
    return (
        GenerationPolicy.objects.filter(plan=plan, panel=panel, is_active=True).first()
        or GenerationPolicy.objects.filter(plan=plan, panel__isnull=True, is_active=True).first()
    )


def authorize_generation(
    *,
    plan: Plan,
    panel: Panel3XUI,
    admin_user: Optional[User] = None,
    requested_duration_days: Optional[int] = None,
    requested_traffic_gb: Optional[int] = None,
    is_user_self_service: bool = False,
) -> GenerationAuthorization:
    policy = _resolve_policy(plan, panel)
    if is_user_self_service:
        if policy and not policy.allow_user_self_service:
            raise PolicyError("This plan is not allowed for self-service generation.")
        return GenerationAuthorization(admin_profile=None, policy=policy)

    if admin_user is None:
        raise PolicyError("Admin user is required for manual generation.")

    if admin_user.is_superuser:
        return GenerationAuthorization(
            admin_profile=AdminProfile.objects.filter(user=admin_user).first(),
            policy=policy,
        )

    profile = _get_admin_profile(admin_user)
    if not _has_permission(profile, GENERATE_PERMISSION):
        raise PolicyError("Admin does not have config generation permission.")

    scope = AdminPanelScope.objects.filter(admin=profile, panel=panel).first()
    if not scope or not scope.can_generate_configs:
        raise PolicyError("Admin is not allowed to generate configs on this panel.")

    if policy and not policy.allow_manual_generation:
        raise PolicyError("Generation is disabled for this plan on the selected panel.")

    duration_days = requested_duration_days or plan.duration_days
    traffic_gb = requested_traffic_gb or plan.traffic_gb
    if policy and policy.max_duration_days_override and duration_days > policy.max_duration_days_override:
        raise PolicyError("Requested duration exceeds the allowed override.")
    if policy and policy.max_traffic_gb_override and traffic_gb > policy.max_traffic_gb_override:
        raise PolicyError("Requested traffic exceeds the allowed override.")

    today = timezone.now().date()
    used_today = (
        GenerationQuotaLedger.objects.filter(
            actor_admin=profile,
            plan=plan,
            panel=panel,
            created_at__date=today,
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    if scope.daily_generation_limit is not None and used_today >= scope.daily_generation_limit:
        raise PolicyError("Admin has reached the daily generation limit for this panel.")

    if policy and policy.max_configs_per_day_per_admin and used_today >= policy.max_configs_per_day_per_admin:
        raise PolicyError("Generation policy limit reached for today.")

    return GenerationAuthorization(admin_profile=profile, policy=policy)


def record_generation_event(
    *,
    admin_profile: Optional[AdminProfile],
    plan: Plan,
    panel: Panel3XUI,
    service,
    action: str,
    quantity: int = 1,
) -> None:
    GenerationQuotaLedger.objects.create(
        actor_admin=admin_profile,
        plan=plan,
        panel=panel,
        service=service,
        action=action,
        quantity=quantity,
    )


def log_audit_event(
    *,
    action: str,
    actor_user: Optional[User] = None,
    actor_admin: Optional[AdminProfile] = None,
    target_model: str = "",
    target_id: str = "",
    message: str = "",
    metadata: Optional[dict] = None,
) -> None:
    AuditLog.objects.create(
        action=action,
        actor_user=actor_user,
        actor_admin=actor_admin,
        target_model=target_model,
        target_id=target_id,
        message=message,
        metadata=metadata or {},
    )
