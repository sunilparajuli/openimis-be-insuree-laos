import graphene

from claim.apps import ClaimConfig
from core.gql.export_mixin import ExportableQueryMixin
from core.schema import signal_mutation_module_validate
from core.utils import filter_validity
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.dispatch import Signal
from graphene_django.filter import DjangoFilterConnectionField
import graphene_django_optimizer as gql_optimizer
from location.models import Location, LocationManager

from insuree.apps import InsureeConfig
from .models import FamilyMutation, InsureeMutation
from django.utils.translation import gettext as _
from location.apps import LocationConfig
from core.schema import OrderedDjangoFilterConnectionField, OfficerGQLType
from core.gql_queries import ValidationMessageGQLType
from policy.models import Policy

# We do need all queries and mutations in the namespace here.
from .gql_queries import *  # lgtm [py/polluting-import]
from .gql_mutations import *  # lgtm [py/polluting-import]
from .signals import signal_before_insuree_policy_query, _read_signal_results, \
    signal_before_family_query, signal_before_insuree_search_query
from django.db import transaction


def family_fk(arg):
    return arg.startswith("members_") or arg.startswith("head_insuree_")


class FamiliesConnectionField(OrderedDjangoFilterConnectionField):
    @classmethod
    def resolve_queryset(
            cls, connection, iterable, info, args, filtering_args, filterset_class
    ):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        qs = super(FamiliesConnectionField, cls).resolve_queryset(
            connection, iterable, info,
            {k: args[k] for k in args.keys() if not k.startswith(
                "members_") and not k.startswith("head_insuree_")},
            filtering_args,
            filterset_class
        )
        head_insuree_filters = {
            k: args[k] for k in args.keys() if k.startswith("head_insuree__")}
        members_filters = {k: args[k]
                           for k in args.keys() if k.startswith("members__")}
        if len(head_insuree_filters) or len(members_filters):
            qs = qs._next_is_sticky()
        if len(head_insuree_filters):
            qs = qs.filter(
                Q(head_insuree__validity_to__isnull=True), **head_insuree_filters)
        if len(members_filters):
            qs = qs.filter(Q(members__validity_to__isnull=True),
                           **members_filters)
        return OrderedDjangoFilterConnectionField.orderBy(qs, args)


def createInsureeInteroperability(chfid):
    from insuree.models import Insuree, Family, InsureePolicy
    from policy.models import Policy
    from datetime import datetime,timedelta
    import requests
    try:
        # import pdb;pdb.set_trace()
        # Set your Supabase URL and API Key
        supabase_url = 'https://jqglqrprytirczvpotug.supabase.co'
        supabase_api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpxZ2xxcnByeXRpcmN6dnBvdHVnIiwicm9sZSI6ImFub24iLCJpYXQiOjE2NjE5NTA0OTYsImV4cCI6MTk3NzUyNjQ5Nn0.t8s2oJm-eqXxRDiyl8Pe66gWY7CwZdlhLx8q5_OM1kI'

        # Example endpoint to fetch data from a table
        endpoint = f'{supabase_url}/rest/v1/insurees'

        # Set headers with the API Key
        headers = {
            'apikey': supabase_api_key,
            'Content-Type': 'application/json',
        }

        # Make a GET request to fetch data from Supabase API
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()  # Raise exception for any HTTP error (e.g., 404, 500)

        # Check if the request was successful
        if response.status_code == 200:
            insurees = response.json()
            with transaction.atomic():
                for insuree_data in insurees:
                    insurance_id = insuree_data.get('insurance_no')
                    # print("insurance_id", "insuree_data", insuree_data, insuree_data.get('Insurance_no'), "insuree_data_no",insuree_data.get('insurance_no'))
                    if chfid == insurance_id:
                        # import pdb;pdb.set_trace()
                        # Create Insuree and Family objects

                        family = Family.objects.create(
                            audit_user_id=-1,
                            head_insuree=Insuree.objects.first()
                        )
                        insuree = Insuree.objects.create(
                            other_names=insuree_data['first_name'],  # Replace with appropriate fields from the JSON
                            last_name=insuree_data['last_name'],
                            family=family,
                            chf_id=chfid,
                            audit_user_id=-1,
                            card_issued=False


                            # Add other fields as needed
                        )
                        family.head_insuree = insuree
                        family.save()
                        insuree.family=family
                        insuree.save()
                        InsureePolicy.objects.create(
                            insuree=insuree,
                            policy=Policy.objects.first(),
                            enrollment_date=datetime.now().date(),
                            start_date=datetime.now().date(),
                            effective_date=datetime.now().date(),
                            expiry_date=datetime.now().date()+timedelta(days=365),
                            audit_user_id=-1
                            # Add other fields as needed
                        )
                return 
    except:
        import traceback
        print(traceback.format_exc())
    return False

