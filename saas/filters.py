# Copyright (c) 2018, DjaoDjin inc.
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

from django.utils.encoding import force_text
from rest_framework.compat import coreapi, coreschema


class SortableSearchableFilterBackend(object):

    def __init__(self, sort_fields, search_fields):
        self.sort_fields = sort_fields
        self.search_fields = search_fields

    def __call__(self):
        return self

    def filter_queryset(self, request, queryset, view):
        #pylint:disable=no-self-use,unused-argument
        return queryset

    def get_schema_fields(self, view):
        #pylint:disable=unused-argument
        assert coreapi is not None, 'coreapi must be installed to use'\
            ' `get_schema_fields()`'
        assert coreschema is not None, 'coreschema must be installed '\
            'to use `get_schema_fields()`'
        sort_fields_description = "sort by %s" % ', '.join([
            field[1] for field in self.sort_fields])
        search_fields_description = "search for matching text in %s"  % (
            ', '.join([field_name for field_name in self.search_fields]))

        fields = [
            coreapi.Field(
                name='o',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='O',
                    description=force_text(sort_fields_description)
                )
            ),
            coreapi.Field(
                name='ot',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='OT',
                    description=force_text(
                        "sort by natural ascending or descending order")
                )
            ),
            coreapi.Field(
                name='q',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='Q',
                    description=force_text(search_fields_description)
                )
            )
        ]
        return fields


class SortableDateRangeSearchableFilterBackend(SortableSearchableFilterBackend):

    def __init__(self, sort_fields, search_fields):
        super(SortableDateRangeSearchableFilterBackend, self).__init__(
            sort_fields, search_fields)

    def get_schema_fields(self, view):
        fields = super(SortableDateRangeSearchableFilterBackend,
            self).get_schema_fields(view)
        fields += [
            coreapi.Field(
                name='start_at',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='StartAt',
                    description=force_text("date/time in ISO format"\
                        " after which records were created.")
                )
            ),
            coreapi.Field(
                name='ends_at',
                required=False,
                location='query',
                schema=coreschema.String(
                    title='EndsAt',
                    description=force_text("date/time in ISO format"\
                        " before which records were created.")
                )
            ),
        ]
        return fields
