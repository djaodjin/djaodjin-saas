# Copyright (c) 2013, Sebastien Mirolo
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.

import datetime

from django.db.models import Sum
from django.shortcuts import render_to_response
from django.views.decorators.http import require_GET
from django.utils.timezone import utc

from saas.decorators import requires_agreement
from saas.views.auth import valid_manager_for_organization
from saas.models import Organization, Transaction
from saas.views.chart import organization_usage

@require_GET
@requires_agreement('terms_of_use')
def organization_overall(request):
    
    organizations = Organization.objects.all()
    all_values =[]
    
    for organization_all in organizations:
        organization = valid_manager_for_organization(request.user, organization_all)
        values = []
        today = datetime.date.today()
        end = datetime.datetime(day=today.day, month=today.month, year=today.year,
                                tzinfo=utc)
        
        for month in range(0, 12):
            first = datetime.datetime(day=1, month=end.month, year=end.year,
                                      tzinfo=utc)
            usages = Transaction.objects.filter(
                                                orig_organization=organization, orig_account='Usage',
                                                created_at__lt=first).aggregate(Sum('amount'))
            amount = usages.get('amount__sum',0)
            if not amount:
                # The key could be associated with a "None".
                amount = 0
            values += [{ "x": datetime.date.strftime(first, "%Y/%m/%d"),
                       "y": amount }]
            end = first - datetime.timedelta(days=1)
        all_values += [{"key":str(organization_all.name),"values":values}]

    context ={'data' : all_values}
    
    
    
    return render_to_response("saas/general_chart.html", context)