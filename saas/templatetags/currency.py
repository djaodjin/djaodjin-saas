import locale

from django import template

from saas.models import Plan


register = template.Library()


@register.filter()
def usd(value):
    if not value:
        return '$0.00'
    return '$%.2f' % (float(value) / 100)
    # XXX return locale.currency(value, grouping=True)

@register.filter()
def humanize_period(period):
    if period == Plan.INTERVAL_CHOICES[1][0]:
        return "per hour"
    elif period == Plan.INTERVAL_CHOICES[2][0]:
        return "per day"
    elif period == Plan.INTERVAL_CHOICES[3][0]:
        return "per week"
    elif period == Plan.INTERVAL_CHOICES[4][0]:
        return "per month"
    elif period == Plan.INTERVAL_CHOICES[5][0]:
        return "per quarter"
    elif period == Plan.INTERVAL_CHOICES[6][0]:
        return "per year"
    return "per ?"
