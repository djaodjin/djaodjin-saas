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
from django.contrib.auth.models import User

@require_GET
@requires_agreement('terms_of_use')
def statistic(request):
    # New vistor analyse
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

    for t in date_tabl:
        t["x"] = datetime.strftime(t["x"],"%Y/%m/%d")
        t["y"] = t["y"]/5

    d = Min_date
    delta = timedelta(days=1)
    while d <= Max_date:
        j=len(date_tabl)
        t=[]
        for i in range(j):
            if date_tabl[i]["x"] == datetime.strftime(d,"%Y/%m/%d"):
                t +=[i]
        if len(t) == 0 :
            date_tabl += [{"x":datetime.strftime(d,"%Y/%m/%d"),"y":0}]
            d+=delta
        else :
            d+=delta

    date_tabl.sort()

    ########################################################
    # Conversion visitors to trial
    user = User.objects.all()
    date_joined_username =[]
    for us in user:
        if datetime.strftime(us.date_joined,"%Y/%m/%d")> datetime.strftime(Min_date,"%Y/%m/%d") and  datetime.strftime(us.date_joined,"%Y/%m/%d")< datetime.strftime(Max_date,"%Y/%m/%d"):
            date_joined_username += [{"date" : us.date_joined, "user":str(us.username)}]

    #print(rien)

    user_per_joined_date = {}
    for datas in date_joined_username:
        key  = datas["date"]
        if not key in user_per_joined_date:
            user_per_joined_date[key] = []
        user_per_joined_date[key]+= [datas["user"]]

    
    trial=[]
    for t in user_per_joined_date.keys():
        trial +=[{"x":t, "y":len(user_per_joined_date[t])}]

    Min_date_trial = User.objects.all().aggregate(Min('date_joined'))
    Max_date_trial = User.objects.all().aggregate(Max('date_joined'))

    Min_date_trial = Min_date_trial.get('date_joined__min',0)
    Max_date_trial = Max_date_trial.get('date_joined__max',0)
    
    for t in trial:
        t["x"] = datetime.strftime(t["x"],"%Y/%m/%d")
    d=Min_date
    delta = timedelta(days=1)
    while d <= Max_date:
        j=len(trial)
        t=[]
        for i in range(j):
            if trial[i]["x"] == datetime.strftime(d,"%Y/%m/%d"):
                t +=[i]
        if len(t) == 0 :
            trial += [{"x":datetime.strftime(d,"%Y/%m/%d"),"y":0}]
            d+=delta
        else :
            d+=delta
    
    trial.sort()
    
    context = {'data' : [{"key":"Signup number" , "color":"#d62728" , "values":trial},{"key":"New visitor number","values": date_tabl}]}
    
    return render_to_response("saas/stat.html", context)
