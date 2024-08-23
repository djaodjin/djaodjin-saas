# Copyright (c) 2023, DjaoDjin inc.
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

#pylint:disable=useless-super-delegation,too-many-lines

import logging

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import Http404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import (ListAPIView, ListCreateAPIView,
    RetrieveUpdateDestroyAPIView, GenericAPIView, get_object_or_404)
from rest_framework.mixins import (RetrieveModelMixin, DestroyModelMixin,
    UpdateModelMixin)
from rest_framework.response import Response

from .. import settings, signals
from ..compat import force_str, gettext_lazy as _
from ..docs import extend_schema, OpenApiResponse
from ..decorators import _has_valid_access
from ..filters import OrderingFilter, SearchFilter
from ..mixins import (OrganizationMixin, OrganizationCreateMixin,
    OrganizationSmartListMixin, RoleDescriptionMixin, RoleMixin,
    RoleSmartListMixin, UserMixin)
from ..models import _clean_field, get_broker
from ..pagination import RoleListPagination
from ..utils import (full_name_natural_split, get_organization_model,
    get_role_model, get_role_serializer, generate_random_slug)
from .organizations import OrganizationDecorateMixin
from .serializers import (AccessibleSerializer, QueryParamForceSerializer,
    OrganizationCreateSerializer,
    OrganizationDetailSerializer, RoleDescriptionSerializer,
    AccessibleCreateSerializer, RoleCreateSerializer,
    QueryParamRoleStatusSerializer, QueryParamPersonalProfSerializer)


LOGGER = logging.getLogger(__name__)


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
    first_name = _clean_field(
        user_model, 'first_name', first_name, prefix='user_')
    last_name = _clean_field(
        user_model, 'last_name', last_name, prefix='user_')
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
        username = _clean_field(
            user_model, 'username', email.split('@')[0], prefix='user_')
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


class ListOptinAPIView(OrganizationDecorateMixin, OrganizationCreateMixin,
                       ListCreateAPIView):

    organization_model = get_organization_model()
    serializer_class = AccessibleSerializer

    @property
    def role_descr(self):
        return self.kwargs.get('role')

    def add_relations(self, organizations, user, ends_at=None):
        #pylint:disable=unused-argument
        requests = []
        new_requests = []
        for organization in organizations:
            role, created = organization.add_role_request(
                user, role_descr=self.role_descr)
            requests += [role]
            if created:
                new_requests += [role]
        self.decorate_personal(organizations)
        return requests, new_requests

    def send_signals(self, relations, user, reason=None, invite=False):
        #pylint:disable=unused-argument
        for role in relations:
            signals.role_request_created.send(sender=__name__,
                role=role, reason=reason)

    def perform_optin(self, serializer, request, user=None):
        #pylint:disable=too-many-locals,too-many-statements
        if user is None:
            user = request.user
        reason = serializer.validated_data.get('message', None)
        if reason:
            reason = force_str(reason)
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
                query_serializer = QueryParamForceSerializer(
                    data=self.request.query_params)
                query_serializer.is_valid(raise_exception=True)
                force = query_serializer.validated_data.get('force', False)
                if not force:
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
                manager = None
                organization = self.create_organization(organization_data)
                if organization.is_personal:
                    # We have created the attached User as part of creating
                    # the Organization.
                    manager = organization.attached_user()
                if not manager:
                    user_model = get_user_model()
                    try:
                        manager = user_model.objects.get(email__iexact=email)
                        organization.add_manager(manager)
                    except user_model.DoesNotExist:
                        # If we are not creating a personal profile, it is OK
                        # no user is associated.
                        pass
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
        resp_serializer = self.serializer_class(
            instance=notified[0], context=self.get_serializer_context())
        result = resp_serializer.data

        return Response(resp_serializer.data, status=resp_status,
            headers=self.get_success_headers(resp_serializer.data))


