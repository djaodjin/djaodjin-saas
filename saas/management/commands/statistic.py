# Copyright (c) 2013, Fortylines LLC
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Command for the cron job. Daily statistics"""

import datetime, sys
import datetime
import time
from time import mktime
from datetime import datetime

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from saas.models import Organization, Transaction, NewVisitors

from saas.models import Organization

class Command(BaseCommand):
    
    
    help = 'Save new vistor datas into the database. This command needs the path of the log file to analyse.'
    
    def handle(self, args, **options):
    
        visitors = []
        values=[]
        log3 = []
        browser = []
        date = []
        log = open(args)
    
        #delete all bot
        rob  = "bot"
        pub = "Pub"
        spy = "Spider"
        spy2 = "spider"
        goog = "google"
        rob2="AhrefsBot"
    
        for ligne in log.readlines():
            log1 = ligne
            if (not rob  in ligne) and (not pub in ligne) and (not spy in ligne) and (not spy2 in ligne) and (not goog in ligne) and (not rob2 in ligne) :
                visitors += [ligne]
    
        print(len(visitors))

        # create a dictionnary of IP, browser per date
        for i in range(len(visitors)):
            browser_name = (visitors[i].split('"'))[5]
            log3 = visitors[i].split("[")
            date = log3[1].split("]")
            datee =(date[0].split(":"))[0]
        
            IP = log3[0].split(" -")[0]
        
            c = time.strptime(datee,"%d/%b/%Y")
            dt = datetime.strftime(datetime.fromtimestamp(mktime(c)),"%Y/%m/%d")
            browser += [{"IP": IP, "browser" : browser_name,
                    "date": dt }]

            # all dates per visitors
        dates_per_unique_visitor = {}
        for datas in browser:
            key  = (datas["IP"], datas["browser"])
            if not key in dates_per_unique_visitor:
                dates_per_unique_visitor[key] = []
            dates_per_unique_visitor[key]+= [datas["date"]]

        final_list ={}
        for it in dates_per_unique_visitor:
            key = dates_per_unique_visitor[it][0]
            if not key in final_list:
                final_list[key] = []
       
            final_list[key]+=[it]

        table=[]
        total = []
        total2 =0
        final_list2 = sorted(final_list.items())


        for it in range(len(final_list2)):
            total += [len(final_list2[it][1])]
            total2 += len(final_list2[it][1])
            c = time.strptime(final_list2[it][0],"%Y/%m/%d")
            
            dt = datetime.strftime(datetime.fromtimestamp(mktime(c)),"%Y-%m-%d")
            
            new = NewVisitors()
            new.date =dt
            new.visitors_number = len(final_list2[it][1])
        
            # check in database if the date exists and if not save into the database
            newvisitor = NewVisitors.objects.filter(date=dt)
            if not newvisitor:
                new.save()
