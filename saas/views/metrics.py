# Copyright (c) 2015, DjaoDjin inc.
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

import csv, json
from datetime import datetime, date, timedelta
from StringIO import StringIO
from types import MethodType

from django.db.models import Min, Sum, Max
from django.http import HttpResponse
from django.utils.datastructures import SortedDict
from django.utils.dateparse import parse_datetime
from django.utils.timezone import utc
from django.views.generic import ListView, TemplateView, View
from django.core.serializers.json import DjangoJSONEncoder

# importing views for their data retrieval methods (maybe should be managers?)
from saas.api.metrics import (ChurnedAPIView, RegisteredAPIView,
    SubscribedAPIView)
from saas.api.coupons import SmartCouponListMixin
# NB: there is another CouponMixin
from saas.api.coupons import CouponMixin as CouponAPIMixin
from saas.mixins import CouponMixin, ProviderMixin, MetricsMixin
from saas.views.auth import valid_manager_for_organization
from saas.managers.metrics import (active_subscribers,
    aggregate_monthly_transactions, churn_subscribers,
    monthly_balances, month_periods)
from saas.models import (CartItem, Organization, Plan, Transaction,
    NewVisitors)
from saas.compat import User
from saas.utils import datetime_or_now


class CouponMetricsView(CouponMixin, ListView):
    """
    Performance of Coupon based on CartItem.
    """

    model = CartItem
    paginate_by = 10
    template_name = 'saas/coupon_metrics.html'

    def get_queryset(self):
        queryset = super(CouponMetricsView, self).get_queryset().filter(
            coupon=self.get_coupon(), recorded=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super(CouponMetricsView, self).get_context_data(**kwargs)
        context.update({'coupon_performance_count': CartItem.objects.filter(
            coupon=self.get_coupon(), recorded=True).count()})
        return context


class CouponMetricsDownloadView(ProviderMixin, View):

    headings = [
        'Code',
        'Percentage',
        'Name',
        'Email',
        'Plan',
    ]

    def get(self, request, **kwargs):
        class CouponAPIDummyView(SmartCouponListMixin, CouponAPIMixin):
            '''
            Stand-in for a view so that django-extra-views can create a
            filtered QuerySet for us. This guarantees that we consider only the
            same Coupons that are displayed to the user in the admin display.
            '''
            def __init__(self, request, kwargs):
                self.request = request
                self.kwargs = kwargs

        coupons = CouponAPIDummyView(request, kwargs).get_queryset()

        content = StringIO()
        csv_writer = csv.writer(content)
        csv_writer.writerow(self.headings)
        for cartitem in CartItem.objects.filter(coupon__in=coupons):
            csv_writer.writerow([
                cartitem.coupon.code.encode('utf-8'),
                cartitem.coupon.percent,
                ' '.join([cartitem.user.first_name, cartitem.user.last_name]).\
                    encode('utf-8'),
                cartitem.user.email.encode('utf-8'),
                cartitem.plan.slug.encode('utf-8'),
            ])
        content.seek(0)
        resp = HttpResponse(content, content_type='text/csv')
        resp['Content-Disposition'] = datetime.now().strftime(
            'attachment; filename="coupons-%Y%m%d.csv"')
        return resp


class PlansMetricsView(ProviderMixin, TemplateView):
    """
    Performance of Plans for a time period
    (as a count of subscribers per plan per month)
    """

    template_name = 'saas/plan_metrics.html'

    def get_context_data(self, **kwargs):
        context = super(PlansMetricsView, self).get_context_data(**kwargs)
        organization = self.get_organization()
        table = []
        for plan in Plan.objects.filter(organization=organization):
            values = active_subscribers(
                plan, from_date=self.kwargs.get('from_date'))
            # XXX The template relies on "key" being plan.slug
            table.append({"key": plan.slug, "values": values,
                          "is_active": plan.is_active})
        extra = [{"key": "churn",
            "values": churn_subscribers(
                from_date=self.kwargs.get('from_date'))}]
        data = SortedDict()
        data['subscribers'] = {"title": "Active Subscribers",
                               "table": table, "extra": extra}
        context.update({'title': "Plans",
            "data": data,
            "data_json": json.dumps(data, cls=DjangoJSONEncoder)})
        return context


class RevenueMetricsView(MetricsMixin, TemplateView):
    """
    Generate a table of revenue (rows) per months (columns).
    """

    template_name = 'saas/revenue_metrics.html'

    def get_context_data(self, **kwargs):
        context = super(RevenueMetricsView, self).get_context_data(**kwargs)
        reverse = True
        account_title = 'Payments'
        account = Transaction.FUNDS
        account_table, customer_table, customer_extra = \
            aggregate_monthly_transactions(self.organization, account,
                account_title=account_title, from_date=self.ends_at,
                reverse=reverse)
        data = SortedDict()
        data['amount'] = {"title": "Amount",
                          "unit": "$", "table": account_table}
        data['customers'] = {"title": "Customers",
                             "table": customer_table, "extra": customer_extra}
        context.update({"title": "Revenue Metrics",
            "data": data,
            "data_json": json.dumps(data, cls=DjangoJSONEncoder)})
        return context


class BalancesMetricsView(MetricsMixin, TemplateView):
    """
    Display balances.
    """

    template_name = 'saas/metrics_balances.html'

    def get_context_data(self, **kwargs):
        context = super(BalancesMetricsView, self).get_context_data(**kwargs)
        context.update({'title': 'Balances'})
        return context


class BalancesDownloadView(MetricsMixin, TemplateView):
    """
    Export balance metrics as a CSV file.
    """
    queryname = 'balances'

    def get(self, request, *args, **kwargs): #pylint: disable=unused-argument
        self.cache_fields(request)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = ('attachment; filename="%s.csv"'
            % self.queryname)
        writer = csv.writer(response)
        # column headers
        values = ['name']
        for end_period in month_periods(from_date=self.ends_at):
            values += [end_period]
        writer.writerow(values)
        # rows
        for key in Transaction.objects.distinct_accounts():
            values = [key] + [item[1] for item in monthly_balances(
                self.organization, key, self.ends_at)]
            writer.writerow(values)
        return response


class SubscriberPipelineView(ProviderMixin, TemplateView):

    template_name = "saas/subscriber_pipeline.html"


class SubscriberPipelineDownloadView(ProviderMixin, View):

    queryset_view_map = {
        'registered': RegisteredAPIView,
        'subscribed': SubscribedAPIView,
        'churned': ChurnedAPIView,
    }

    def get(self, request, subscriber_type, **kwargs):
        queryset_view = self.queryset_view_map[subscriber_type]

        class APIViewProxy(queryset_view):
            def __init__(self, provider):
                self.provider = provider
        view_proxy = APIViewProxy(self.get_organization())
        view_proxy.get_range_queryset = MethodType(
            queryset_view.get_range_queryset, view_proxy)

        start_date = datetime_or_now(
            parse_datetime(request.GET.get('start_date', None)))
        end_date = datetime_or_now(
            parse_datetime(request.GET.get('end_date', None)))

        content = StringIO()
        csv_writer = csv.writer(content)
        csv_writer.writerow(['Name', 'Email', 'Registration Date'])
        for org in view_proxy.get_range_queryset(start_date, end_date):
            csv_writer.writerow([
                org.full_name.encode('utf-8'),
                org.email.encode('utf-8'),
                org.created_at])
        content.seek(0)
        resp = HttpResponse(content, content_type='text/csv')
        resp['Content-Disposition'] = \
            'attachment; filename="subscribers-{}-{}.csv"'.format(
                subscriber_type, datetime.now().strftime('%Y%m%d'))
        return resp


class UsageMetricsView(ProviderMixin, TemplateView):

    template_name = "saas/usage_chart.html"

    def get_context_data(self, **kwargs):
        context = super(UsageMetricsView, self).get_context_data(**kwargs)
        organization = self.get_organization()
        # Note: There is a way to get the result in a single SQL statement
        # but that requires to deal with differences in databases
        # (MySQL: date_format, SQLite: strftime) and get around the
        # "Raw query must include the primary key" constraint.
        values = []
        today = date.today()
        end = datetime(day=today.day, month=today.month, year=today.year,
                                tzinfo=utc)
        for _ in range(0, 12):
            first = datetime(day=1, month=end.month, year=end.year,
                                      tzinfo=utc)
            usages = Transaction.objects.filter(
                orig_organization=organization, orig_account='Usage',
                created_at__lt=first).aggregate(Sum('amount'))
            amount = usages.get('amount__sum', 0)
            if not amount:
                # The key could be associated with a "None".
                amount = 0
            values += [{"x": date.strftime(first, "%Y/%m/%d"), "y": amount}]
            end = first - timedelta(days=1)
        context.update({'data': [{"key": "Usage", "values": values}]})
        return context


class OverallMetricsView(TemplateView):

    template_name = "saas/general_chart.html"

    def get_context_data(self, **kwargs):
        organizations = Organization.objects.all()
        all_values = []

        for organization_all in organizations:
            organization = valid_manager_for_organization(
                self.request.user, organization_all)
            values = []
            today = date.today()
            end = datetime(day=today.day, month=today.month, year=today.year,
                                    tzinfo=utc)
            for _ in range(0, 12):
                first = datetime(day=1, month=end.month, year=end.year,
                                          tzinfo=utc)
                usages = Transaction.objects.filter(
                    orig_organization=organization, orig_account='Usage',
                    created_at__lt=first).aggregate(Sum('amount'))
                amount = usages.get('amount__sum', 0)
                if not amount:
                    # The key could be associated with a "None".
                    amount = 0
                values += [{"x": date.strftime(first, "%Y/%m/%d"),
                            "y": amount}]
                end = first - timedelta(days=1)
            all_values += [{
                "key": str(organization_all.slug), "values": values}]
        context = {'data' : all_values}
        return context


class VisitorsView(TemplateView):
    """
    Number of visitors as measured by the website logs.
    """

    template_name = 'saas/stat.html'

    def get_context_data(self, **kwargs):
        #pylint: disable=too-many-locals
        context = super(VisitorsView, self).get_context_data(**kwargs)
        min_date = NewVisitors.objects.all().aggregate(Min('date'))
        max_date = NewVisitors.objects.all().aggregate(Max('date'))
        min_date = min_date.get('date__min', 0)
        max_date = max_date.get('date__max', 0)
        date_tabl = [{"x": datetime.strftime(new.date, "%Y/%m/%d"),
                      "y": new.visitors_number / 5}
                     for new in NewVisitors.objects.all()]
        current_date = min_date
        delta = timedelta(days=1)
        while current_date <= max_date:
            j = len(date_tabl)
            tbl = []
            for i in range(j):
                if date_tabl[i]["x"] == datetime.strftime(
                    current_date, "%Y/%m/%d"):
                    tbl += [i]
            if len(tbl) == 0:
                date_tabl += [{
                    "x": datetime.strftime(current_date, "%Y/%m/%d"), "y": 0}]
            current_date += delta

        date_tabl.sort()

        ########################################################
        # Conversion visitors to trial
        date_joined_username = []
        for user in User.objects.all():
            if (datetime.strftime(user.date_joined, "%Y/%m/%d")
                > datetime.strftime(min_date, "%Y/%m/%d") and
                datetime.strftime(user.date_joined, "%Y/%m/%d")
                < datetime.strftime(max_date, "%Y/%m/%d")):
                date_joined_username += [{
                        "date": user.date_joined, "user": str(user.username)}]

        user_per_joined_date = {}
        for datas in date_joined_username:
            key = datas["date"]
            if not key in user_per_joined_date:
                user_per_joined_date[key] = []
            user_per_joined_date[key] += [datas["user"]]

        trial = []
        for joined_at in user_per_joined_date.keys():
            trial += [{
                "x": joined_at, "y": len(user_per_joined_date[joined_at])}]

        min_date_trial = User.objects.all().aggregate(Min('date_joined'))
        max_date_trial = User.objects.all().aggregate(Max('date_joined'))
        min_date_trial = min_date_trial.get('date_joined__min', 0)
        max_date_trial = max_date_trial.get('date_joined__max', 0)

        for item in trial:
            item["x"] = datetime.strftime(item["x"], "%Y/%m/%d")
        curr_date = min_date
        delta = timedelta(days=1)
        while curr_date <= max_date:
            j = len(trial)
            count = 0
            for i in range(j):
                if trial[i]["x"] == datetime.strftime(curr_date, "%Y/%m/%d"):
                    count += 1
            if count == 0:
                trial += [{
                    "x": datetime.strftime(curr_date, "%Y/%m/%d"), "y": 0}]
            curr_date += delta
        trial.sort()

        context = {'data' : [{"key": "Signup number",
                              "color": "#d62728",
                              "values": trial},
                             {"key": "New visitor number",
                              "values": date_tabl}]}
        return context
