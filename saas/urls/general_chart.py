from django.conf.urls import patterns, url

from saas.settings import ACCT_REGEX

urlpatterns = patterns(
                       'saas.views.general_chart',
                       url(r'^','organization_overall'),
                    )