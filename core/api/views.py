from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import PaymentReceipt, PaymentSettings, Plan, UserService
from core.services.provisioning import ProvisioningError, create_user_service


class PlansView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        plans = Plan.objects.filter(is_active=True).values("id", "name_fa", "name_en", "duration_days", "traffic_gb", "price")
        return Response(list(plans))


class BankTransferInfoView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        lang = request.headers.get("Accept-Language", "fa").lower()
        settings = PaymentSettings.objects.filter(is_active=True).first()
        if not settings:
            return Response({"detail": "payment settings not configured"}, status=status.HTTP_404_NOT_FOUND)
        text = settings.bank_transfer_text_fa if lang.startswith("fa") else settings.bank_transfer_text_en
        return Response({"text": text})


class UploadReceiptView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        telegram_user_id = int(request.data.get("telegram_user_id", 0))
        plan_id = int(request.data.get("plan_id", 0))
        screenshot = request.FILES.get("screenshot")
        note = request.data.get("note", "")
        if not telegram_user_id or not plan_id or not screenshot:
            return Response({"detail": "telegram_user_id, plan_id, screenshot required"}, status=status.HTTP_400_BAD_REQUEST)

        plan = Plan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            return Response({"detail": "active plan not found"}, status=status.HTTP_400_BAD_REQUEST)

        receipt = PaymentReceipt.objects.create(
            telegram_user_id=telegram_user_id,
            plan=plan,
            amount=plan.price,
            screenshot=screenshot,
            note=note,
        )
        return Response({"receipt_id": receipt.id, "status": receipt.status})


class CreateServiceView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        telegram_user_id = int(request.data.get("telegram_user_id", 0))
        plan_id = int(request.data.get("plan_id", 0))
        if not telegram_user_id or not plan_id:
            return Response({"detail": "telegram_user_id and plan_id required"}, status=status.HTTP_400_BAD_REQUEST)

        has_approved_payment = PaymentReceipt.objects.filter(
            telegram_user_id=telegram_user_id,
            plan_id=plan_id,
            status="approved",
        ).exists()
        if not has_approved_payment:
            return Response({"detail": "approved payment receipt required"}, status=status.HTTP_402_PAYMENT_REQUIRED)

        plan = Plan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            return Response({"detail": "active plan not found"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            service = create_user_service(telegram_user_id=telegram_user_id, plan=plan, reason="user_purchase")
        except ProvisioningError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"detail": "failed to create service with 3x-ui"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"id": service.id, "config_link": service.config_link, "expire_at": service.expire_at})


class MyServicesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        telegram_user_id = int(request.query_params.get("telegram_user_id", 0))
        if not telegram_user_id:
            return Response({"detail": "telegram_user_id required"}, status=status.HTTP_400_BAD_REQUEST)

        services = UserService.objects.filter(telegram_user_id=telegram_user_id).values(
            "id",
            "email",
            "status",
            "expire_at",
            "config_link",
            "plan__name_fa",
            "plan__name_en",
            "plan__traffic_gb",
        )
        return Response(list(services))
