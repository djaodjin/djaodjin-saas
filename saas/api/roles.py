# Copyright (c) 2020, DjaoDjin inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#pylint:disable=useless-super-delegation

import logging
from collections import OrderedDict

from django.core import validators
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import Http404
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import (ListAPIView, ListCreateAPIView,
    DestroyAPIView, RetrieveUpdateDestroyAPIView,
    GenericAPIView, get_object_or_404)
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .. import settings, signals
from ..docs import no_body, swagger_auto_schema
from ..mixins import (OrganizationMixin, OrganizationSmartListMixin,
    RoleDescriptionMixin, RoleMixin, RoleSmartListMixin, UserMixin)
from ..utils import (full_name_natural_split, get_organization_model,
    get_role_model, generate_random_slug)
from .organizations import OrganizationCreateMixin, OrganizationDecorateMixin
from .serializers import (AccessibleSerializer,
    CreateAccessibleRequestSerializer, ForceSerializer, NoModelSerializer,
    OrganizationCreateSerializer, OrganizationDetailSerializer,
    RoleDescriptionSerializer, RoleSerializer)


LOGGER = logging.getLogger(__name__)


def _clean_field(user_model, field_name, value):
    #pylint:disable=protected-access
    field = user_model._meta.get_field(field_name)
    max_length = field.max_length
    if len(value) > max_length:
        orig = value
        value = value[:max_length]
        LOGGER.info("shorten %s '%s' to '%s' because it is longer than"\
            " %d characters", field_name, orig, value, max_length)
    try:
        field.run_validators(value)
    except ValidationError:
        orig = value
        value = generate_random_slug(max_length, prefix='user_')
        LOGGER.info("'%s' is an invalid %s so use '%s' instead.",
            orig, field_name, value)
    return value


def create_user_from_email(email, password=None, **kwargs):
    #pylint:disable=too-many-locals,unused-variable
    #
    # Implementation Note: This code is very similar to
    # `signup.models.ActivatedUserManager.create_user_from_email`.
    # Its purpose here instead of calling the above is to have
    # djaodjin-saas works as a stand-alone project (no dependency on signup).
    user = None
    user_model = get_user_model()
    first_name = kwargs.get('first_name', "")
    last_name = kwargs.get('last_name', "")
    if not (first_name or last_name):
        first_name, middle, last_name = full_name_natural_split(
            kwargs.get('full_name', ''))
    first_name = _clean_field(user_model, 'first_name', first_name)
    last_name = _clean_field(user_model, 'last_name', last_name)
    # The e-mail address was already validated by the Serializer.
    err = IntegrityError()
    if hasattr(user_model.objects, 'create_user_from_email'):
        # Implementation Note:
        # calling `signup.models.ActivatedUserManager.create_user_from_email`
        # directly bypasses sending a `user_registered` signal.
        user = user_model.objects.create_user_from_email(
            email, password=password,
            first_name=first_name, last_name=last_name)
    else:
        username = _clean_field(user_model, 'username', email.split('@')[0])
        #pylint:disable=protected-access
        field = user_model._meta.get_field('username')
        max_length = field.max_length
        trials = 0
        username_base = username
        while trials < 10:
            try:
                user = user_model.objects.create_user(username,
                    email=email, first_name=first_name, last_name=last_name)
                break
            except IntegrityError as exp:
                err = exp
                suffix = '-%s' % generate_random_slug(3)
                if len(username_base) + len(suffix) > max_length:
                    username = '%s%s' % (
                        username_base[:(max_length - len(suffix))],
                        suffix)
                else:
                    username = '%s%s' % (username_base, suffix)
                trials = trials + 1
    if not user:
        raise err
    request = kwargs.get('request', None)
    invited_by = request.user if request else None
    LOGGER.info("'%s %s <%s>' invited by '%s'",
        user.first_name, user.last_name, user.email, invited_by,
        extra={'event': 'invited', 'user': user, 'invited_by': invited_by})
    signals.user_invited.send(
        sender=__name__, user=user, invited_by=invited_by)
    return user


class OrganizationRoleCreateSerializer(NoModelSerializer):
    #pylint:disable=abstract-method

    slug = serializers.CharField(required=False, validators=[
        validators.RegexValidator(settings.ACCT_REGEX,
            _("Enter a valid organization slug."), 'invalid')])
    email = serializers.EmailField(required=False)
    message = serializers.CharField(max_length=255, required=False)


