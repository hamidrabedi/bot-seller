from django.urls import path
from .views import PlansView, CreateServiceView, MyServicesView, BankTransferInfoView, UploadReceiptView

urlpatterns = [
    path("plans/", PlansView.as_view(), name="plans"),
    path("payment/bank-info/", BankTransferInfoView.as_view(), name="bank-info"),
    path("payment/upload-receipt/", UploadReceiptView.as_view(), name="upload-receipt"),
    path("services/create/", CreateServiceView.as_view(), name="service-create"),
    path("services/my/", MyServicesView.as_view(), name="my-services"),
]
