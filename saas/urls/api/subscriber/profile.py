# Copyright (c) 2022, DjaoDjin inc.
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

"""
URLs API for profile resources (managers, custom roles and subscriptions)
"""

from .... import settings
from ....api.organizations import (
    OrganizationDetailAPIView, OrganizationPictureAPIView)
from ....api.subscriptions import (SubscriptionDetailAPIView,
    SubscribedSubscriptionListAPIView)
from ....compat import path


urlpatterns = [
    path('profile/<slug:%s>/subscriptions/<slug:subscribed_plan>' %
        settings.PROFILE_URL_KWARG,
        SubscriptionDetailAPIView.as_view(),
        name='saas_api_subscription_detail'),
    path('profile/<slug:%s>/subscriptions' %
        settings.PROFILE_URL_KWARG,
        SubscribedSubscriptionListAPIView.as_view(),
        name='saas_api_subscription_list'),
    path('profile/<slug:%s>/picture' %
        settings.PROFILE_URL_KWARG,
        OrganizationPictureAPIView.as_view(),
        name='saas_api_organization_picture'),
    path('profile/<slug:%s>' %
        settings.PROFILE_URL_KWARG,
        OrganizationDetailAPIView.as_view(), name='saas_api_organization'),
]
