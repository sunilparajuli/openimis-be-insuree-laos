import graphene
from graphene_django import DjangoObjectType

from .apps import InsureeConfig
from .models import Insuree, InsureePhoto, Education, Profession, Gender, IdentificationType, \
    Family, FamilyType, ConfirmationType, Relation, InsureePolicy, FamilyMutation, InsureeMutation, InsureeStatusReason
from location.schema import LocationGQLType
from policy.gql_queries import PolicyGQLType
from core import prefix_filterset, filter_validity, ExtendedConnection
from django.utils.translation import gettext as _
from django.core.exceptions import PermissionDenied

from .services import load_photo_file


class GenderGQLType(DjangoObjectType):
    class Meta:
        model = Gender
        filter_fields = {
            "code": ["exact"]
        }


class PhotoGQLType(DjangoObjectType):
    photo = graphene.String()

    def resolve_photo(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_photo_perms):
            raise PermissionDenied(_("unauthorized"))
        if self.photo:
            return self.photo
        elif InsureeConfig.insuree_photos_root_path and self.folder and self.filename:
            return load_photo_file(self.folder, self.filename)
        return None

    class Meta:
        model = InsureePhoto
        filter_fields = {
            "id": ["exact"]
        }


class IdentificationTypeGQLType(DjangoObjectType):
    class Meta:
        model = IdentificationType
        filter_fields = {
            "code": ["exact"]
        }


class EducationGQLType(DjangoObjectType):
    class Meta:
        model = Education
        filter_fields = {
            "id": ["exact"]
        }

        exclude_fields = ('insurees',)


class ProfessionGQLType(DjangoObjectType):
    class Meta:
        model = Profession
        filter_fields = {
            "id": ["exact"]
        }


class FamilyTypeGQLType(DjangoObjectType):
    class Meta:
        model = FamilyType
        filter_fields = {
            "code": ["exact"]
        }


class ConfirmationTypeGQLType(DjangoObjectType):
    class Meta:
        model = ConfirmationType
        filter_fields = {
            "code": ["exact"]
        }


class RelationGQLType(DjangoObjectType):
    class Meta:
        model = Relation
        filter_fields = {
            "code": ["exact"]
        }


class InsureeStatusReasonGQLType(DjangoObjectType):
    status_type = graphene.String(required=False)

    class Meta:
        model = InsureeStatusReason
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "code": ["exact"],
            "insuree_status_reason": ["exact", 'icontains', 'istartswith'],
            "status_type": ["exact"]
        }
        connection_class = ExtendedConnection


class InsureeGQLType(DjangoObjectType):
    age = graphene.Int(source='age')
    client_mutation_id = graphene.String()
    photo = PhotoGQLType()
    insuree_sso = graphene.Boolean()
    
    def resolve_insuree_sso(self, info):
        import requests
        import os
        try:
            # Set your Supabase URL and API Key
            supabase_url = 'https://jqglqrprytirczvpotug.supabase.co'
            supabase_api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpxZ2xxcnByeXRpcmN6dnBvdHVnIiwicm9sZSI6ImFub24iLCJpYXQiOjE2NjE5NTA0OTYsImV4cCI6MTk3NzUyNjQ5Nn0.t8s2oJm-eqXxRDiyl8Pe66gWY7CwZdlhLx8q5_OM1kI'

            # Example endpoint to fetch data from a table
            endpoint = f'{supabase_url}/rest/v1/sso'

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
                # Check if self.chf_id matches any insurance ID in the insurees list
                for insuree in insurees:
                    if self.chf_id == insuree.get('Insurance_id'):
                        return True  # Return True if match found
            return False  # Return False if no match found or API response was not 200
        except requests.RequestException as e:
            print("Error fetching data from the API:", e)

    

    def resolve_current_village(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_perms):
            raise PermissionDenied(_("unauthorized"))
        if "location_loader" in info.context.dataloaders and self.current_village_id:
            return info.context.dataloaders["location_loader"].load(
                self.current_village_id
            )
        return self.current_village

    def resolve_family(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_perms):
            raise PermissionDenied(_("unauthorized"))
        if "family_loader" in info.context.dataloaders and self.family_id:
            return info.context.dataloaders["family_loader"].load(self.family_id)
        return self.family

    def resolve_health_facility(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_perms):
            raise PermissionDenied(_("unauthorized"))
        if "health_facililty" in info.context.dataloaders and self.health_facility_id:
            return info.context.dataloaders["health_facility"].load(
                self.health_facility_id
            )
        return self.health_facility

    def resolve_photo(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_perms):
            raise PermissionDenied(_("unauthorized"))
        return self.photo

    class Meta:
        model = Insuree
        filter_fields = {
            "uuid": ["exact","iexact"],
            "chf_id": ["exact", "istartswith", "icontains", "iexact"],
            "last_name": ["exact", "istartswith", "icontains", "iexact"],
            "other_names": ["exact", "istartswith", "icontains", "iexact"],
            "email": ["exact", "istartswith", "icontains", "iexact", "isnull"],
            "phone": ["exact", "istartswith", "icontains", "iexact", "isnull"],
            "dob": ["exact", "lt", "lte", "gt", "gte", "isnull"],
            "head": ["exact"],
            "passport": ["exact", "istartswith", "icontains", "iexact", "isnull"],
            "gender__code": ["exact", "isnull"],
            "marital": ["exact", "isnull"],
            "status": ["exact"],
            "validity_from": ["exact", "lt", "lte", "gt", "gte", "isnull"],
            "validity_to": ["exact", "lt", "lte", "gt", "gte", "isnull"],
            **prefix_filterset("photo__", PhotoGQLType._meta.filter_fields),
            "photo": ["isnull"],
            "family": ["isnull"],
            **prefix_filterset("gender__", GenderGQLType._meta.filter_fields)
        }
        interfaces = (graphene.relay.Node,)
        connection_class = ExtendedConnection

    def resolve_client_mutation_id(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_insuree_perms):
            raise PermissionDenied(_("unauthorized"))
        insuree_mutation = self.mutations.select_related(
            'mutation').filter(mutation__status=0).first()
        return insuree_mutation.mutation.client_mutation_id if insuree_mutation else None

    @classmethod
    def get_queryset(cls, queryset, info):
        return Insuree.get_queryset(queryset, info)


