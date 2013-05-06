import locale

from django import template

register = template.Library()

# XXX locale.setlocale(locale.LC_ALL, '')

@register.filter()
def usd(value):
    if not value:
        return '$0.00'
    return '$%.2f' % (value / 100)
    # XXX return locale.currency(value, grouping=True)
