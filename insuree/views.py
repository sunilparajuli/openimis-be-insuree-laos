# Create your views here.
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa

from django.shortcuts import render
from wkhtmltopdf.views import PDFTemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

# Create your views here.
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db.models.query import QuerySet
from django.shortcuts import render
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from location.models import Location


def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("utf8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type="application/pdf")
    return None





class PrintPdfSlipView(APIView, PDFTemplateView):
    filename = "slip_forms.pdf"
    template_name = "membership.html"
    cmd_options = {
        # 'margin-top': 3,
        "orientation": "Portrait",
        "page-size": "A4",
        "no-outline": None,
        "encoding": "UTF-8",
        "enable-local-file-access": None,
        "quiet": True,
    }

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        # if request.method == "GET":
        #     raise Http404
        return super(PrintPdfSlipView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        print("self", self.request.user)
        print("kwargs", kwargs)
        from .models import Insuree, Family

        # import pdb;pdb.set_trace()
        if kwargs.get("type") == "2" or kwargs.get("type") == 2:
            insuree = Insuree.objects.filter(uuid=kwargs.get("family_uuid")).first()
            insuree_families = (
                Insuree.objects.filter(family=insuree.family).order_by("id").all()
            )
            chfid = str(insuree.chf_id)
            # Convert chfid property to an array
            chfid_array = list(chfid)
            context = {
                "insurees": insuree_families,
                "insuree": insuree,
                "multiples": [1, 2] if insuree_families.count() <=12 else [1,2],
                "chfid_array": chfid_array,
            }
        else:
            family_uuid = kwargs.get("family_uuid")
            family = Family.objects.filter(uuid=family_uuid).first()
            insurees = Insuree.objects.filter(family=family).order_by("id").all()
            insuree = Insuree.objects.filter(family=family, head=True).first()
            chfid = str(insuree.chf_id)
            chfid_array = list(chfid)
            context = {
                "insurees": insurees,
                "multiples": [1, 2],
                "chfid_array": chfid_array,
                "insuree": insuree,
            }
        context["title"] = "Slip Generation"

        # context["size"] = 400
        # context["results"] = sorted(matched_cases, key=lambda k: k['index'])
        return context


import io
from django.db import connection
import xlsxwriter



def query_to_excel_download_helper(query, custom_header=None, filename=None):
    output = io.BytesIO()
    cursor = connection.cursor()
    cursor.execute(query)

    header = [row[0] for row in cursor.description]
    if custom_header:
        header = custom_header
    rows = cursor.fetchall()
    # Create an new Excel file and add a worksheet.
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet("Report")

    # Create style for cells
    header_cell_format = workbook.add_format(
        {"bold": True, "border": True}
    )
    body_cell_format = workbook.add_format({"border": True})

    # header, rows = fetch_table_data(table_name)

    row_index = 0
    column_index = 0
    # if not custom_header:
    for column_name in header:
        # print('col_name', column_name)
        worksheet.write(row_index, column_index, column_name, header_cell_format)
        column_index += 1

    row_index += 1
    for row in rows:
        column_index = 0
        for column in row:
            worksheet.write(row_index, column_index, column, body_cell_format)
            column_index += 1
        row_index += 1

    # Closing workbook
    workbook.close()
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="report_data.xlsx"'
    print("response", response)
    output.close()
    return response


from django.core.exceptions import PermissionDenied
from .models import Insuree
from claim.models import Claim
import pandas as pd
import io 


def stringify_querset(qs):
    sql, params = qs.query.sql_with_params()
    with connection.cursor() as cursor:
        return cursor.mogrify(sql, params)



@api_view(["GET"])
def claimToExcelExport(request):
    
    cleaned_get_params = {key: value[0] if isinstance(value, list) and len(value) == 1 else value for key, value in request.GET.items()}
  
    fields_to_select_claim = [
        "code",
        "validity_from",
        "validity_to",
        "claimed",
        "approved",
        "date_claimed",
        "status"
        # Add more field names from the Claim model as needed
    ]

    fields_to_select_insuree= [
        "insuree__chf_id",
        "insuree__other_names",
        "insuree__last_name"
        # Add more field names from the Claim model as needed
    ]
    
    
    # Specify the fields you want to retrieve from the related models
    
    fields_to_select_hf = [
        "health_facility__name",
        # Add more field names from the related model as needed
    ]  
    claim = Claim.objects.\
        filter(**cleaned_get_params, validity_to=None)\
        .values(*fields_to_select_claim, * fields_to_select_insuree, *fields_to_select_hf)
    
    print(claim.query.__str__())
    k = stringify_querset(claim)
    return query_to_excel_download_helper(k)
    # Fetch data from the queryset
    claim_data = list(claim.values())  # Convert queryset to list of dictionaries
    
    # Convert data to DataFrame
    df = pd.DataFrame(claim_data)
    
    # Convert DataFrame to Excel
    excel_buffer = io.BytesIO()  # Create a file-like object
    df.to_excel(excel_buffer, index=False)  # Write DataFrame to the file-like object
    
    # Prepare HttpResponse with Excel content for download
    excel_buffer.seek(0)  # Move the cursor to the start of the buffer
    response = HttpResponse(excel_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="claim_data.xlsx"'
    
    return response
    cleaned_get_params = {key: value[0] if isinstance(value, list) and len(value) == 1 else value for key, value in request.GET.items()}
    claim = Claim.objects.filter(**cleaned_get_params)
    print("claimn", str((claim.query)))

    return query_to_excel_download_helper(str(claim.query))
    # Extracting all parameters from the URL
    parent_location_params = [
        value
        for key, value in request.GET.items()
        if key.startswith("parent_location_")
    ]
    chfid = request.GET.get("chfid")
    last_name = request.GET.get("last_name")
    given_name = request.GET.get("given_name")
    gender = request.GET.get("gender")
   

    # Assuming `parent_location_params` is a list of UUID strings
    parent_location_filters = " OR ".join(
        [
            f'("tblLocations"."LocationUUID" = \'{location_id}\')'
            for location_id in parent_location_params
        ]
    )

    # Assuming `chfid`, `last_name`, `given_name`, and `gender` are provided as string values
    chfid_filter = f'("tblInsuree"."CHFID" = \'{chfid}\')' if chfid else ""
    last_name_filter = (
        f'("tblInsuree"."LastName" = \'{last_name}\')' if last_name else ""
    )
    given_name_filter = (
        f'("tblInsuree"."OtherNames" = \'{given_name}\')' if given_name else ""
    )
    gender_filter = f'("tblInsuree"."Gender" = \'{gender}\')' if gender else ""

    # Concatenate all filters
    filters = [
        filter
        for filter in [
            parent_location_filters,
            chfid_filter,
            last_name_filter,
            given_name_filter,
            gender_filter,
        ]
        if filter
    ]
    where_clause = " AND ".join(filters) if filters else "1=1"

    # Construct the SQL query
    sql_query = f"""
        SELECT 
            "tblInsuree"."CHFID",
            "tblInsuree"."LastName",
            "tblInsuree"."OtherNames", 
            "tblInsuree"."Gender", 
            "tblInsuree"."Email", 
            "tblInsuree"."Phone", 
            CAST("tblInsuree"."DOB" AS DATE),
            "tblInsuree"."status"
        FROM 
            "tblInsuree"
        INNER JOIN 
            "tblFamilies" ON "tblInsuree"."FamilyID" = "tblFamilies"."FamilyID"
        INNER JOIN 
            "tblLocations" ON "tblFamilies"."LocationId" = "tblLocations"."LocationId"
        WHERE 
            {where_clause} 
            AND "tblInsuree"."ValidityTo" IS NULL;
    """

    print(sql_query)
    # if not request.user:
    #     raise PermissionDenied(_("unauthorized"))
    query_string = f"""
                     {sql_query}
                   """
    return query_to_excel_download_helper(query_string)



@api_view(["GET"])
def InsureeToExcelExport(request):
    print("request", request.GET)

    # Extracting all parameters from the URL
    parent_location_params = [
        value
        for key, value in request.GET.items()
        if key.startswith("parent_location_")
    ]
    chfid = request.GET.get("chfid")
    last_name = request.GET.get("last_name")
    given_name = request.GET.get("given_name")
    gender = request.GET.get("gender")
    """
    # Initialize a queryset with all Insuree objects
    insuree_queryset = Insuree.objects.all()

    # Apply filters based on parameters
    if parent_location_params:
        # Filter based on parent locations
        for index, location_id in enumerate(parent_location_params):
            print("locationid", location_id)
            _location = Location.objects.filter(uuid=location_id).first()
            print("_location", _location)
            insuree_queryset = insuree_queryset.filter(family__location__id=_location.id)

    if chfid:
        # Filter based on chfid
        insuree_queryset = insuree_queryset.filter(chf_id=chfid)

    if last_name:
        # Filter based on last_name
        insuree_queryset = insuree_queryset.filter(last_name=last_name)

    if given_name:
        # Filter based on given_name
        insuree_queryset = insuree_queryset.filter(other_names=given_name)

    if gender:
        # Filter based on gender
        insuree_queryset = insuree_queryset.filter(gender=gender)

    queryset_string = str(insuree_queryset.query)
    print("query", insuree_queryset.query)
    """

    # Assuming `parent_location_params` is a list of UUID strings
    parent_location_filters = " OR ".join(
        [
            f'("tblLocations"."LocationUUID" = \'{location_id}\')'
            for location_id in parent_location_params
        ]
    )

    # Assuming `chfid`, `last_name`, `given_name`, and `gender` are provided as string values
    chfid_filter = f'("tblInsuree"."CHFID" = \'{chfid}\')' if chfid else ""
    last_name_filter = (
        f'("tblInsuree"."LastName" = \'{last_name}\')' if last_name else ""
    )
    given_name_filter = (
        f'("tblInsuree"."OtherNames" = \'{given_name}\')' if given_name else ""
    )
    gender_filter = f'("tblInsuree"."Gender" = \'{gender}\')' if gender else ""

    # Concatenate all filters
    filters = [
        filter
        for filter in [
            parent_location_filters,
            chfid_filter,
            last_name_filter,
            given_name_filter,
            gender_filter,
        ]
        if filter
    ]
    where_clause = " AND ".join(filters) if filters else "1=1"

    # Construct the SQL query
    sql_query = f"""
        SELECT 
            "tblInsuree"."CHFID",
            "tblInsuree"."LastName",
            "tblInsuree"."OtherNames", 
            "tblInsuree"."Gender", 
            "tblInsuree"."Email", 
            "tblInsuree"."Phone", 
            CAST("tblInsuree"."DOB" AS DATE),
            "tblInsuree"."status"
        FROM 
            "tblInsuree"
        INNER JOIN 
            "tblFamilies" ON "tblInsuree"."FamilyID" = "tblFamilies"."FamilyID"
        INNER JOIN 
            "tblLocations" ON "tblFamilies"."LocationId" = "tblLocations"."LocationId"
        WHERE 
            {where_clause} 
            AND "tblInsuree"."ValidityTo" IS NULL;
    """

    print(sql_query)
    if not request.user:
        raise PermissionDenied(_("unauthorized"))
    query_string = f"""
                     {sql_query}
                   """
    return query_to_excel_download_helper(query_string)
    # print('request.get', request.GET)
    print("request user", request.user.i_user.health_facility_id)

    hf_id = request.GET.get("hf_id", None)
    print("hf_id", hf_id)
    if hf_id:
        healthfacility_id = HealthFacility.objects.filter(code=hf_id).first().pk
    else:
        healthfacility_id = None
    print("healthfacility_id", healthfacility_id)
    if not hf_id:
        print("request.get", request.GET)
        health_facility_id = request.user.i_user.health_facility_id
        if request.user.i_user.health_facility_id:
            hf_id = HealthFacility.objects.filter(pk=health_facility_id).first().code
    claim_status = request.GET.get("claim_status")
    insuree_chfid = request.GET.get("chfid", None)
    fromDate = request.GET.get("from_date", "")  # datetime.now().strftime('%Y-%m-%d'))
    todate = request.GET.get("to_date", "")  # datetime.now().strftime('%Y-%m-%d'))
    claim_no = request.GET.get("claim_no")
    payment_status = request.GET.get("payment_status")
    product_code = request.GET.get("product")
    if product_code == "SSF0001":
        product_id = 2
    elif product_code == "SSF0002":
        product_id = 1
    else:
        product_id = None

    """
    # print(req_data['to_data'])
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="claim_payment_status.xls"'

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Claims Payment Status')

    # Sheet header, first row
    row_num = 0

    font_style = xlwt.XFStyle()
    font_style.font.bold = True
    headers = ['Report Date',datetime.now().strftime('%Y-%m-%d'),'From Date',fromDate,'To Date',todate]
    for col_num in range(len(headers)):
        ws.write(row_num, col_num, headers[col_num], font_style)
    row_num+=1
    columns = ['Code','Insuree SSID','Insuree Name','Scheme Name','Sub Scheme','Claim Date', 'Claimed', 'Approved', 'Claim Status','Payment Status','Action Date','Payment Remarks' ]

    for col_num in range(len(columns)):
        ws.write(row_num, col_num, columns[col_num], font_style)

    # Sheet body, remaining rows
    font_style = xlwt.XFStyle()
    statuses = {
                1: "Rejected",
                2: "Entered",
                4: "Checked",
                6: "Recommended",
                8: "Processed",
                9: "Forwarded",
                16: "Valuated",
            }
    payment_statuses = {
                0: "Booked",
                1: "Rejected",
                2: "Paid",
            }
    # a = useDict.get(useBy,None)
    hf = HealthFacility.objects.all().filter(code = hf_id,validity_to = None).first()
    rows = Claim.objects\
        .select_related('product','subProduct','insuree')\
        .filter(health_facility=hf,date_claimed__gte = fromDate,date_claimed__lte=todate,validity_to=None)\
        .order_by('date_claimed')
    # print('query',rows.query)
    if insuree_no:
        insuree = Insureee.objects.filter(chf_id=insuree_no,validity_to=None).first() 
        rows = rows.filter(insuree= insuree)
    l = []
    """
    try:
        # print('queries',rows.query)
        from .query_string_report import construct_query_string

        columns = [
            "Code",
            "Insuree SSID",
            "Insuree Name",
            "Scheme Name",
            "Sub Scheme",
            "Claim Date",
            "Claimed",
            "Approved",
            "Claim Status",
            "Payment Status",
            "Action Date",
            "Payment Remarks",
        ]

        query_string = f""" 
              SELECT 
              tblclaim.ClaimCode, 
              tblclaim.Claimed as Claimed,
              CONCAT(
                tblinsuree.OtherNames, ' ', tblInsuree.LastName
              ) as Insuree, 
              tblInsuree.CHFID,
              SELECT CONCAT(CAST(tblclaim.DateClaimed AS VARCHAR), '.') AS DateClaimed
              tblProduct.ProductName, 
              tblhf.HFName, 
              case when tblClaim.ClaimStatus=1 then 'Rejected'
               when tblClaim.ClaimStatus=2 then 'Entered'
               when tblClaim.ClaimStatus=4 then 'Checked'
               when tblClaim.ClaimStatus=6 then 'Recommended'
                when tblClaim.ClaimStatus=8 then 'Processe'
               when tblClaim.ClaimStatus=9 then 'Forwaded'
               when tblClaim.ClaimStatus=16 then 'Valuated'
              else ''
               END as ApprovalStatus,
               tblClaim.Claimed as Entered,
              tblClaim.approved as Approved, 
              case when tblClaim.PaymentStatus=0 then 'Booked'
               when tblClaim.PaymentStatus=1 then 'Reject'
               when tblClaim.PaymentStatus=2 then 'Paid'
              
              else 'Idle'
               END as 'Payment Status',
              CONCAT(tblclaim.paymentDate, '.') as PaymentDate
            FROM 
              [tblClaim] 
              INNER JOIN [tblInsuree] ON (
                [tblClaim].[InsureeID] = [tblInsuree].[InsureeID]
              ) 
              LEFT OUTER JOIN [sosys_subproduct] ON (
                [tblClaim].[subProduct_id] = [sosys_subproduct].[id]
              ) 
              LEFT OUTER JOIN [tblProduct] ON (
                [tblClaim].[product_id] = [tblProduct].[ProdID]
              ) 
              JOIN [tblHF] on (
                [tblClaim].[HFID] =  [tblHF].[HfID]
              )
        """
        if fromDate and todate:
            print("719")
            query_string += f"""

            WHERE 
              (
                [tblClaim].[DateClaimed] >= '{fromDate}' 
                AND [tblClaim].[DateClaimed] <= '{todate}'
                )
            """
        if not fromDate:
            print("728")
            if todate:
                print("730")
                query_string += f""" 
                    WHERE [tblClaim].[DateClaimed] <= '{todate}' 
                """
        if not todate:
            print("735")
            if fromDate:
                print("737")
                query_string += f""" 
                    WHERE [tblClaim].[DateClaimed] >= '{fromDate}' 
                """
        if not fromDate:
            if not todate:
                print("742")
                query_string += f""" where 1=1"""
        if healthfacility_id or request.user.i_user.health_facility_id:
            query_string += f""" AND [tblClaim].[HFID] = {healthfacility_id if healthfacility_id else request.user.i_user.health_facility_id}"""  # if healthfacility_id else request.user.i_user.get('health_facility_id')}"""

        if product_id:
            query_string += f""" 

            AND tblClaim.product_id = {product_id}
            """
        if insuree_chfid:
            query_string += f""" 
                    AND tblInsuree.CHFID = '{insuree_chfid}' 
                """
        if claim_no:
            query_string += f""" 
                    AND tblclaim.ClaimCode = '{claim_no}' 
                """

        if claim_status:
            query_string += f""" 
                    AND tblclaim.ClaimStatus = '{claim_status}' 
                """
        if payment_status:
            query_string += f""" 
                    AND tblclaim.paymentStatus = '{payment_status}' 
                """
        else:
            query_string += f""" 
                 AND [tblClaim].[ValidityTo] IS NULL
               
            ORDER BY 
              [tblClaim].[DateClaimed] ASC

        """

        print("query String", query_string)
        return query_to_excel_download_helper(query_string)
    except Exception:
        print(traceback.format_exc())



