import time
import uuid
from datetime import timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import AdminProfile, Panel3XUI, Plan, UserService
from core.services.policies import PolicyError, authorize_generation, log_audit_event, record_generation_event
from core.services.three_xui import ThreeXUIClient, ThreeXUICredentials

User = get_user_model()


class ProvisioningError(Exception):
    pass


def create_user_service(
    *,
    telegram_user_id: int,
    plan: Plan,
    admin_user: Optional[User] = None,
    panel: Optional[Panel3XUI] = None,
    reason: str = "manual_generation",
    requested_duration_days: Optional[int] = None,
    requested_traffic_gb: Optional[int] = None,
) -> UserService:
    selected_panel = panel or Panel3XUI.objects.filter(is_active=True).first()
    if not selected_panel:
        raise ProvisioningError("No active 3x-ui panel configured")

    duration_days = requested_duration_days or plan.duration_days
    traffic_gb = requested_traffic_gb or plan.traffic_gb

    try:
        authz = authorize_generation(
            plan=plan,
            panel=selected_panel,
            admin_user=admin_user,
            requested_duration_days=duration_days,
            requested_traffic_gb=traffic_gb,
            is_user_self_service=admin_user is None,
        )
    except PolicyError as exc:
        raise ProvisioningError(str(exc)) from exc

    client_uuid = str(uuid.uuid4())
    email = f"u{telegram_user_id}-{int(time.time())}@bot"
    expire_at = timezone.now() + timedelta(days=duration_days)
    expire_time_ms = int(expire_at.timestamp() * 1000)
    total_gb = traffic_gb * 1024 * 1024 * 1024

    creds = ThreeXUICredentials(selected_panel.base_url, selected_panel.username, selected_panel.password)
    client = ThreeXUIClient(creds)
    client.login()
    created = client.create_client(
        selected_panel.inbound_id,
        email,
        expire_time_ms,
        total_gb,
        client_id=client_uuid,
    )
    link = client.build_client_link(email)

    service = UserService.objects.create(
        telegram_user_id=telegram_user_id,
        plan=plan,
        panel=selected_panel,
        client_uuid=created["client_id"],
        email=email,
        config_link=link,
        expire_at=expire_at,
    )

    record_generation_event(
        admin_profile=authz.admin_profile,
        plan=plan,
        panel=selected_panel,
        service=service,
        action="service_create",
    )
    log_audit_event(
        action="service_create",
        actor_user=admin_user,
        actor_admin=authz.admin_profile,
        target_model="UserService",
        target_id=str(service.pk),
        message=f"Created service for telegram user {telegram_user_id}",
        metadata={
            "reason": reason,
            "plan_id": plan.pk,
            "panel_id": selected_panel.pk,
            "duration_days": duration_days,
            "traffic_gb": traffic_gb,
        },
    )
    return service


def renew_user_service(
    *,
    service: UserService,
    admin_user: User,
    duration_days: Optional[int] = None,
    traffic_gb: Optional[int] = None,
) -> UserService:
    if not service.client_uuid:
        raise ProvisioningError("Service does not have a tracked 3x-ui client id.")

    selected_panel = service.panel
    plan = service.plan
    extra_days = duration_days or plan.duration_days
    total_traffic_gb = traffic_gb or plan.traffic_gb

    try:
        authz = authorize_generation(
            plan=plan,
            panel=selected_panel,
            admin_user=admin_user,
            requested_duration_days=extra_days,
            requested_traffic_gb=total_traffic_gb,
        )
    except PolicyError as exc:
        raise ProvisioningError(str(exc)) from exc

    base_time = service.expire_at if service.expire_at and service.expire_at > timezone.now() else timezone.now()
    service.expire_at = base_time + timedelta(days=extra_days)
    total_gb = total_traffic_gb * 1024 * 1024 * 1024

    creds = ThreeXUICredentials(selected_panel.base_url, selected_panel.username, selected_panel.password)
    client = ThreeXUIClient(creds)
    client.login()
    client.update_client(
        inbound_id=selected_panel.inbound_id,
        client_id=service.client_uuid,
        email=service.email,
        expire_time_ms=int(service.expire_at.timestamp() * 1000),
        total_gb=total_gb,
        enable=True,
    )
    client.reset_client_traffic(selected_panel.inbound_id, service.email)
    service.status = "active"
    service.save(update_fields=["expire_at", "status"])

    record_generation_event(
        admin_profile=authz.admin_profile,
        plan=plan,
        panel=selected_panel,
        service=service,
        action="service_renew",
    )
    log_audit_event(
        action="service_renew",
        actor_user=admin_user,
        actor_admin=authz.admin_profile,
        target_model="UserService",
        target_id=str(service.pk),
        message=f"Renewed service {service.pk}",
        metadata={"duration_days": extra_days, "traffic_gb": total_traffic_gb},
    )
    return service


def suspend_user_service(*, service: UserService, admin_user: User) -> UserService:
    if not service.client_uuid:
        raise ProvisioningError("Service does not have a tracked 3x-ui client id.")

    creds = ThreeXUICredentials(service.panel.base_url, service.panel.username, service.panel.password)
    client = ThreeXUIClient(creds)
    client.login()
    client.update_client(
        inbound_id=service.panel.inbound_id,
        client_id=service.client_uuid,
        email=service.email,
        expire_time_ms=int((service.expire_at or timezone.now()).timestamp() * 1000),
        total_gb=service.plan.traffic_gb * 1024 * 1024 * 1024,
        enable=False,
    )
    service.status = "suspended"
    service.save(update_fields=["status"])
    log_audit_event(
        action="service_suspend",
        actor_user=admin_user,
        actor_admin=AdminProfile.objects.filter(user=admin_user).first(),
        target_model="UserService",
        target_id=str(service.pk),
        message=f"Suspended service {service.pk}",
    )
    return service


def revoke_user_service(*, service: UserService, admin_user: User) -> UserService:
    creds = ThreeXUICredentials(service.panel.base_url, service.panel.username, service.panel.password)
    client = ThreeXUIClient(creds)
    client.login()
    client.delete_client_by_email(service.panel.inbound_id, service.email)
    service.status = "revoked"
    service.save(update_fields=["status"])
    log_audit_event(
        action="service_revoke",
        actor_user=admin_user,
        actor_admin=AdminProfile.objects.filter(user=admin_user).first(),
        target_model="UserService",
        target_id=str(service.pk),
        message=f"Revoked service {service.pk}",
    )
    return service
