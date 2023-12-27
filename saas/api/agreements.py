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

from django.db import IntegrityError
from django.template.defaultfilters import slugify
from rest_framework import generics, status
from rest_framework.mixins import (CreateModelMixin, DestroyModelMixin,
    UpdateModelMixin)
from rest_framework.response import Response

from .serializers import (AgreementSerializer, AgreementCreateSerializer,
    AgreementDetailSerializer, AgreementUpdateSerializer)
from ..docs import extend_schema, OpenApiResponse
from ..filters import OrderingFilter, SearchFilter
from ..models import Agreement
from ..utils import handle_uniq_error


class AgreementSmartListMixin(object):

    search_fields = (
        'slug',
        'title'
    )
    ordering_fields = (
        ('title', 'title'),
        ('updated_at', 'updated_at'),
    )
    ordering = ('title',)

    filter_backends = (OrderingFilter, SearchFilter,)


class AgreementListAPIView(AgreementSmartListMixin, generics.ListAPIView):
    """
    List legal agreements

    Returns a list of {{PAGE_SIZE}} legal agreements a user might be requested
    to sign such as "terms of use" or "security policy". This end point can be
    used by unauthenticated users. As such it is perfect for
    `legal disclosure pages </docs/guides/themes/#workflow_legal_index>`_.

    **Tags**: visitor

    **Examples**

    .. code-block:: http

         GET /api/legal HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "terms-of-use",
                    "title": "Terms of Use",
                    "updated_at": "2023-08-16T00:00:00Z"
                }
            ]
        }
    """
    serializer_class = AgreementSerializer
    queryset = Agreement.objects.all()


class AgreementListCreateAPIView(CreateModelMixin, AgreementListAPIView):
    """
    List legal agreements (broker)

    List all legal agreements a user might be requested to sign.
    This is a convenience API for authenticated broker profile managers.
    For listing legal agreements publicly, see
    `GET /api/legal <#listAgreement>`_.

    **Tags**: broker

    **Examples**

    .. code-block:: http

         GET /api/agreements HTTP/1.1

    responds

    .. code-block:: json

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "slug": "terms-of-use",
                    "title": "Terms of Use",
                    "updated_at": "2023-08-16T00:00:00Z"
                }
            ]
        }
    """
    def get_serializer_class(self):
        if self.request.method.lower() in ('post',):
            return AgreementCreateSerializer
        return super(AgreementListCreateAPIView, self).get_serializer_class()

    @extend_schema(responses={
        201: OpenApiResponse(AgreementSerializer)})
    def post(self, request, *args, **kwargs): #pylint:disable=unused-argument
        """
        Creates a legal agreement

        Creates a new legal agreement a user might be requested to sign.

        All users visiting an URL decorated with an "Agreed to {agreement}"
        access control rule will be prompted to sign the agreement.

        **Tags**: broker

        **Examples**

        .. code-block:: http

             POST /api/agreements HTTP/1.1

        .. code-block:: json

            {
                "title": "Terms of Use"
            }

        responds

        .. code-block:: json

            {
                "slug": "terms-of-use",
                "title": "Terms of Use",
                "updated_at": "2023-08-16T00:00:00Z"
            }
        """
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        #pylint:disable=unused-argument
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(slug=slugify(serializer.validated_data['title']))
        except IntegrityError as err:
            handle_uniq_error(err)
        headers = self.get_success_headers(serializer.data)
        return Response(AgreementSerializer().to_representation(
            serializer.instance), status=status.HTTP_201_CREATED,
            headers=headers)


class AgreementDetailAPIView(generics.RetrieveAPIView):
    """
    Retrieves a legal agreement

    Retrieves the text of legal agreement a user might be requested to sign.
    This end point can be used by unauthenticated users. As such it is perfect
    for `legal disclosure pages
    </docs/guides/themes/#workflow_legal_agreement>`_.

    **Tags**: broker, visitor

    **Examples**

    .. code-block:: http

         GET /api/legal/terms-of-use HTTP/1.1

    responds

    .. code-block:: json

           {
                "slug": "terms-of-use",
                "title": "Terms of Use",
                "updated_at": "2023-08-16T00:00:00Z",
                "text": "..."
            }
    """
    serializer_class = AgreementDetailSerializer
    queryset = Agreement.objects.all()
    lookup_field = 'slug'
    lookup_url_kwarg = 'agreement'


class AgreementUpdateAPIView(UpdateModelMixin, DestroyModelMixin,
                             AgreementDetailAPIView):
    """
    Retrieves a legal agreement (broker)

    Retrieves the text of legal agreement a user might be requested to sign.
    This is a convenience API for authenticated broker profile managers.
    For retrieving the text of a legal agreement publicly, see
    `GET /api/legal/{agreement} <#retrieveAgreementDetail>`_.

    **Tags**: broker

    **Examples**

    .. code-block:: http

         GET /api/agreements/terms-of-use HTTP/1.1

    responds

    .. code-block:: json

           {
                "slug": "terms-of-use",
                "title": "Terms of Use",
                "updated_at": "2023-08-16T00:00:00Z",
                "text": "..."
            }
    """
    serializer_class = AgreementDetailSerializer
    lookup_url_kwarg = 'document'

    def get_serializer_class(self):
        if self.request.method.lower() in ('put', 'patch'):
            return AgreementUpdateSerializer
        return super(AgreementUpdateAPIView, self).get_serializer_class()

    @extend_schema(responses={
        200: OpenApiResponse(AgreementDetailSerializer)})
    def put(self, request, *args, **kwargs): #pylint:disable=unused-argument
        """
        Updates a legal agreement

        Updates the latest modification date of a legal agreement a user might
        be requested to sign.

        All users visiting an URL decorated with an "Agreed to {agreement}"
        access control rule will be prompted to sign the agreement again
        if the last time they signed is older that the `updated_at` date set
        here.

        **Tags**: broker

        **Examples**

        .. code-block:: http

             PUT /api/agreements/terms-of-use HTTP/1.1

        .. code-block:: json

            {
                "title": "Terms of Use",
                "updated_at": "2023-08-16T00:00:00Z"
            }

        responds

        .. code-block:: json

            {
                "slug": "terms-of-use",
                "title": "Terms of Use",
                "updated_at": "2023-08-16T00:00:00Z",
                "text": "..."
            }
        """
        return self.update(request, *args, **kwargs)

    @extend_schema(responses={
        200: OpenApiResponse(AgreementDetailSerializer)})
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


    def delete(self, request, *args, **kwargs): #pylint:disable=unused-argument
        """
        Deletes a legal agreement

        Deletes a legal agreement a user might be requested to sign.

        This will remove the agreement as well as all user signatures of it.

        **Tags**: broker

        **Examples**

        .. code-block:: http

             DELETE /api/agreements/terms-of-use HTTP/1.1
        """
        return self.destroy(request, *args, **kwargs)
