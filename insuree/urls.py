from .views import * 
from django.urls import path, include

urlpatterns = [
    # path('insuree/family/<family_uuid>', print_membership),
    path('insuree/family/<family_uuid>/<type>', PrintPdfSlipView.as_view(), name="membership"),
    path('insuree/report/excel-export', InsureeToExcelExport, name="InsureeToExcelExport")
    
]