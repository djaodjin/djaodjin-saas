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
import time
from time import mktime
from datetime import datetime, date, timedelta

from django.db.models import Sum
from django.shortcuts import render_to_response
from django.views.decorators.http import require_GET
from django.utils.timezone import utc
from django.db.models import Max
from django.db.models import Count, Min, Sum, Avg

from saas.decorators import requires_agreement
from saas.views.auth import valid_manager_for_organization
from saas.models import Organization, Transaction, NewVisitors
from saas.views.chart import organization_usage

@require_GET
@requires_agreement('terms_of_use')

def statistic(request):
    
    newvisitor = NewVisitors.objects.all()
    
    if not newvisitor:
        return render_to_response("saas/stat.html")
    
    Min_date = NewVisitors.objects.all().aggregate(Min('date'))
    Max_date = NewVisitors.objects.all().aggregate(Max('date'))
    
    Min_date = Min_date.get('date__min',0)
    Max_date = Max_date.get('date__max',0)
    
    date_tabl = []
    n={}
    
    for new in newvisitor:
        date_tabl +=[{"x":new.date,"y":new.visitors_number}]
    
    new_visitor=[]
    d = Min_date
    delta = timedelta(days=1)
    while d <= Max_date:
        new_visitor += [{"x":d,"y":0}]
        d += delta

    diff = len(new_visitor) - len(date_tabl)

    for i in range(diff):
        date_tabl+=[{"x":date(day=1, month=1, year=1900),"y":0}]

    print(date_tabl)

    for i in range(len(new_visitor)):
        for j in range(len(date_tabl)):
            if new_visitor[i]["x"] == date_tabl[j]["x"]:
                new_visitor[i]["y"]=date_tabl[j]["y"]
            if date_tabl[j] == 0 :
                new_visitor[i]["x"] = date_tabl[j]["x"]


    for t in new_visitor:
        t["x"] = datetime.strftime(t["x"],"%Y/%m/%d")
    
    context = {'data' : [{"key":"new visitor","values": new_visitor}]}

    return render_to_response("saas/stat.html", context)