class UserRoleCreateSerializer(serializers.Serializer):
    #pylint:disable=abstract-method,protected-access

    slug = serializers.CharField(required=False,
        help_text=_("Username"),
        validators=[validators.RegexValidator(settings.ACCT_REGEX,
            _("Enter a valid username."), 'invalid')])
    email = serializers.EmailField(
        max_length=get_user_model()._meta.get_field('email').max_length,
        required=False, help_text=_("E-mail of the invitee"))
    full_name = serializers.CharField(required=False,
        help_text=_("Full name"))
    message = serializers.CharField(max_length=255, required=False,
        help_text=_("Message to send along the invitation"))

    @staticmethod
    def validate_slug(data):
        # The ``slug`` / ``username`` is implicit in the addition of a role
        # for a newly created user while adding a role. Hence we don't return
        # a validation error if the length is too long but arbitrarly shorten
        # the username.
        user_model = get_user_model()
        max_length = user_model._meta.get_field('username').max_length
        if len(data) > max_length:
            if '@' in data:
                data = data.split('@')[0]
            data = data[:max_length]
        return data


class RoleListPagination(PageNumberPagination):

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('invited_count', self.request.invited_count),
            ('requested_count', self.request.requested_count),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class OptinBase(OrganizationDecorateMixin, OrganizationCreateMixin):

    organization_model = get_organization_model()

    def add_relations(self, organizations, user, ends_at=None):
        #pylint:disable=no-self-use,unused-argument
        roles = []
        created = False
        for organization in organizations:
            role = organization.add_role_request(user)
            if role:
                created = True
                roles += [role]
        self.decorate_personal(organizations)
        return roles, created

    def send_signals(self, relations, user, reason=None, invite=False):
        #pylint:disable=no-self-use,unused-argument
        for role in relations:
            signals.role_request_created.send(sender=__name__,
                role=role, reason=reason)

    def perform_optin(self, serializer, request, user=None):
        #pylint:disable=too-many-locals
        if user is None:
            user = request.user
        reason = serializer.validated_data.get('message', None)
        if reason:
            reason = force_text(reason)
        organization_data = serializer.validated_data.get('organization', {})
        slug = serializer.validated_data.get('slug',
            organization_data.get('slug', None))
        email = serializer.validated_data.get('email',
            organization_data.get('email', None))
        if slug:
            organizations = self.organization_model.objects.filter(
                slug=slug)
        elif email:
            organizations = self.organization_model.objects.filter(
                email__iexact=email)
        else:
            organizations = self.organization_model.objects.none()
        invite = False
        with transaction.atomic():
            organizations = list(organizations)
            if not organizations:
                if organization_data.get('type') == 'personal':
                    user_exists = False
                    if ('slug' in organization_data and
                        organization_data['slug']):
                        user_exists = self.user_model.objects.filter(
                            username=organization_data['slug']).exists()
                    elif email:
                        try:
                            user = self.user_model.objects.filter(
                                email__iexact=email).get()
                            organization_data['slug'] = user.username
                            user_exists = True
                        except self.user_model.DoesNotExist:
                            pass
                    if user_exists:
                        # If we are creating a personal organization and
                        # we already have a user, we will implicitly create
                        # an organization as a personal billing profile
                        # for that user.
                        organizations = [
                            self.create_organization(organization_data)]
            if not organizations:
                if not request.GET.get('force', False):
                    raise Http404(_("Profile %(organization)s does not exist."
                    ) % {'organization': slug})
                if not email:
                    raise serializers.ValidationError({
                        'email': _("We cannot invite an organization"\
                            " without an e-mail address.")})
                if not organization_data.get('email', None):
                    organization_data['email'] = email
                full_name = organization_data.get('full_name', None)
                if not full_name:
                    default_full_name = slug
                    if not default_full_name:
                        email_parts = email.split('@')
                        email_parts = \
                            email_parts[:1] + email_parts[1].split('.')
                        # creates a default full_name from the username
                        # of an e-mail address.
                        default_full_name = email_parts[0]
                        # or creates a default full_name from the domain name
                        # of an e-mail address.
                        #if len(email_parts) >= 3:
                        #    default_full_name = email_parts[-2]
                    organization_data['full_name'] = \
                        serializer.validated_data.get('full_name',
                            default_full_name)
                organization = self.create_organization(organization_data)
                if organization.is_personal:
                    # We have created the attached User as part of creating
                    # the Organization.
                    manager = organization.attached_user()
                else:
                    user_model = get_user_model()
                    try:
                        manager = user_model.objects.get(email__iexact=email)
                    except user_model.DoesNotExist:
                        manager = create_user_from_email(email, request=request)
                    organization.add_manager(manager, request_user=request.user)
                organizations = [organization]
                invite = True

            # notified will either be a list of `Role` or `Subscription`.
            notified, created = self.add_relations(organizations, user)

        self.send_signals(notified, user, reason=reason, invite=invite)

        if created:
            resp_status = status.HTTP_201_CREATED
        else:
            resp_status = status.HTTP_200_OK
        # We were going to return the list of managers here but
        # angularjs complains about deserialization of a list
        # while expecting a single object.
        # XXX There is currently a single relation created due to statement
        # `organizations = [organization]` earlier in the code.
        if notified:
            resp_serializer = self.get_serializer(notified[0])
            result = resp_serializer.data
        else:
            result = None
        return Response(result, status=resp_status,
            headers=self.get_success_headers(serializer.validated_data))