class Query(ExportableQueryMixin, graphene.ObjectType):
    exportable_fields = ['insurees']


    can_add_insuree = graphene.Field(
        graphene.List(graphene.String),
        family_id=graphene.Int(required=True),
        description="Checks that the specified family id is allowed to add more insurees (like a Policy limitation)"
    )
    insuree_genders = graphene.List(GenderGQLType)
    insurees = OrderedDjangoFilterConnectionField(
        InsureeGQLType,
        show_history=graphene.Boolean(),
        parent_location=graphene.String(),
        parent_location_level=graphene.Int(),
        client_mutation_id=graphene.String(),
        ignore_location=graphene.Boolean(),
        orderBy=graphene.List(of_type=graphene.String),
        additional_filters=graphene.JSONString()
    )
    identification_types = graphene.List(IdentificationTypeGQLType)
    educations = graphene.List(EducationGQLType)
    professions = graphene.List(ProfessionGQLType)
    family_types = graphene.List(FamilyTypeGQLType)
    confirmation_types = graphene.List(ConfirmationTypeGQLType)
    relations = graphene.List(RelationGQLType)
    insuree_status_reasons = DjangoFilterConnectionField(
        InsureeStatusReasonGQLType,
        str=graphene.String()
    )

    families = FamiliesConnectionField(
        FamilyGQLType,
        null_as_false_poverty=graphene.Boolean(),
        show_history=graphene.Boolean(),
        parent_location=graphene.String(),
        parent_location_level=graphene.Int(),
        client_mutation_id=graphene.String(),
        orderBy=graphene.List(of_type=graphene.String),
        additional_filter=graphene.JSONString(),
        officer=graphene.String()
    )
    family_members = OrderedDjangoFilterConnectionField(
        InsureeGQLType,
        family_uuid=graphene.String(required=True),
        orderBy=graphene.List(of_type=graphene.String),
    )
    insuree_officers = DjangoFilterConnectionField(OfficerGQLType)
    insuree_policy = OrderedDjangoFilterConnectionField(
        InsureePolicyGQLType,
        parent_location=graphene.String(),
        parent_location_level=graphene.Int(),
        orderBy=graphene.List(of_type=graphene.String),
        additional_filter=graphene.JSONString(),
    )
    insuree_number_validity = graphene.Field(
        ValidationMessageGQLType,
        insuree_number=graphene.String(required=True),
        description="Checks that the specified insuree number is valid"
    )

    def resolve_insuree_number_validity(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insurees_perms):
            raise PermissionDenied(_("unauthorized"))
        errors = validate_insuree_number(kwargs['insuree_number'])
        if errors:
            return ValidationMessageGQLType(False, errors[0]['errorCode'], errors[0]['message'])
        else:
            return ValidationMessageGQLType(True, 0, "")

    def resolve_can_add_insuree(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_perms):
            raise PermissionDenied(_("unauthorized"))
        family = Family.objects.get(id=kwargs.get('family_id'))
        warnings = []
        policies = family.policies\
            .filter(validity_to__isnull=True)\
            .exclude(status__in=[Policy.STATUS_EXPIRED, Policy.STATUS_SUSPENDED])
        for policy in policies:
            if not policy.can_add_insuree():
                warnings.append(
                    _("insuree.validation.policy_above_max_members")
                    % {
                        "product_code": policy.product.code,
                        "start_date": policy.start_date,
                        "max": policy.product.max_members,
                        "count": family.members.filter(
                            validity_to__isnull=True
                        ).count(),
                    }
                )
        return warnings

    def resolve_insuree_genders(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_perms):
            raise PermissionDenied(_("unauthorized"))
        return Gender.objects.order_by('sort_order').all()

    def resolve_insurees(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insurees_perms):
            raise PermissionDenied(_("unauthorized"))
        filters = []
        additional_filter = kwargs.get('additional_filters', None)
        chf_id = kwargs.get('chf_id')
        insuree = Insuree.objects.filter(chf_id=chf_id, validity_to=None).first()
        if not insuree:
            createInsureeInteroperability(chf_id)
            # filters.append(Q(chf_id=chf_id))
    
        if chf_id is not None:
            filters.append(Q(chf_id=chf_id))
        if additional_filter:
            filters_from_signal = _insuree_insuree_additional_filters(
                sender=self, additional_filter=additional_filter, user=info.context.user
            )
            filters.extend(filters_from_signal)
        show_history = kwargs.get('show_history', False)
        if not show_history and not kwargs.get('uuid', None):
            filters += filter_validity(**kwargs)
        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(
                Q(mutations__mutation__client_mutation_id=client_mutation_id))
        parent_location = kwargs.get('parent_location')
        if parent_location is not None:
            parent_location_level = kwargs.get('parent_location_level')
            if parent_location_level is None:
                raise ValueError(
                    "Missing parentLocationLevel argument when filtering on parentLocation")
            f = "uuid"
            for i in range(len(LocationConfig.location_types) - parent_location_level - 1):
                f = "parent__" + f
            current_village = "current_village__" + f
            family_location = "family__location__" + f
            filters += [(Q(current_village__isnull=False) & Q(**{current_village: parent_location})) |
                        (Q(current_village__isnull=True) & Q(**{family_location: parent_location}))]

        if not info.context.user._u.is_imis_admin and (kwargs.get('ignore_location') == False or kwargs.get('ignore_location') is None):
            # Limit the list by the logged in user location mapping
            filters += [Q(LocationManager().build_user_location_filter_query(info.context.user._u, prefix='current_village__parent__parent', loc_types=['D']) |
                        LocationManager().build_user_location_filter_query(info.context.user._u, prefix='family__location__parent__parent', loc_types=['D']))]

        return gql_optimizer.query(Insuree.objects.filter(*filters).all(), info)

    def resolve_family_members(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_family_members):
            raise PermissionDenied(_("unauthorized"))
        family = Family.objects.get(Q(uuid=(kwargs.get('family_uuid'))))
        return Insuree.objects.filter(
            Q(family=family),
            *filter_validity(**kwargs)
        ).order_by('-head', 'dob')

    def resolve_educations(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        return Education.objects.order_by('sort_order').all()

    def resolve_professions(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        return Profession.objects.order_by('sort_order').all()

    def resolve_identification_types(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        return IdentificationType.objects.order_by('sort_order').all()

    def resolve_confirmation_types(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        return ConfirmationType.objects.order_by('sort_order').all()

    def resolve_relations(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        return Relation.objects.order_by('sort_order').all()

    def resolve_family_types(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        return FamilyType.objects.order_by('sort_order').all()

    def resolve_families(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))

        filters = []
        additional_filter = kwargs.get('additional_filter', None)
        if additional_filter:
            filters_from_signal = _family_additional_filters(
                sender=self, additional_filter=additional_filter, user=info.context.user
            )
            filters.extend(filters_from_signal)

        officer = kwargs.get('officer', None)
        if officer:
            officer_policies_families = Policy.objects.filter(
                officer__uuid=(officer)).values_list('family', flat=True)
            filters.append(Q(id__in=officer_policies_families))

        null_as_false_poverty = kwargs.get('null_as_false_poverty')
        if null_as_false_poverty is not None:
            filters += [Q(poverty=True)] if null_as_false_poverty else [
                Q(poverty=False) | Q(poverty__isnull=True)]
        show_history = kwargs.get('show_history', False)
        if not show_history:
            filters += filter_validity(**kwargs)
        client_mutation_id = kwargs.get("client_mutation_id", None)
        if client_mutation_id:
            filters.append(
                Q(mutations__mutation__client_mutation_id=client_mutation_id))
        parent_location = kwargs.get('parent_location')
        if parent_location is not None:
            parent_location_level = kwargs.get('parent_location_level')
            if parent_location_level is None:
                raise NotImplementedError(
                    "Missing parentLocationLevel argument when filtering on parentLocation")
            f = "uuid"
            for i in range(len(LocationConfig.location_types) - parent_location_level - 1):
                f = "parent__" + f
            f = "location__" + f
            filters += [Q(**{f: parent_location})]

        # Limit the list by the logged in user location mapping
        if not info.context.user._u.is_imis_admin:
            filters += [LocationManager().build_user_location_filter_query(info.context.user._u, prefix= 'location__parent__parent', loc_types = ['D'])]

        # Duplicates cannot be removed with distinct, as TEXT field is not comparable
        ids = Family.objects.filter(*filters).values_list('id')
        dinstinct_queryset = Family.objects.filter(id__in=ids)
        return gql_optimizer.query(dinstinct_queryset.all(), info)

    def resolve_insuree_officers(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_officers_perms):
            raise PermissionDenied(_("unauthorized"))

    def resolve_insuree_policy(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_policy_perms):
            raise PermissionDenied(_("unauthorized"))
        filters = []
        additional_filter = kwargs.get('additional_filter', None)
        # go to process additional filter only when this arg of filter was passed into query
        if additional_filter:
            filters_from_signal = _insuree_additional_filters(
                sender=self, additional_filter=additional_filter, user=info.context.user
            )
            # check if there is filter from signal (perms will be checked in the signals)
            if len(filters_from_signal) == 0:
                raise PermissionDenied(_("unauthorized"))
            filters.extend(filters_from_signal)
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_policy_perms):
            raise PermissionDenied(_("unauthorized"))
        parent_location = kwargs.get('parent_location')
        if parent_location is not None:
            parent_location_level = kwargs.get('parent_location_level')
            if parent_location_level is None:
                raise NotImplementedError(
                    "Missing parentLocationLevel argument when filtering on parentLocation")
            f = "uuid"
            for i in range(len(LocationConfig.location_types) - parent_location_level - 1):
                f = "parent__" + f
            current_village = "insuree__current_village__" + f
            family_location = "insuree__family__location__" + f
            filters += [(Q(insuree__current_village__isnull=False) & Q(**{current_village: parent_location})) |
                        (Q(insuree__current_village__isnull=True) & Q(**{family_location: parent_location}))]
        return gql_optimizer.query(InsureePolicy.objects.filter(*filters).all(), info)


class Mutation(graphene.ObjectType):
    create_family = CreateFamilyMutation.Field()
    update_family = UpdateFamilyMutation.Field()
    delete_families = DeleteFamiliesMutation.Field()
    create_insuree = CreateInsureeMutation.Field()
    update_insuree = UpdateInsureeMutation.Field()
    delete_insurees = DeleteInsureesMutation.Field()
    remove_insurees = RemoveInsureesMutation.Field()
    set_family_head = SetFamilyHeadMutation.Field()
    change_insuree_family = ChangeInsureeFamilyMutation.Field()
    upload_excel = UploadExcel.Field()


def on_family_mutation(kwargs, k='uuid'):
    family_uuid = kwargs['data'].get('uuid', None)
    if not family_uuid:
        return []
    impacted_family = Family.objects.filter(Q(uuid=(family_uuid))).first()
    if impacted_family is None:
        return []
    FamilyMutation.objects.create(
        family=impacted_family, mutation_id=kwargs['mutation_log_id'])
    return []


def on_families_mutation(kwargs):
    uuids = kwargs['data'].get('uuids', [])
    if not uuids:
        uuid = kwargs['data'].get('uuid', None)
        uuids = [uuid] if uuid else []
    if not uuids:
        return []
    impacted_families = Family.objects.filter(uuid__in=uuids).all()
    for family in impacted_families:
        FamilyMutation.objects.create(
            family=family, mutation_id=kwargs['mutation_log_id'])
    return []


def on_insuree_mutation(kwargs, k='uuid'):
    insuree_uuid = kwargs['data'].get('uuid', None)
    if not insuree_uuid:
        return []
    impacted_insuree = Insuree.objects.filter(Q(uuid=(insuree_uuid))).first()
    if impacted_insuree is None:
        return []
    InsureeMutation.objects.create(
        insuree=impacted_insuree, mutation_id=kwargs['mutation_log_id'])
    return []


def on_insurees_mutation(kwargs):
    uuids = kwargs['data'].get('uuids', [])
    if not uuids:
        uuid = kwargs['data'].get('uuid', None)
        uuids = [uuid] if uuid else []
    if not uuids:
        return []
    impacted_insurees = Insuree.objects.filter(uuid__in=uuids).all()
    for insuree in impacted_insurees:
        InsureeMutation.objects.create(
            insuree=insuree, mutation_id=kwargs['mutation_log_id'])
    return []


def on_family_and_insurees_mutation(kwargs):
    family = on_family_mutation(kwargs)
    insurees = on_insurees_mutation(kwargs)
    return family + insurees


def on_family_and_insuree_mutation(kwargs):
    family = on_family_mutation(kwargs, 'family_uuid')
    insuree = on_insuree_mutation(kwargs, 'insuree_uuid')
    return family + insuree


def on_mutation(sender, **kwargs):
    return {
        CreateFamilyMutation._mutation_class: on_family_mutation,
        UpdateFamilyMutation._mutation_class: on_family_mutation,
        DeleteFamiliesMutation._mutation_class: on_families_mutation,
        CreateInsureeMutation._mutation_class: on_insurees_mutation,
        UpdateInsureeMutation._mutation_class: on_insurees_mutation,
        DeleteInsureesMutation._mutation_class: on_family_and_insurees_mutation,
        RemoveInsureesMutation._mutation_class: on_family_and_insurees_mutation,
        SetFamilyHeadMutation._mutation_class: on_family_mutation,
        ChangeInsureeFamilyMutation._mutation_class: on_family_and_insuree_mutation,
    }.get(sender._mutation_class, lambda x: [])(kwargs)


def bind_signals():
    signal_mutation_module_validate["insuree"].connect(on_mutation)


def _insuree_additional_filters(sender, additional_filter, user):
    return _get_additional_filter(sender, additional_filter, user, signal_before_insuree_policy_query)

def _insuree_insuree_additional_filters(sender, additional_filter, user):
    return _get_additional_filter(sender, additional_filter, user, signal_before_insuree_search_query)


def _family_additional_filters(sender, additional_filter, user):
    return _get_additional_filter(sender, additional_filter, user, signal_before_family_query)


def _get_additional_filter(sender, additional_filter, user, signal: Signal):
    # function to retrieve additional filters from signal
    filters_from_signal = []
    if additional_filter:
        # send signal to append additional filter
        results_signal = signal.send(
            sender=sender, additional_filter=additional_filter, user=user,
        )
        filters_from_signal = _read_signal_results(results_signal)
    return filters_from_signal
