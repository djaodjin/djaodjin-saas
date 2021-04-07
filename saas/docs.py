# Copyright (c) 2021, Djaodjin Inc.
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

#pylint:disable=unused-argument,unused-import

try:
    from drf_yasg.openapi import Response as OpenAPIResponse, Parameter, IN_PATH
    from drf_yasg.utils import no_body, swagger_auto_schema
except ImportError:
    from functools import wraps
    from .compat import available_attrs

    IN_PATH = 0

    class no_body(object):#pylint:disable=invalid-name
        pass

    def swagger_auto_schema(function=None, **kwargs):
        """
        Dummy decorator when drf_yasg is not present.
        """
        def decorator(view_func):
            @wraps(view_func, assigned=available_attrs(view_func))
            def _wrapped_view(request, *args, **kwargs):
                return view_func(request, *args, **kwargs)
            return _wrapped_view

        if function:
            return decorator(function)
        return decorator

    class OpenAPIResponse(object):
        """
        Dummy response object to document API.
        """
        def __init__(self, *args, **kwargs):
            pass

    class Parameter(object):
        """
        Dummy object to document API.
        """
        def __init__(self, *args, **kwargs):
            pass