class InvitedRequestedListMixin(object):
    """
    Filters requests for any role on an organization.
    """

    def get_queryset(self):
        queryset = super(InvitedRequestedListMixin, self).get_queryset()
        self.request.requested_count = queryset.filter(
            request_key__isnull=False).count()
        # Because we must count the number of invited
        # in `RoleByDescrQuerysetMixin.get_queryset`, we also need to compute
        # here instead of later in RoleInvitedListMixin.
        self.request.invited_count = queryset.filter(
            grant_key__isnull=False).count()
        role_status = self.request.query_params.get('role_status', '')
        stts = role_status.split(',')
        flt = None
        if 'active' in stts:
            flt = Q(grant_key__isnull=True) & Q(request_key__isnull=True)
            if 'invited' in stts:
                flt = Q(request_key__isnull=True)
                if 'requested' in stts:
                    flt = None
            elif 'requested' in stts:
                flt = Q(grant_key__isnull=True)
        elif 'invited' in stts:
            flt = Q(grant_key__isnull=False)
            if 'requested' in stts:
                flt = flt | Q(request_key__isnull=False)
        elif 'requested' in stts:
            flt = Q(request_key__isnull=False)

        if flt is not None:
            return queryset.filter(flt)
        return queryset


class AccessibleByQuerysetMixin(UserMixin):

    role_model = get_role_model()

    def get_queryset(self):
        return self.role_model.objects.filter(user=self.user)


class AccessibleByDescrQuerysetMixin(AccessibleByQuerysetMixin):

    def get_queryset(self):
        return super(AccessibleByDescrQuerysetMixin, self).get_queryset(
            ).filter(role_description__slug=self.kwargs.get('role'))


class AccessibleByListAPIView(RoleSmartListMixin, InvitedRequestedListMixin,
                              AccessibleByQuerysetMixin,
                              OptinBase, ListCreateAPIView):
    """
    Lists roles by user

    Lists all relations where an ``Organization`` is accessible by
    a ``User``. Typically the user was granted specific permissions through
    a ``Role``.

    see :doc:`Flexible Security Framework <security>`.

    **Tags**: rbac

    **Examples**

    .. code-block:: http

        GET  /api/users/alice/accessibles/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "cowork",
                    "created_at": "2018-01-01T00:00:00Z",
                    "printable_name": "ABC Corp.",
                    "email": "help@cowork.net",
                    "role_description": {
                        "slug": "manager",
                        "created_at": "2018-01-01T00:00:00Z",
                        "title": "Profile Manager",
                        "is_global": true,
                        "organization": null
                    },
                    "request_key": null,
                    "accept_grant_api_url": null,
                    "remove_api_url": "https://cowork.net/api/users/alice/accessibles/manager/cowork",
                    "home_url": "https://cowork.net/app/",
                    "settings_url": "https://cowork.net/profile/cowork/contact/"
                 }
            ]
        }
    """
    serializer_class = AccessibleSerializer
    pagination_class = RoleListPagination

    @swagger_auto_schema(request_body=OrganizationRoleCreateSerializer,
        query_serializer=ForceSerializer)
    def post(self, request, *args, **kwargs):
        """
        Requests a role

        Creates a request to attach a user to a role on an organization

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            POST /api/users/xia/accessibles/ HTTP/1.1

        .. code-block:: json

            {
              "slug": "cowork"
            }

        responds

        .. code-block:: json

            {
              "organization": {
                "slug": "cowork",
                "full_name": "Cowork",
                "printable_name": "Cowork",
                "picture": null,
                "type": "organization",
                "credentials": false
              },
              "created_at": "2020-06-06T04:55:41.766938Z",
              "request_key": "53a1b0657c7cf738514bf791e6f20f36429e57aa",
              "role_description": null,
              "home_url": "/app/cowork/",
              "settings_url": "/profile/cowork/contact/",
              "accept_grant_api_url": null,
              "remove_api_url": "/api/users/xia/accessibles/manager/cowork"
            }
        """
        return super(AccessibleByListAPIView, self).post(
            request, *args, **kwargs)

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = OrganizationRoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_optin(serializer, request, user=self.user)


