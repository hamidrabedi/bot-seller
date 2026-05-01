import time
from datetime import timedelta
from django.utils import timezone
from core.models import Panel3XUI, Plan, UserService
from core.services.three_xui import ThreeXUIClient, ThreeXUICredentials


class ProvisioningError(Exception):
    pass


def create_user_service(*, telegram_user_id: int, plan: Plan) -> UserService:
    panel = Panel3XUI.objects.filter(is_active=True).first()
    if not panel:
        raise ProvisioningError("No active 3x-ui panel configured")

    email = f"u{telegram_user_id}-{int(time.time())}@bot"
    expire_at = timezone.now() + timedelta(days=plan.duration_days)
    expire_time_ms = int(expire_at.timestamp() * 1000)
    total_gb = plan.traffic_gb * 1024 * 1024 * 1024

    creds = ThreeXUICredentials(panel.base_url, panel.username, panel.password)
    client = ThreeXUIClient(creds)
    client.login()
    client.create_client(panel.inbound_id, email, expire_time_ms, total_gb)
    link = client.build_client_link(email)

    return UserService.objects.create(
        telegram_user_id=telegram_user_id,
        plan=plan,
        panel=panel,
        email=email,
        config_link=link,
        expire_at=expire_at,
    )