class InvitedRequestedListMixin(object):
    """
    Filters requests for any role on an organization.
    """
    role_status_param = 'role_status'

    def get_queryset(self):
        queryset = super(InvitedRequestedListMixin, self).get_queryset()
        self.request.requested_count = queryset.filter(
            request_key__isnull=False).count()
        # Because we must count the number of invited
        # in `RoleByDescrQuerysetMixin.get_queryset`, we also need to compute
        # here instead of later in RoleInvitedListMixin.
        self.request.invited_count = queryset.filter(
            grant_key__isnull=False).count()
        query_serializer = QueryParamRoleStatusSerializer(
            data=self.request.query_params)
        role_status = ''
        if query_serializer.is_valid(raise_exception=True):
            role_status = query_serializer.validated_data.get(
                self.role_status_param, '')
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
    include_personal_profile_param = 'include_personal_profile'

    def get_queryset(self):
        queryset = self.role_model.objects.filter(user=self.user)
        query_serializer = QueryParamPersonalProfSerializer(
            data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)

        include_personal_profile = query_serializer.validated_data.get(
            self.include_personal_profile_param, False)
        if not include_personal_profile:
            queryset = queryset.exclude(organization__slug=self.user)

        # `RoleSerializer` will expand `user` and `role_description`.
        queryset = queryset.select_related('user').select_related(
            'role_description')

        return queryset


class AccessibleByDescrQuerysetMixin(AccessibleByQuerysetMixin):

    def get_queryset(self):
        return super(AccessibleByDescrQuerysetMixin, self).get_queryset(
            ).filter(role_description__slug=self.kwargs.get('role'))