class AccessibleByDescrListAPIView(RoleSmartListMixin,
                                   InvitedRequestedListMixin,
                                   AccessibleByDescrQuerysetMixin, UserMixin,
                                   ListCreateAPIView):
    """
    Lists roles of specific type by user

    Lists all relations where a ``User`` has a specified ``Role``
    on an ``Organization``.

    see :doc:`Flexible Security Framework <security>`.

    **Tags**: rbac

    **Examples**

    .. code-block:: http

        GET  /api/users/alice/accessibles/manager/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "cowork",
                    "created_at": "2018-01-01T00:00:00Z",
                    "printable_name": "ABC Corp.",
                    "email": "help@cowork.net",
                    "role_description": {
                        "slug": "manager",
                        "created_at": "2018-01-01T00:00:00Z",
                        "title": "Profile manager",
                        "is_global": true,
                        "organization": null
                    },
                    "request_key": null,
                    "accept_grant_api_url": null,
                    "remove_api_url": "https://cowork.net/api/users/alice/accessibles/manager/cowork",
                    "home_url": "https://cowork.net/app/",
                    "settings_url": "https://cowork.net/profile/cowork/contact/"
                }
            ]
        }
    """
    serializer_class = AccessibleSerializer
    pagination_class = RoleListPagination

    def get_serializer_class(self):
        if self.request.method.lower() == 'post':
            return CreateAccessibleRequestSerializer
        return super(AccessibleByDescrListAPIView, self).get_serializer_class()

    @swagger_auto_schema(request_body=OrganizationRoleCreateSerializer,
        query_serializer=ForceSerializer)
    def post(self, request, *args, **kwargs): #pylint:disable=unused-argument
        """
        Requests a role of a specified type

        Creates a request to attach a user to an organization
        with a specified role.

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            POST /api/users/xia/accessibles/manager/ HTTP/1.1

        .. code-block:: json

            {
              "slug": "cowork"
            }

        responds

        .. code-block:: json

            {
              "organization": {
                "slug": "cowork",
                "full_name": "Cowork",
                "printable_name": "Cowork",
                "picture": null,
                "type": "organization",
                "credentials": false
              },
              "created_at": "2020-06-06T04:55:41.766938Z",
              "request_key": "53a1b0657c7cf738514bf791e6f20f36429e57aa",
              "role_description": {
                "slug": "manager",
                "created_at": "2018-01-01T00:00:00Z",
                "title": "Profile manager",
                "is_global": true,
                "organization": null
              },
              "home_url": "/app/cowork/",
              "settings_url": "/profile/cowork/contact/",
              "accept_grant_api_url": null,
              "remove_api_url": "/api/users/xia/accessibles/manager/cowork"
            }
        """
        return super(AccessibleByDescrListAPIView, self).post(
            request, *args, **kwargs)

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        serializer = OrganizationRoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_optin(serializer, request, user=self.user)


class RoleDescriptionQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        return self.organization.get_role_descriptions()

    @staticmethod
    def check_local(instance):
        if instance.is_global():
            raise PermissionDenied()


class RoleDescriptionListCreateView(RoleDescriptionQuerysetMixin,
                                    ListCreateAPIView):
    """
    Lists role types

    Lists roles by description``RoleDescription``.

    see :doc:`Flexible Security Framework <security>`.

    **Tags**: rbac

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/roles/describe/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 2,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2018-01-01T00:00:00Z",
                    "title": "Managers",
                    "slug": "manager",
                    "is_global": true
                },
                {
                    "created_at": "2018-01-01T00:00:00Z",
                    "title": "Contributors",
                    "slug": "contributor",
                    "is_global": false,
                    "roles": []
                }
            ]
        }
    """
    serializer_class = RoleDescriptionSerializer

    def post(self, request, *args, **kwargs):
        """
        Creates a role type

        Creates a role that users can take on an organization.

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            POST /api/profile/cowork/roles/describe/ HTTP/1.1

        .. code-block:: json

            {
              "title": "Support"
            }

        responds

        .. code-block:: json

            {
              "created_at": "2018-01-01T00:00:00Z",
              "title": "Support",
              "slug": "support",
              "is_global": false,
              "roles": []
            }

        """
        return super(RoleDescriptionListCreateView, self).post(
            request, *args, **kwargs)



