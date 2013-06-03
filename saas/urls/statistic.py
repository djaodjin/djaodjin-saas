from django.conf.urls import patterns, url

from saas.settings import ACCT_REGEX

urlpatterns = patterns(
                       'saas.views.statistic',
                       url(r'^','statistic'),
                       )