class AccessibleByListAPIView(RoleSmartListMixin,
                              InvitedRequestedListMixin,
                              AccessibleByQuerysetMixin,
                              ListOptinAPIView):
    """
    Lists roles by user

    Returns a list of {{PAGE_SIZE}} roles where a profile is accessible by
    {user}. Typically the user was granted a role with specific permissions
    on the profile.

    The queryset can be further refined to match a search filter (``q``)
    and sorted on specific fields (``o``).

    The API is typically used within an HTML
    `connected profiles page </docs/guides/themes/#dashboard_users_roles>`_
    as present in the default theme.

    see :doc:`Flexible Security Framework <security>`.

    **Tags**: rbac, user, rolemodel

    **Examples**

    .. code-block:: http

        GET  /api/users/xia/accessibles HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "invited_count": 0,
            "requested_count": 0,
            "results": [
                {
                    "profile": {
                        "slug": "cowork",
                        "printable_name": "ABC Corp.",
                        "type": "organization",
                        "credentials": false
                    },
                    "role_description": {
                        "slug": "manager",
                        "created_at": "2023-01-01T00:00:00Z",
                        "title": "Profile Manager",
                        "is_global": true,
                        "profile": null
                    },
                    "request_key": null,
                    "accept_grant_api_url": null,
                    "remove_api_url": "https://cowork.net/api/users/alice/\
accessibles/manager/cowork",
                    "home_url": "https://cowork.net/app/",
                    "settings_url": "https://cowork.net/profile/cowork/contact/"
                }
            ]
        }
    """
    search_fields = (
        'profile',
        'profile__full_name',
        'profile__email',
        'role',
        'role__title'
    )

    serializer_class = AccessibleSerializer
    pagination_class = RoleListPagination

    def get_serializer_class(self):
        if self.request.method.lower() == 'post':
            return AccessibleCreateSerializer
        return super(AccessibleByListAPIView, self).get_serializer_class()

    @extend_schema(parameters=[QueryParamForceSerializer], responses={
      201: OpenApiResponse(AccessibleSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Requests a role

        Creates a request to connect {user} to a profile

        The API is typically used within an HTML
        `connected profiles page </docs/guides/themes/#dashboard_users_roles>`_
        as present in the default theme.

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac, user, rolemodel

        **Examples**

        .. code-block:: http

            POST /api/users/xia/accessibles HTTP/1.1

        .. code-block:: json

            {
              "slug": "cowork"
            }

        responds

        .. code-block:: json

            {
              "profile": {
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_optin(serializer, request, user=self.user)


class AccessibleByDescrListAPIView(RoleSmartListMixin,
                                   InvitedRequestedListMixin,
                                   AccessibleByDescrQuerysetMixin,
                                   ListOptinAPIView):
    """
    Lists roles of specific type by user

    Returns a list of {{PAGE_SIZE}} roles where a profile is accessible by
    {user} through a {role}. Typically the user was granted the {role}
    with specific permissions on the profile.

    The queryset can be further refined to match a search filter (``q``)
    and sorted on specific fields (``o``).

    The API is typically used within an HTML
    `connected profiles page </docs/guides/themes/#dashboard_users_roles>`_
    as present in the default theme.

    see :doc:`Flexible Security Framework <security>`.

    **Tags**: rbac, user, rolemodel

    **Examples**

    .. code-block:: http

        GET  /api/users/xia/accessibles/manager HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "invited_count": 0,
            "requested_count": 0,
            "results": [
                {
                    "profile": {
                        "slug": "cowork",
                        "printable_name": "ABC Corp.",
                        "type": "organization",
                        "credentials": false
                    },
                    "role_description": {
                        "slug": "manager",
                        "created_at": "2023-01-01T00:00:00Z",
                        "title": "Profile manager",
                        "is_global": true,
                        "profile": null
                    },
                    "request_key": null,
                    "accept_grant_api_url": null,
                    "remove_api_url": "https://cowork.net/api/users/alice/\
accessibles/manager/cowork",
                    "home_url": "https://cowork.net/app/",
                    "settings_url": "https://cowork.net/profile/cowork/contact/"
                }
            ]
        }
    """
    search_fields = (
        'profile',
        'profile__full_name',
        'profile__email'
    )

    serializer_class = AccessibleSerializer
    pagination_class = RoleListPagination

    def get_serializer_class(self):
        if self.request.method.lower() == 'post':
            return AccessibleCreateSerializer
        return super(AccessibleByDescrListAPIView, self).get_serializer_class()

    @extend_schema(operation_id='users_accessibles_list_by_role')
    def get(self, request, *args, **kwargs):
        return super(AccessibleByDescrListAPIView, self).get(
            request, *args, **kwargs)

    @extend_schema(operation_id='users_accessibles_create_by_role',
        parameters=[QueryParamForceSerializer], responses={
        201: OpenApiResponse(AccessibleSerializer)})
    def post(self, request, *args, **kwargs): #pylint:disable=unused-argument
        """
        Requests a role of a specified type

        Creates a request to connect {user} to a profile
        with a specified {role}.

        The API is typically used within an HTML
        `connected profiles page </docs/guides/themes/#dashboard_users_roles>`_
        as present in the default theme.

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac, user, rolemodel

        **Examples**

        .. code-block:: http

            POST /api/users/xia/accessibles/manager HTTP/1.1

        .. code-block:: json

            {
              "slug": "cowork"
            }

        responds

        .. code-block:: json

            {
              "profile": {
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
                "created_at": "2023-01-01T00:00:00Z",
                "title": "Profile manager",
                "is_global": true,
                "profile": null
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_optin(serializer, request, user=self.user)


class RoleDescriptionSmartListMixin(object):

    search_fields = (
        'slug',
        'title',
    )
    ordering_fields = (
        ('slug', 'slug'),
        ('title', 'title'),
    )
    ordering = ('slug',)

    filter_backends = (SearchFilter, OrderingFilter)


class RoleDescriptionQuerysetMixin(OrganizationMixin):

    def get_queryset(self):
        return self.organization.get_role_descriptions()

    def check_local(self, instance):
        if (instance.is_global() and
            not _has_valid_access(self.request, [get_broker()])):
            raise PermissionDenied()


class RoleDescriptionListCreateView(RoleDescriptionSmartListMixin,
                                    RoleDescriptionQuerysetMixin,
                                    ListCreateAPIView):
    """
    Lists role types

    Lists roles by description``RoleDescription``.

    see :doc:`Flexible Security Framework <security>`.

    **Tags**: rbac, list, subscriber, rolemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/xia/roles/describe HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 2,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2023-01-01T00:00:00Z",
                    "slug": "manager",
                    "title": "Manager",
                    "skip_optin_on_grant": false,
                    "implicit_create_on_none": false,
                    "is_global": true
                },
                {
                    "created_at": "2023-01-01T00:00:00Z",
                    "slug": "contributor",
                    "title": "Contributor",
                    "skip_optin_on_grant": true,
                    "implicit_create_on_none": false,
                    "is_global": false,
                    "profile": {
                        "slug": "xia",
                        "printable_name": "Xia",
                        "picture": null,
                        "type": "personal",
                        "credentials": true,
                        "created_at": "2023-01-01T00:00:00Z"
                    }
                }
            ]
        }
    """
    serializer_class = RoleDescriptionSerializer

    def post(self, request, *args, **kwargs):
        """
        Creates a role type

        Creates a role that users can take on a profile.

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac, subscriber, rolemodel

        **Examples**

        .. code-block:: http

            POST /api/profile/xia/roles/describe HTTP/1.1

        .. code-block:: json

            {
              "title": "Support"
            }

        responds

        .. code-block:: json

            {
              "created_at": "2023-01-01T00:00:00Z",
              "title": "Support",
              "slug": "support",
              "skip_optin_on_grant": false,
              "implicit_create_on_none": false,
              "is_global": false,
              "profile": {
                  "slug": "xia",
                  "printable_name": "Xia",
                  "picture": null,
                  "type": "personal",
                  "credentials": true,
                  "created_at": "2023-01-01T00:00:00Z"
              }
            }

        """
        return super(RoleDescriptionListCreateView, self).post(
            request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(organization=self.organization if not self.organization.is_broker else None)


class RoleDescriptionDetailView(RoleDescriptionQuerysetMixin,
                                RetrieveUpdateDestroyAPIView):
    """
    Retrieves a role type

    see :doc:`Flexible Security Framework <security>`.

    **Tags**: rbac, subscriber, rolemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/xia/roles/describe/manager HTTP/1.1

    responds

    .. code-block:: json

        {
            "created_at": "2023-01-01T00:00:00Z",
            "slug": "manager",
            "title": "Profile Manager",
            "skip_optin_on_grant": false,
            "implicit_create_on_none": false,
            "is_global": true
        }

    """
    serializer_class = RoleDescriptionSerializer
    lookup_field = 'slug'
    lookup_url_kwarg = 'role'

    def delete(self, request, *args, **kwargs):
        """
        Deletes a role type

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac, subscriber, rolemodel

        **Examples**

        .. code-block:: http

            DELETE /api/profile/xia/roles/describe/support HTTP/1.1
        """
        return super(RoleDescriptionDetailView, self).delete(
            request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        """
        Updates a role type

        see :doc:`Flexible Security Framework <security>`.

        **Tags**: rbac, subscriber, rolemodel

        **Examples**

        .. code-block:: http

            PUT /api/profile/xia/roles/describe/support HTTP/1.1

        .. code-block:: json

            {
                "title": "Associate"
            }

        responds

        .. code-block:: json

            {
                "created_at": "2023-01-01T00:00:00Z",
                "slug": "support",
                "title": "Associate",
                "skip_optin_on_grant": false,
                "implicit_create_on_none": false,
                "is_global": false,
                "profile": {
                    "slug": "xia",
                    "printable_name": "Xia",
                    "picture": null,
                    "type": "personal",
                    "credentials": true,
                    "created_at": "2023-01-01T00:00:00Z"
                }
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
        queryset = get_role_model().objects.filter(
            organization=self.organization)
        # `RoleSerializer` will expand `user` and `role_description`.
        queryset = queryset.select_related('user').select_related(
            'role_description')
        return queryset


class RoleListAPIView(RoleSmartListMixin, InvitedRequestedListMixin,
                      RoleQuerysetBaseMixin, ListAPIView):
    """
    Lists users and their role on an profile

    **Tags**: rbac, list, subscriber, rolemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/xia/roles HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "invited_count": 0,
            "requested_count": 0,
            "results": [
                {
                    "created_at": "2022-01-01T00:00:00Z",
                    "role_description": {
                        "title": "Manager",
                        "slug": "manager",
                        "profile": null
                    },
                    "user": {
                        "slug": "xia",
                        "username": "xia",
                        "printable_name": "Xia Lee",
                        "picture": null
                    },
                    "request_key": "1",
                    "grant_key": null
                }
            ]
        }
    """
    search_fields = (
        'user',
        'user__full_name',
        'user__email',
        'role',
        'role__title'
    )

    serializer_class = get_role_serializer()
    pagination_class = RoleListPagination


class RoleByDescrQuerysetMixin(RoleDescriptionMixin, RoleQuerysetBaseMixin):
    # We cannot use `InvitedRequestedListMixin` here because `role_description`
    # will be None on requested roles. We thus need a `role_description = X
    # *OR* request_key IS NOT NULL`. Calls to more and more refined `filter`
    # through class inheritence only allows us to implement `*AND*`.
    role_status_param = 'role_status'

    def get_queryset(self):
        query_serializer = QueryParamRoleStatusSerializer(
            data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)
        role_status = query_serializer.validated_data.get(
            self.role_status_param, '')

        queryset = super(RoleByDescrQuerysetMixin, self).get_queryset()
        self.request.requested_count = queryset.filter(
            request_key__isnull=False).count()
        # We have to get the count of invited here otherwise
        # `GET /api/profile/{organization}/roles/manager?role_status=requested`
        # will always return zero invited users.
        self.request.invited_count = queryset.filter(
            role_description=self.role_description,
            grant_key__isnull=False).count()

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
    Lists users of a specific role type on a profile

    Lists the specified role assignments for a profile.

    **Tags**: rbac, list, subscriber, rolemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/cowork/roles/manager HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "invited_count": 0,
            "requested_count": 0,
            "results": [
                {
                    "created_at": "2023-01-01T00:00:00Z",
                    "role_description": {
                        "name": "Manager",
                        "slug": "manager"
                    },
                    "user": {
                        "slug": "alice",
                        "username": "alice",
                        "printable_name": "Alice Doe",
                        "picture": null
                    },
                    "request_key": "1",
                    "grant_key": null
                }
            ]
        }
    """
    search_fields = (
        'user',
        'user__full_name',
        'user__email'
    )

    serializer_class = get_role_serializer()
    pagination_class = RoleListPagination

    def get_serializer_class(self):
        if self.request.method.lower() == 'post':
            return RoleCreateSerializer
        return super(RoleByDescrListAPIView, self).get_serializer_class()

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        grant_key = None
        serializer = self.get_serializer(data=request.data)
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
            query_serializer = QueryParamForceSerializer(
                data=self.request.query_params)
            query_serializer.is_valid(raise_exception=True)
            force = query_serializer.validated_data.get('force', False)
            if not force:
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
            reason = force_str(reason)
        role, created = self.organization.add_role(
            user, self.role_description, grant_key=grant_key,
            extra=serializer.validated_data.get('extra'),
            reason=reason, request_user=request.user)
        if created:
            resp_status = status.HTTP_201_CREATED
        else:
            resp_status = status.HTTP_200_OK

        resp_serializer_class = super(
            RoleByDescrListAPIView, self).get_serializer_class()
        resp_serializer = resp_serializer_class(#pylint:disable=not-callable
            role, context=self.get_serializer_context())
        return Response(resp_serializer.data, status=resp_status,
            headers=self.get_success_headers(resp_serializer.data))

    @extend_schema(operation_id='profile_roles_list_by_role')
    def get(self, request, *args, **kwargs):
        return super(RoleByDescrListAPIView, self).get(
            request, *args, **kwargs)

    @extend_schema(parameters=[QueryParamForceSerializer], responses={
      201: OpenApiResponse(get_role_serializer())})
    def post(self, request, *args, **kwargs):
        """
        Creates a role

        Attaches a user to a specified billing profile with a {role},
        typically granting permissions to the user with regards
        to managing the profile
        (see :doc:`Flexible Security Framework <security>`).

        **Tags**: rbac, subscriber, rolemodel

        **Examples**

        .. code-block:: http

            POST /api/profile/xia/roles/manager HTTP/1.1

        .. code-block:: json

            {
              "slug": "xia"
            }

        responds

        .. code-block:: json

            {
                "created_at": "2023-01-01T00:00:00Z",
                "role_description": {
                    "created_at": "2023-01-01T00:00:00Z",
                    "title": "Profile Manager",
                    "slug": "manager",
                    "is_global": true
                },
                "user": {
                    "slug": "xia",
                    "username": "xia",
                    "printable_name": "Xia Lee",
                    "picture": null
                },
                "grant_key": null
            }
        """
        return super(RoleByDescrListAPIView, self).post(
            request, *args, **kwargs)


class RoleDetailBaseAPIView(RoleMixin, RetrieveModelMixin, DestroyModelMixin,
                            GenericAPIView):

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.kwargs.pop('role') # If we leave 'role' in kwargs, we can't deny
                                # requests that haven't been accepted yet.
        queryset = self.get_queryset()
        roles = [str(role.role_description) for role in queryset
            if role.role_description]
        LOGGER.info("Remove roles %s for user '%s' on organization '%s'",
            roles, self.user, self.organization,
            extra={'event': 'remove-roles', 'user': self.user,
                'organization': self.organization.slug, 'roles': roles})
        queryset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoleDetailAPIView(UpdateModelMixin, RoleDetailBaseAPIView):
    """
    Retrieves a role through a profile

    Retrieves the role of a user on a profile.

    **Tags**: rbac, subscriber, rolemodel

    **Examples**

    .. code-block:: http

        GET /api/profile/xia/roles/manager/xia HTTP/1.1

    responds

    .. code-block:: json

        {
            "created_at": "2023-01-01T00:00:00Z",
            "role_description": {
                "created_at": "2023-01-01T00:00:00Z",
                "title": "Profile Manager",
                "slug": "manager",
                "is_global": true
            },
            "user": {
                "slug": "xia",
                "username": "xia",
                "printable_name": "Xia Lee",
                "picture": null
            },
            "grant_key": null
        }
    """
    serializer_class = get_role_serializer()

    @extend_schema(operation_id='profile_roles_invite', request=None)
    def post(self, request, *args, **kwargs):#pylint:disable=unused-argument
        """
        Sends invite notification for a role

        Re-sends the notification that the {user} was granted a {role}
        on the specified billing profile.

        **Tags**: rbac, subscriber, rolemodel

        **Examples**

        .. code-block:: http

            POST /api/profile/xia/roles/manager/xia HTTP/1.1

        responds

        .. code-block:: json

            {
                "created_at": "2023-01-01T00:00:00Z",
                "role_description": {
                    "created_at": "2023-01-01T00:00:00Z",
                    "title": "Profile Manager",
                    "slug": "manager",
                    "is_global": true
                },
                "user": {
                    "slug": "xia",
                    "username": "xia",
                    "printable_name": "Xia Lee",
                    "picture": null
                },
                "grant_key": null
            }
        """
        role = self.get_object()
        signals.role_grant_created.send(sender=__name__,
            role=role, reason=None, request_user=request.user)
        role.detail = _("Invite for %(username)s has been sent") % {
            'username': role.user.username
        }
        serializer = self.get_serializer(role)
        return Response(serializer.data)


    def put(self, request, *args, **kwargs):
        """
        Updates role meta information

        Updates meta information for a role.

        **Tags**: rbac, subscriber, rolemodel

        **Examples**

        .. code-block:: http

            PUT /api/profile/xia/roles/manager/xia HTTP/1.1

        .. code-block:: json

            {
              "extra": {"kinship": "self"}
            }

        responds

        .. code-block:: json

            {
                "created_at": "2023-01-01T00:00:00Z",
                "role_description": {
                    "created_at": "2023-01-01T00:00:00Z",
                    "title": "Profile Manager",
                    "slug": "manager",
                    "is_global": true
                },
                "user": {
                    "slug": "xia",
                    "username": "xia",
                    "printable_name": "Xia Lee",
                    "picture": null
                },
                "grant_key": null,
                "extra": {"kinship": "self"}
            }
        """
        return self.update(request, *args, **kwargs)


    def delete(self, request, *args, **kwargs):
        """
        Deletes a role through a profile

        Dettaches a {user} from one or all roles with regards to the
        specified billing profile, typically resulting in revoking
        permissions from the user to manage part of the profile.

        **Tags**: rbac, subscriber, rolemodel

        **Examples**

        .. code-block:: http

            DELETE /api/profile/xia/roles/manager/xia HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)


class AccessibleDetailAPIView(RoleDetailBaseAPIView):
    """
    Retrieves a role through a user

    Retrieves the accessible role for a profile by a user.

    **Tags**: rbac, subscriber, rolemodel

    **Examples**

    .. code-block:: http

        GET /api/users/xia/accessibles/manager/cowork HTTP/1.1

    responds

    .. code-block:: json

        {
            "created_at": "2023-01-01T00:00:00Z",
            "role_description": {
                "created_at": "2023-01-01T00:00:00Z",
                "title": "Profile Manager",
                "slug": "manager",
                "is_global": true
            },
            "profile": {
                "slug": "cowork",
                "printable_name": "ABC Corp.",
                "type": "organization",
                "credentials": false
            },
            "request_key": null
        }
    """
    serializer_class = AccessibleSerializer

    def get_queryset(self):
        # We never take the `role_description` into account when removing
        # on the accessibles page.
        queryset = get_role_model().objects.filter(
            organization=self.organization, user=self.user)
        # `RoleSerializer` will expand `user` and `role_description`.
        queryset = queryset.select_related('user').select_related(
            'role_description')
        return queryset


    @extend_schema(operation_id='users_accessibles_invite', request=None)
    def post(self, request, *args, **kwargs):
        """
        Sends request notification for role

        Re-sends the notification that the {user} is requesting a {role}
        on the specified billing profile.

        **Tags**: rbac, user, rolemodel

        **Examples**

        .. code-block:: http

            POST /api/users/xia/accessibles/manager/cowork HTTP/1.1

        responds

        .. code-block:: json

            {
                "created_at": "2023-01-01T00:00:00Z",
                "role_description": {
                    "created_at": "2023-01-01T00:00:00Z",
                    "title": "Profile Manager",
                    "slug": "manager",
                    "is_global": true
                },
                "profile": {
                    "slug": "cowork",
                    "printable_name": "ABC Corp.",
                    "type": "organization",
                    "credentials": false
                },
                "request_key": null
            }
        """
        role = self.get_object()
        signals.role_request_created.send(sender=__name__,
            role=role, reason=None, request_user=request.user)
        serializer = self.get_serializer(role)
        return Response(serializer.data)


    def delete(self, request, *args, **kwargs):
        """
        Deletes a role through a user

        Dettaches {user} from one or all roles with regards to the
        specified billing profile, typically resulting in revoking
        permissions from this user to manage part of the profile.

        The API is typically used within an HTML
        `connected profiles page </docs/guides/themes/#dashboard_users_roles>`_
        as present in the default theme.

        **Tags**: rbac

        **Examples**

        .. code-block:: http

            DELETE /api/users/xia/accessibles/manager/cowork HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)


class RoleAcceptAPIView(UserMixin, GenericAPIView):

    serializer_class = AccessibleSerializer

    @extend_schema(request=None)
    def put(self, request, *args, **kwargs):#pylint:disable=unused-argument
        """
        Accepts role invite

        Accepts a role identified by {verification_key}.

        The API is typically used within an HTML
        `connected profiles page </docs/guides/themes/#dashboard_users_roles>`_
        as present in the default theme.

        **Tags**: rbac, user, rolemodel

        **Examples**

        .. code-block:: http

            PUT /api/users/xia/accessibles/accept/\
a00000d0a0000001234567890123456789012345 HTTP/1.1

        responds

        .. code-block:: json

            {
                "created_at": "2023-01-01T00:00:00Z",
                "role_description": {
                    "created_at": "2023-01-01T00:00:00Z",
                    "title": "Profile Manager",
                    "slug": "manager",
                    "is_global": true
                },
                "profile": {
                    "slug": "cowork",
                    "printable_name": "ABC Corp.",
                    "type": "organization",
                    "credentials": false
                }
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
    Lists billing profiles with a user as a profile manager

    Returns a list of {{PAGE_SIZE}} of profiles

    The queryset can be further refined to match a search filter (``q``)
    and/or a range of dates ([``start_at``, ``ends_at``]),
    and sorted on specific fields (``o``).

    **Tags**: rbac, profile, user, usermodel

    **Examples**

    .. code-block:: http

        GET /api/users/xia/profiles?o=created_at HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "created_at": "2023-01-01T00:00:00Z",
                    "email": "xia@locahost.localdomain",
                    "full_name": "Xia Lee",
                    "printable_name": "Xia Lee",
                    "slug": "xia",
                    "phone": "555-555-5555",
                    "street_address": "185 Berry St #550",
                    "locality": "San Francisco",
                    "region": "CA",
                    "postal_code": "",
                    "country": "US",
                    "default_timezone": "Europe/Kiev",
                    "is_provider": false,
                    "is_bulk_buyer": false,
                    "type": "personal",
                    "picture": ""
            }]
        }
    """
    serializer_class = OrganizationDetailSerializer
    convert_from_personal_param = 'convert_from_personal'

    def paginate_queryset(self, queryset):
        page = super(UserProfileListAPIView, self).paginate_queryset(queryset)
        page = self.decorate_personal(page)
        return page

    def get_serializer_class(self):
        if self.request.method.lower() == 'post':
            return OrganizationCreateSerializer
        return super(UserProfileListAPIView, self).get_serializer_class()

    def get_queryset(self):
        queryset = get_organization_model().objects.accessible_by(
            self.user, role_descr=settings.MANAGER)
        return queryset


    @extend_schema(responses={
      201: OpenApiResponse(OrganizationDetailSerializer)})
    def post(self, request, *args, **kwargs):
        """
        Creates a connected profile

        This end-point creates a new profile whose manager is {user}.
        It returns an error if the profile already exists.

        If you want to request access to an already existing profile,
        see the `accessibles <#createAccessibleByList>`_
        end-point.

        **Tags**: rbac, profile, user, usermodel

        **Examples**

        .. code-block:: http

            POST /api/users/xia/profiles HTTP/1.1

        .. code-block:: json

            {
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

    def is_valid_convert_to_organization_request(self, organization):
        return organization and organization.attached_user() == self.user

    def create(self, request, *args, **kwargs): #pylint:disable=unused-argument
        #pylint:disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = dict(serializer.validated_data)

        # If we're creating an organization from a personal profile
        query_serializer = QueryParamPersonalProfSerializer(
            data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        convert_from_personal = query_serializer.validated_data.get(
            self.convert_from_personal_param, False)

        if convert_from_personal:
            organization = self.get_queryset().filter(
                slug__exact=self.user.username).first()

            if not self.is_valid_convert_to_organization_request(organization):
                return Response({'error': _('Invalid request.')},
                    status=status.HTTP_400_BAD_REQUEST)

            organization.full_name = serializer.validated_data.get('full_name')
            organization.slug = serializer.validated_data.get('slug', None)
            organization.save()

            return Response({"detail":
                _("Successfully converted personal profile to organization.")},
                status=status.HTTP_200_OK)

        if 'email' not in validated_data:
            # email is optional to create the profile but it is required
            # to save the record in the database.
            validated_data.update({'email': request.user.email})
        if 'full_name' not in validated_data:
            # full_name is optional to create the profile but it is required
            # to save the record in the database.
            validated_data.update({'full_name': ""})

        # creates profile
        with transaction.atomic():
            organization = self.create_organization(validated_data)
            organization.add_manager(self.user)
        self.decorate_personal(organization)

        # returns created profile
        serializer = self.serializer_class(
            instance=organization, context=self.get_serializer_context())
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
            status=status.HTTP_201_CREATED, headers=headers)
