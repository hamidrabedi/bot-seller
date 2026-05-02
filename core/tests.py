from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.admin import PaymentReceiptAdmin
from core.models import (
    AdminPanelScope,
    AdminProfile,
    AdminRole,
    AdminRoleAssignment,
    AdminRoleGrant,
    GenerationPolicy,
    Panel3XUI,
    PaymentReceipt,
    Plan,
    UserService,
)

User = get_user_model()


class APITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.plan = Plan.objects.create(name_fa="پلن تست", name_en="Test Plan", duration_days=30, traffic_gb=50, price=100)
        self.panel = Panel3XUI.objects.create(
            name="Main",
            base_url="https://example.com",
            username="admin",
            password="pass",
            inbound_id=1,
            is_active=True,
        )

    def test_plans_list(self):
        resp = self.client.get("/api/plans/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    @patch("core.api.views.create_user_service")
    def test_create_service(self, mock_create):
        PaymentReceipt.objects.create(
            telegram_user_id=123,
            plan=self.plan,
            amount=self.plan.price,
            screenshot="receipts/test.jpg",
            status="approved",
        )

        mock_service = UserService(
            id=1,
            telegram_user_id=123,
            plan=self.plan,
            panel=self.panel,
            email="u@test",
            config_link="3xui://client/u@test",
            expire_at=timezone.now() + timedelta(days=30),
        )
        mock_create.return_value = mock_service
        resp = self.client.post("/api/services/create/", {"telegram_user_id": 123, "plan_id": self.plan.id}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("config_link", resp.json())


class AdminApprovalTests(TestCase):
    def setUp(self):
        self.site = admin.site
        self.factory = RequestFactory()
        self.plan = Plan.objects.create(name_fa="پلن تست", name_en="Test Plan", duration_days=30, traffic_gb=50, price=100)
        self.panel = Panel3XUI.objects.create(
            name="Main",
            base_url="https://example.com",
            username="admin",
            password="pass",
            inbound_id=1,
            is_active=True,
        )
        self.user = User.objects.create_user(username="ops", password="secret")
        self.profile = AdminProfile.objects.create(user=self.user)
        self.role = AdminRole.objects.create(code="sales_admin", name="Sales Admin")
        AdminRoleGrant.objects.create(role=self.role, permission_code="configs.generate")
        AdminRoleAssignment.objects.create(admin=self.profile, role=self.role)
        AdminPanelScope.objects.create(admin=self.profile, panel=self.panel, can_generate_configs=True, daily_generation_limit=5)
        GenerationPolicy.objects.create(plan=self.plan, panel=self.panel, max_configs_per_day_per_admin=5)
        self.receipt = PaymentReceipt.objects.create(
            telegram_user_id=123,
            plan=self.plan,
            amount=self.plan.price,
            screenshot="receipts/test.jpg",
            status="pending",
        )

    @patch("core.services.provisioning.ThreeXUIClient.create_client")
    @patch("core.services.provisioning.ThreeXUIClient.login")
    @patch("core.admin.subprocess.run")
    def test_admin_can_approve_receipt_and_create_service(self, _mock_subprocess, _mock_login, _mock_create_client):
        request = self.factory.post("/admin/core/paymentreceipt/")
        request.user = self.user
        model_admin = PaymentReceiptAdmin(PaymentReceipt, self.site)
        model_admin.approve_receipts(request, PaymentReceipt.objects.filter(pk=self.receipt.pk))

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "approved")
        self.assertEqual(UserService.objects.count(), 1)
