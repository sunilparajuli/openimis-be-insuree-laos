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
from django.core.exceptions import PermissionDenied
from .models import Insuree
from claim.models import Claim
import pandas as pd
import io 
from django.db import connection
import xlsxwriter
from insuree.apps import InsureeConfig

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("utf8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type="application/pdf")
    return None


class PrintPdfSlipView(APIView, PDFTemplateView):

    filename =  InsureeConfig.membership_slip_name#"slip_forms.pdf"

    template_name = InsureeConfig.get_os_architecture() #the wkhtmltopdf, acts differently in different OS, template replacement based on os type
    cmd_options = InsureeConfig.wkhtml_cmd_options_for_printing

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        if not request.user:#request.user.has_perm('<permission_name>'): #to do , add persmission, maybe admin user, default user only
            return HttpResponseForbidden("You do not have permission to access this resource.")
        return super(PrintPdfSlipView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from .models import Insuree, Family
        # import pdb;pdb.set_trace()
        if kwargs.get("type") == str(InsureeConfig.card_print_config.get('family')) or kwargs.get("type") == InsureeConfig.card_print_config.get('family'):
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
                "multiples": [1, 2] if insuree_families.count() <=12 else [1,2], #todo, if family count is greater than 12, need to print another with remaining member
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
                "multiples": [1, 2], #need config to print multiple times if no. of family members are large
                "chfid_array": chfid_array,
                "insuree": insuree,
            }
        context["title"] = "Slip Generation"

        # context["size"] = 400
        # context["results"] = sorted(matched_cases, key=lambda k: k['index'])
        return context




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
    output.close()
    return response




def stringify_querset(qs):
    sql, params = qs.query.sql_with_params()
    with connection.cursor() as cursor:
        return cursor.mogrify(sql, params)


@api_view(["GET"])
def claimToExcelExport(request):

    if not request.user: #todo, object level permission need to check
        raise PermissionDenied(_("unauthorized"))

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
        # Add more field names from the Insuree model as needed
    ]
    
    
    # Specify the fields you want to retrieve from the related models
    
    fields_to_select_hf = [
        "health_facility__name",
        # Add more field names from the related model as needed
    ]  
    claim = Claim.objects.\
        filter(**cleaned_get_params, validity_to=None)\
        .values(*fields_to_select_claim, * fields_to_select_insuree, *fields_to_select_hf)

    k = stringify_querset(claim)
    return query_to_excel_download_helper(k)
  


@api_view(["GET"])
def InsureeToExcelExport(request):
    # Extracting all parameters from the URL
    if not request.user:
        raise PermissionDenied(_("unauthorized"))

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
    query_string = f"""
                     {sql_query}
                   """
    return query_to_excel_download_helper(query_string)