class FamilyGQLType(DjangoObjectType):
    client_mutation_id = graphene.String()

    def resolve_location(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        if "location_loader" in info.context.dataloaders:
            return info.context.dataloaders["location_loader"].load(self.location_id)

    def resolve_head_insuree(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        if "insuree_loader" in info.context.dataloaders:
            return info.context.dataloaders["insuree_loader"].load(self.head_insuree_id)

    class Meta:
        model = Family
        filter_fields = {
            "uuid": ["exact","iexact"],
            "poverty": ["exact", "isnull"],
            "confirmation_no": ["exact", "istartswith", "icontains", "iexact"],
            "confirmation_type": ["exact"],
            "family_type": ["exact"],
            "address": ["exact", "istartswith", "icontains", "iexact"],
            "ethnicity": ["exact"],
            "is_offline": ["exact"],
            **prefix_filterset("location__", LocationGQLType._meta.filter_fields),
            **prefix_filterset("head_insuree__", InsureeGQLType._meta.filter_fields),
            **prefix_filterset("members__", InsureeGQLType._meta.filter_fields)
        }
        interfaces = (graphene.relay.Node,)
        connection_class = ExtendedConnection

    def resolve_client_mutation_id(self, info):
        if not info.context.user.has_perms(InsureeConfig.gql_query_families_perms):
            raise PermissionDenied(_("unauthorized"))
        family_mutation = self.mutations.select_related(
            'mutation').filter(mutation__status=0).first()
        return family_mutation.mutation.client_mutation_id if family_mutation else None

    @classmethod
    def get_queryset(cls, queryset, info):
        return Family.get_queryset(queryset, info)


class InsureePolicyGQLType(DjangoObjectType):
    class Meta:
        model = InsureePolicy
        filter_fields = {
            "enrollment_date": ["exact", "lt", "lte", "gt", "gte"],
            "start_date": ["exact", "lt", "lte", "gt", "gte"],
            "effective_date": ["exact", "lt", "lte", "gt", "gte"],
            "expiry_date": ["exact", "lt", "lte", "gt", "gte"],
            **prefix_filterset("insuree__", InsureeGQLType._meta.filter_fields),
            **prefix_filterset("policy__", PolicyGQLType._meta.filter_fields),
        }
        interfaces = (graphene.relay.Node,)
        connection_class = ExtendedConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        return InsureePolicy.get_queryset(queryset, info)


class FamilyMutationGQLType(DjangoObjectType):
    class Meta:
        model = FamilyMutation


class InsureeMutationGQLType(DjangoObjectType):
    class Meta:
        model = InsureeMutation
