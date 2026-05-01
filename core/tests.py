from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from core.models import Plan, Panel3XUI, UserService, PaymentReceipt


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
        resp = self.client.get('/api/plans/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    @patch('core.api.views.create_user_service')
    def test_create_service(self, mock_create):
        PaymentReceipt.objects.create(
            telegram_user_id=123,
            plan=self.plan,
            amount=self.plan.price,
            screenshot='receipts/test.jpg',
            status='approved',
        )

        mock_service = UserService(
            id=1,
            telegram_user_id=123,
            plan=self.plan,
            panel=self.panel,
            email='u@test',
            config_link='3xui://client/u@test',
            expire_at=timezone.now() + timedelta(days=30),
        )
        mock_create.return_value = mock_service
        resp = self.client.post('/api/services/create/', {'telegram_user_id': 123, 'plan_id': self.plan.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('config_link', resp.json())
