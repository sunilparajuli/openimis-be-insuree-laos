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


def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("utf8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type="application/pdf")
    return None


def print_membership(request, family_uuid, **kwargs):
    context = {}
    pdf = render_to_pdf("membership.html", context)
    return HttpResponse(pdf, content_type="application/pdf")
    # return render(request, 'final_invoice.html',context)
    return HttpResponse("Invalid invoice Type", status=status.HTTP_400_BAD_REQUEST)


class PrintPdfSlipView(APIView, PDFTemplateView):
    filename = "slip_forms.pdf"
    template_name = "membership.html"
    cmd_options = {
        # 'margin-top': 3,
        "orientation": "Portrait",
        "page-size": "A4",
        "disable-smart-shrinking": None,
        "no-outline": None,
        "encoding": "UTF-8",
        "enable-local-file-access": None,
        "quiet": False,
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
                "multiples": [1, 2],
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
        {"bold": True, "border": True, "bg_color": "yellow"}
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


@api_view(["GET"])
def InsureeToExcelExport(request):
    if not request.user:
        raise PermissionDenied(_("unauthorized"))
    filters = request.GET.get("")
    query_string = """
                     SELECT * FROM public."tblInsuree" LIMIT 1000;   
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
              CONCAT(
                tblinsuree.OtherNames, ' ', tblInsuree.LastName
              ) as Insuree, 
              tblInsuree.CHFID,
              CONCAT(tblclaim.DateClaimed, '.') as DateClaimed, 
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
    # for row in rows:
    #     data = (
    #         row.code,
    #         row.insuree.chf_id if row.insuree else "No Insuree found",
    #         row.insuree.other_names +' '+row.insuree.last_name if row.insuree else "No Insuree found",
    #         "No Scheme" if not row.product else row.product.name,
    #         "No Sub Scheme" if not row.subProduct else row.subProduct.sch_name_eng,
    #         row.date_claimed.strftime('%Y-%m-%d') if row.date_claimed else "",
    #         row.claimed,
    #         row.approved,
    #         statuses.get(row.status,"null"),
    #         payment_statuses.get(row.payment_status,"Booked") if row.status != 1 else "Reversed",
    #         row.payment_date.strftime('%Y-%m-%d') if row.payment_date else "",
    #         row.payment_remarks
    #         )
    #     l.append(data)
    # print('l____query', l)
    # for row in l:
    #     row_num += 1
    #     for col_num in range(len(row)):
    #         ws.write(row_num, col_num, row[col_num], font_style)

    # wb.save(response)
    # return response