class RoleDescriptionDetailView(RoleDescriptionQuerysetMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves a role type

    see :doc:`Flexible Security Framework <security>`.

    **Tags**: rbac

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/roles/describe/manager HTTP/1.1

    responds

    .. code-block:: json

        {
            "created_at": "2018-01-01T00:00:00Z",
            "slug": "manager",
            "title": "Profile Managers",
            "is_global": true,
            "roles": [
                {
                    "created_at": "2018-01-01T00:00:00Z",
                    "user": {
                        "slug": "donny",
                        "email": "donny@localhost.localdomain",
                        "full_name": "Donny Cooper",
                        "created_at": "2018-01-01T00:00:00Z"
                    },
                    "request_key": null,
                    "grant_key": null
                }
            ]
        }

    """
    serializer_class = RoleDescriptionSerializer
    lookup_field = 'slug'
    lookup_url_kwarg = 'role'

    def delete(self, request, *args, **kwargs):
        """
        Deletes a role type

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            DELETE /api/profile/cowork/roles/describe/manager HTTP/1.1
        """
        return super(RoleDescriptionDetailView, self).delete(
            request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        """
        Updates a role type

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            PUT /api/profile/cowork/roles/describe/manager HTTP/1.1

        .. code-block:: json

            {
                "title": "Profile managers"
            }

        responds

        .. code-block:: json

            {
                "created_at": "2018-01-01T00:00:00Z",
                "title": "Profile managers",
                "slug": "manager",
                "is_global": true,
                "roles": [
                    {
                        "created_at": "2018-01-01T00:00:00Z",
                        "user": {
                            "slug": "donny",
                            "email": "donny@localhost.localdomain",
                            "full_name": "Donny Cooper",
                            "created_at": "2018-01-01T00:00:00Z"
                        },
                        "request_key": null,
                        "grant_key": null
                    }
                ]
            }

        """
        return super(RoleDescriptionDetailView, self).put(
            request, *args, **kwargs)

    def perform_update(self, serializer):
        self.check_local(serializer.instance)
        super(RoleDescriptionDetailView, self).perform_update(serializer)

    def perform_destroy(self, instance):
        self.check_local(instance)
        super(RoleDescriptionDetailView, self).perform_destroy(instance)


class RoleQuerysetBaseMixin(OrganizationMixin):

    def get_queryset(self):
        return get_role_model().objects.filter(organization=self.organization)


class RoleListAPIView(RoleSmartListMixin, InvitedRequestedListMixin,
                      RoleQuerysetBaseMixin, ListAPIView):
    """
    Lists roles for an organization

    **Tags**: rbac

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/roles/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2018-01-01T00:00:00Z",
                    "role_description": {
                        "name": "Manager",
                        "slug": "manager",
                        "organization": {
                            "slug": "cowork",
                            "full_name": "ABC Corp.",
                            "printable_name": "ABC Corp.",
                            "created_at": "2018-01-01T00:00:00Z",
                            "email": "support@localhost.localdomain"
                        }
                    },
                    "user": {
                        "slug": "alice",
                        "email": "alice@localhost.localdomain",
                        "full_name": "Alice Doe",
                        "created_at": "2018-01-01T00:00:00Z"
                    },
                    "request_key": "1",
                    "grant_key": null
                }
            ]
        }
    """
    serializer_class = RoleSerializer
    pagination_class = RoleListPagination


class RoleByDescrQuerysetMixin(RoleDescriptionMixin, RoleQuerysetBaseMixin):
    # We cannot use `InvitedRequestedListMixin` here because `role_description`
    # will be None on requested roles. We thus need a `role_description = X
    # *OR* request_key IS NOT NULL`. Calls to more and more refined `filter`
    # through class inheritence only allows us to implement `*AND*`.

    def get_queryset(self):
        queryset = super(RoleByDescrQuerysetMixin, self).get_queryset()
        self.request.requested_count = queryset.filter(
            request_key__isnull=False).count()
        # We have to get the count of invited here otherwise
        # `GET /api/profile/{organization}/roles/manager?role_status=requested`
        # will always return zero invited users.
        self.request.invited_count = queryset.filter(
            role_description=self.role_description,
            grant_key__isnull=False).count()
        role_status = self.request.query_params.get('role_status', '')
        stts = role_status.split(',')
        flt = (Q(role_description=self.role_description) |
            Q(request_key__isnull=False))
        if 'active' in stts:
            flt = (Q(role_description=self.role_description) &
                Q(grant_key__isnull=True) & Q(request_key__isnull=True))
            if 'invited' in stts:
                flt = Q(role_description=self.role_description)
            if 'requested' in stts:
                flt = flt | Q(request_key__isnull=False)
        else:
            if 'invited' in stts:
                flt = (Q(role_description=self.role_description) &
                    Q(grant_key__isnull=False))
                if 'requested' in stts:
                    flt = flt | Q(request_key__isnull=False)
            elif 'requested' in stts:
                flt = Q(request_key__isnull=False)
        return queryset.filter(flt)


class RoleByDescrListAPIView(RoleSmartListMixin, RoleByDescrQuerysetMixin,
                             ListCreateAPIView):
    """
    Lists roles of a specific type

    Lists the specified role assignments for an organization.

    **Tags**: rbac

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/roles/manager/ HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2018-01-01T00:00:00Z",
                    "role_description": {
                        "name": "Manager",
                        "slug": "manager",
                        "organization": {
                            "slug": "cowork",
                            "full_name": "ABC Corp.",
                            "printable_name": "ABC Corp.",
                            "created_at": "2018-01-01T00:00:00Z",
                            "email": "support@localhost.localdomain"
                        }
                    },
                    "user": {
                        "slug": "alice",
                        "email": "alice@localhost.localdomain",
                        "full_name": "Alice Doe",
                        "created_at": "2018-01-01T00:00:00Z"
                    },
                    "request_key": "1",
                    "grant_key": null
                }
            ]
        }
    """
    serializer_class = RoleSerializer
    pagination_class = RoleListPagination

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        grant_key = None
        serializer = UserRoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_model = get_user_model()
        user = None
        if serializer.validated_data.get('slug'):
            try:
                user = user_model.objects.get(
                    username=serializer.validated_data['slug'])
            except user_model.DoesNotExist:
                user = None
        if not user and serializer.validated_data.get('email'):
            try:
                # The following SQL query is not folded into the previous
                # one so we can have a priority of username over email.
                user = user_model.objects.get(
                    email__iexact=serializer.validated_data['email'])
            except user_model.DoesNotExist:
                user = None
        if not user:
            if not request.GET.get('force', False):
                sep = ""
                not_found_msg = "Cannot find"
                if serializer.validated_data.get('slug'):
                    not_found_msg += " username %(username)s" % {
                        'username': serializer.validated_data['slug']
                    }
                    sep = "or"
                if serializer.validated_data.get('email'):
                    not_found_msg += sep + " email %(email)s" % {
                        'email': serializer.validated_data['email']
                    }
                raise Http404(not_found_msg)
            user = create_user_from_email(
                serializer.validated_data['email'],
                full_name=serializer.validated_data.get('full_name', ''),
                request=request)
            grant_key = generate_random_slug()
        reason = serializer.validated_data.get('message', None)
        if reason:
            reason = force_text(reason)
        created = self.organization.add_role(
            user, self.role_description, grant_key=grant_key, reason=reason,
            request_user=request.user)
        if created:
            resp_status = status.HTTP_201_CREATED
        else:
            resp_status = status.HTTP_200_OK
        # We were going to return the list of managers here but
        # angularjs complains about deserialization of a list
        # while expecting a single object.
        return Response(serializer.validated_data, status=resp_status,
            headers=self.get_success_headers(serializer.validated_data))

    @swagger_auto_schema(request_body=UserRoleCreateSerializer,
        query_serializer=ForceSerializer)
    def post(self, request, *args, **kwargs):
        """
        Creates a role

        Attaches a user to a role on an organization, typically granting
        permissions to the user with regards to managing an organization profile
        (see :doc:`Flexible Security Framework <security>`).

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            POST /api/profile/cowork/roles/manager/ HTTP/1.1

        .. code-block:: json

            {
              "slug": "xia"
            }

        responds

        .. code-block:: json

            {
              "slug": "xia"
            }
        """
        return super(RoleByDescrListAPIView, self).post(
            request, *args, **kwargs)


class RoleDetailAPIView(RoleMixin, DestroyAPIView):
    """
    Re-sends and delete role for a user on a profile.
    """
    serializer_class = RoleSerializer

    @swagger_auto_schema(request_body=no_body)
    def post(self, request, *args, **kwargs):#pylint:disable=unused-argument
        """
        Re-sends role invite

        Re-sends the invite e-mail that the user was granted a role
        on the organization.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            POST /api/profile/cowork/roles/manager/xia/ HTTP/1.1

        responds

        .. code-block:: json

            {
                "created_at": "2018-01-01T00:00:00Z",
                "role_description": {
                    "created_at": "2018-01-01T00:00:00Z",
                    "title": "Profile Manager",
                    "slug": "manager",
                    "is_global": true,
                    "organization": {
                        "slug": "cowork",
                        "full_name": "ABC Corp.",
                        "printable_name": "ABC Corp.",
                        "created_at": "2018-01-01T00:00:00Z",
                        "email": "support@localhost.localdomain"
                    }
                },
                "user": {
                    "slug": "alice",
                    "email": "alice@localhost.localdomain",
                    "full_name": "Alice Doe",
                    "created_at": "2018-01-01T00:00:00Z"
                },
                "request_key": "1",
                "grant_key": null
            }
        """
        role = self.get_object()
        signals.role_grant_created.send(sender=__name__,
            role=role, reason=None, request_user=request.user)
        serializer = self.get_serializer(role)
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        """
        Deletes a role

        Dettach a user from one or all roles with regards to an organization,
        typically resulting in revoking permissions from this user to manage
        part of an organization profile.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            DELETE /api/profile/cowork/roles/manager/xia/ HTTP/1.1
        """
        return super(RoleDetailAPIView, self).delete(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        roles = [str(role.role_description) for role in queryset]
        LOGGER.info("Remove roles %s for user '%s' on organization '%s'",
            roles, self.user, self.organization,
            extra={'event': 'remove-roles', 'user': self.user,
                'organization': self.organization.slug, 'roles': roles})
        queryset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccessibleDetailAPIView(RoleDetailAPIView):
    """
    Re-sends and delete role for a user on a profile.
    """

    def get_queryset(self):
        # We never take the `role_description` into account when removing
        # on the accessibles page.
        return get_role_model().objects.filter(
            organization=self.organization, user=self.user)

    @swagger_auto_schema(request_body=no_body)
    def post(self, request, *args, **kwargs):
        """
        Re-sends request for role

        Re-sends the request e-mail that the user is requesting a role
        on the organization.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            POST /api/users/xia/accessibles/manager/cowork/ HTTP/1.1

        responds

        .. code-block:: json

            {
                "created_at": "2018-01-01T00:00:00Z",
                "role_description": {
                    "created_at": "2018-01-01T00:00:00Z",
                    "title": "Profile Manager",
                    "slug": "manager",
                    "is_global": true,
                    "organization": {
                        "slug": "cowork",
                        "full_name": "ABC Corp.",
                        "printable_name": "ABC Corp.",
                        "created_at": "2018-01-01T00:00:00Z",
                        "email": "support@localhost.localdomain"
                    }
                },
                "user": {
                    "slug": "alice",
                    "email": "alice@localhost.localdomain",
                    "full_name": "Alice Doe",
                    "created_at": "2018-01-01T00:00:00Z"
                },
                "request_key": "1",
                "grant_key": null
            }
        """
        role = self.get_object()
        signals.role_request_created.send(sender=__name__,
            role=role, reason=None, request_user=request.user)
        serializer = self.get_serializer(role)
        return Response(serializer.data)


    def delete(self, request, *args, **kwargs):
        """
        Deletes a role by type

        Dettach a user from one or all roles with regards to an organization,
        typically resulting in revoking permissions from this user to manage
        part of an organization profile.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            DELETE /api/users/xia/accessibles/manager/cowork/ HTTP/1.1
        """
        return super(AccessibleDetailAPIView, self).delete(
            request, *args, **kwargs)


class RoleAcceptAPIView(UserMixin, GenericAPIView):

    serializer_class = AccessibleSerializer

    @swagger_auto_schema(request_body=no_body)
    def put(self, request, *args, **kwargs):#pylint:disable=unused-argument
        """
        Accepts role invite

        Accepts a role on an organization.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            PUT /api/users/xia/accessibles/accept/0123456789abcef/ HTTP/1.1

        responds

        .. code-block:: json

            {
                "created_at": "2018-01-01T00:00:00Z",
                "role_description": {
                    "created_at": "2018-01-01T00:00:00Z",
                    "title": "Profile Manager",
                    "slug": "manager",
                    "is_global": true,
                    "organization": {
                        "slug": "cowork",
                        "full_name": "ABC Corp.",
                        "printable_name": "ABC Corp.",
                        "created_at": "2018-01-01T00:00:00Z",
                        "email": "support@localhost.localdomain"
                    }
                },
                "user": {
                    "slug": "alice",
                    "email": "alice@localhost.localdomain",
                    "full_name": "Alice Doe",
                    "created_at": "2018-01-01T00:00:00Z"
                },
                "request_key": "1",
                "grant_key": null
            }
        """
        key = kwargs.get('verification_key')
        obj = get_object_or_404(get_role_model().objects.all(),
                grant_key=key)
        existing_role = get_role_model().objects.filter(
            organization=obj.organization, user=self.user).exclude(
            pk=obj.pk).first()
        if existing_role:
            raise serializers.ValidationError(
                _("You already have a %(existing_role)s"\
                " role on %(organization)s. Please drop this role first if"\
                " you want to accept a role of %(role)s instead.") % {
                    'role': obj.role_description.title,
                    'organization': obj.organization.printable_name,
                    'existing_role': existing_role.role_description.title})

        grant_key = obj.grant_key
        obj.grant_key = None
        obj.save()
        LOGGER.info("%s accepted role of %s to %s (grant_key=%s)",
            self.user, obj.role_description, obj.organization,
            grant_key, extra={
                'request': request, 'event': 'accept',
                'user': str(self.user),
                'organization': str(obj.organization),
                'role_description': str(obj.role_description),
                'grant_key': grant_key})
        signals.role_grant_accepted.send(sender=__name__,
            role=obj, grant_key=grant_key, request=request)

        serializer = self.get_serializer(instance=obj)
        return Response(serializer.data)


class UserProfileListAPIView(OrganizationSmartListMixin,
                             OrganizationDecorateMixin, OrganizationCreateMixin,
                             UserMixin, ListCreateAPIView):
    """
    List billing profiles owned by user

    Queries a page (``PAGE_SIZE`` records) of organization and user profiles.

    The queryset can be filtered for at least one field to match a search
    term (``q``).

    The queryset can be ordered by a field by adding an HTTP query parameter
    ``o=`` followed by the field name. A sequence of fields can be used
    to create a complete ordering by adding a sequence of ``o`` HTTP query
    parameters. To reverse the natural order of a field, prefix the field
    name by a minus (-) sign.

    **Tags**: profile

    **Examples**

    .. code-block:: http

        GET /api/users/xia/profiles/?o=created_at HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [{
                "slug": "xia",
                "full_name": "Xia Lee",
                "email": "xia@localhost.localdomain",
                "printable_name": "Xia Lee",
                "created_at": "2016-01-14T23:16:55Z"
            }]
        }
    """
    serializer_class = OrganizationDetailSerializer

    def paginate_queryset(self, queryset):
        page = super(UserProfileListAPIView, self).paginate_queryset(queryset)
        page = self.decorate_personal(page)
        return page

    def get_serializer_class(self):
        if self.request.method.lower() == 'post':
            return OrganizationCreateSerializer
        return super(UserProfileListAPIView, self).get_serializer_class()

    def get_queryset(self):
        return get_organization_model().objects.accessible_by(
            self.user, role_description=settings.MANAGER)

    def post(self, request, *args, **kwargs):
        """
        Creates a new profile owned by user

        This end-point creates a new profile whose manager is user and
        returns an error if the profile already exists.

        If you want to request access to an already existing profile,
        see the accessibles end-point.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            POST /api/users/xia/profiles/ HTTP/1.1

        .. code-block:: json

            {
              "slug": "myproject",
              "full_name": "My Project"
            }

        responds

        .. code-block:: json

            {
              "slug": "myproject",
              "full_name": "My Project"
            }
        """
        return super(UserProfileListAPIView, self).post(
            request, *args, **kwargs)

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        #pylint:disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # creates profile
        with transaction.atomic():
            organization = self.create_organization(serializer.validated_data)
            organization.add_manager(self.user, request_user=self.request.user)
        self.decorate_personal(organization)

        # returns created profile
        serializer = self.get_serializer(instance=organization)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
            status=status.HTTP_201_CREATED, headers=headers)
