# Copyright (c) 2025, DjaoDjin inc.
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

#pylint: disable=too-many-lines

# Implementation Note:
#   The models and managers are declared in the same file to avoid messy
#   import loops.

"""

Subscribers and providers are both instances of ``Organization``. This is done
such that one can be a subscriber to a ``Plan`` for a service hosted on
the broker website as well as itself a provider to other subscribers.
(ex: An organization can provide a CRM tool to subscribers while paying
another app, also hosted on the broker platform, to display usage analytics
of its own product). It is possible to implement
a :doc:`symmetric double-entry bookkeeping ledger<ledger>` by having a single
model ``Organization``.

Typically if you are self-hosting a pure Software-as-a-Service, as opposed to
building a marketplace, you will define a single provider which incidently
is also the the broker (See :doc:`examples<getting-started>`).

A billing profile (credit card and deposit bank account) is represented by
an ``Organization``.
An ``Organization`` subscriber subscribes to services provided by another
``Organization`` provider through a ``Subscription`` to a ``Plan``.
An ``Organization`` represents a billing profile. The ``processor_card_key``
and ``processor_deposit_key`` fields are respectively used when an organization
acts as a subscriber or provider in the subscription relationship.

There are no mechanism provided to authenticate as an ``Organization``.
Instead ``User`` authenticate with the application (through a login page
or an API token). They are then able to access URLs related
to an ``Organization`` based on their relation with that ``Organization``
as implemented by a ``RoleDescription``.
For historical reasons, two roles are often implemented: managers
and contributors (for details see :doc:`Security <security>`).
"""
from __future__ import unicode_literals

import datetime, logging, re

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import (DatabaseError, IntegrityError, connections, models,
    transaction)
from django.db.models import F, Max, Q, Sum
from django.db.models.query import QuerySet
from django.db.models.signals import post_save
from django.db.utils import DEFAULT_DB_ALIAS
from django.dispatch import receiver
from django.template.defaultfilters import slugify
from django.utils.safestring import mark_safe
from django_countries.fields import CountryField
from rest_framework.exceptions import ValidationError

from . import humanize, settings, signals
from .backends import (get_processor_backend, CardError, ProcessorError,
    ProcessorSetupError)
from .compat import (import_string, gettext_lazy as _,
    python_2_unicode_compatible, six, urlquote)
from .utils import (SlugTitleMixin, datetime_or_now, full_name_natural_split,
    generate_random_slug, handle_uniq_error)
from .utils import (get_organization_model, get_role_model,
    is_mail_provider_domain)


LOGGER = logging.getLogger(__name__)


class InsufficientFunds(Exception):

    pass


class Price(object):

    def __init__(self, amount, unit):
        assert isinstance(amount, six.integer_types)
        self.amount = amount
        self.unit = unit
        if not self.unit:
            self.unit = settings.DEFAULT_UNIT # XXX


def get_extra_field_class():
    extra_class = settings.EXTRA_FIELD
    if extra_class is None:
        extra_class = models.TextField
    elif isinstance(extra_class, six.string_types):
        extra_class = import_string(extra_class)
    return extra_class


class OrganizationManager(models.Manager):

    def create_organization_from_user(self, user):
        with transaction.atomic():
            organization = self.create(
                slug=user.username,
                full_name=user.get_full_name(),
                email=user.email)
            organization.add_manager(user)
        return organization

    def attached(self, user):
        """
        Returns the personal profile (``Organization``) associated to the user
        or None if none can be reliably found.
        """
        if isinstance(user, get_user_model()):
            return self.filter(role__user=user, slug=user.username).first()
        if isinstance(user, six.string_types):
            return self.filter(role__user__username=user, slug=user).first()
        return None

    def accessible_by(self, user, role_descr=None, includes_personal=True):
        """
        Returns a QuerySet of Organziation which *user* has an associated
        role with.

        When *user* is a string instead of a ``User`` instance, it will
        be interpreted as a username.
        """
        kwargs = {}
        user_model = get_user_model()
        if isinstance(user, user_model):
            kwargs.update({'user': user})
        else:
            kwargs.update({'user__username': str(user)})
        if role_descr:
            if isinstance(role_descr, RoleDescription):
                kwargs.update({'role_description': role_descr})
            elif isinstance(role_descr, six.string_types):
                kwargs.update({'role_description__slug': str(role_descr)})
            else:
                kwargs.update({'role_description__slug__in': [
                    str(descr) for descr in role_descr]})
        roles = get_role_model().objects.db_manager(using=self._db).valid_for(
            includes_personal=includes_personal, **kwargs)
        return self.filter(
            is_active=True, pk__in=roles.values('organization')).distinct()

    def find_candidates_by_domain(self, domain):
        return self.filter(is_active=True, email__endswith=domain)

    def find_candidates(self, full_name, user=None):
        """
        Returns a set of organizations based on a fuzzy match of *full_name*
        and the email address of *user*.

        This method is primarly intended in registration pages to help
        a user decides to create a new organization or request access
        to an already existing organization.
        """
        queryset = self.filter(
            Q(slug=slugify(full_name)) | Q(full_name__iexact=full_name))
        if queryset.exists():
            return queryset
        if user:
            email_suffix = user.email.split('@')[-1]
            candidates_from_email = get_role_model().objects.valid_for(
                user__email__iendswith=email_suffix,
                role_description__slug=settings.MANAGER).values(
                    'organization')
            return self.filter(pk__in=candidates_from_email)
        return self.none()

    def providers(self, subscriptions):
        """
        Set of ``Organization`` which provides the plans referenced
        by *subscriptions*.
        """
        if subscriptions:
            # Would be almost straightforward in a single raw SQL query
            # but expressing it for the Django compiler is not easy.
            selectors = set([])
            for subscription in subscriptions:
                selectors |= set([subscription.plan.organization.id])
            return self.filter(pk__in=selectors)
        return self.none()

    def receivable_providers(self, invoiced_items):
        """
        Returns a list of unique providers referenced by *invoiced_items*.
        """
        results = set([])
        for invoiced_item in invoiced_items:
            assert invoiced_item.orig_account in (Transaction.RECEIVABLE,
                Transaction.SETTLED)
            results |= set([invoiced_item.orig_organization])
            event = invoiced_item.get_event() # Subscription,
                                              # or Coupon (i.e. Group buy)
            if event:
                results |= set([event.provider])
        return list(results)


    def providers_to(self, organization):
        """
        Set of ``Organization`` which provides active services
        to a subscribed *organization*.
        """
        return self.providers(Subscription.objects.valid_for(
            organization=organization))


@python_2_unicode_compatible
class AbstractOrganization(models.Model):
    """
    The Organization table stores information about who gets
    charged (subscriber) and who gets paid (provider) for using a service.
    A special ``Organization``, named processor, is used to represent
    the backend charge/deposit processor.

    Users can have one of multiple relationships (roles) with an Organization.
    They can either be managers (all permissions) or a custom role defined
    through a ``RoleDescription``.
    """
    #pylint:disable=too-many-instance-attributes

    ACCOUNT_UNKNOWN = 0
    ACCOUNT_USER = 1
    ACCOUNT_PERSONAL = 2
    ACCOUNT_ORGANIZATION = 3
    ACCOUNT_PROVIDER = 4

    ACCOUNT_TYPE = (
        (ACCOUNT_UNKNOWN, "unknown"),
        (ACCOUNT_USER, "user"),
        (ACCOUNT_PERSONAL, "personal"),
        (ACCOUNT_ORGANIZATION, "organization"),
        (ACCOUNT_PROVIDER, "provider"),
    )

    objects = OrganizationManager()
    slug = models.SlugField(unique=True,
        help_text=_("Unique identifier shown in the URL bar"))

    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time of creation (in ISO format)"))
    is_active = models.BooleanField(default=True)
    full_name = models.CharField(_("Profile name"), max_length=100, blank=True)
    # contact by e-mail
    email = models.EmailField()
    # contact by phone
    phone = models.CharField(max_length=50)
    # contact by physical mail
    street_address = models.CharField(_("Street address"), max_length=150)
    locality = models.CharField(_("City/Town"), max_length=50)
    region = models.CharField(_("State/Province/County"), max_length=50)
    postal_code = models.CharField(_("Zip/Postal code"), max_length=50)
    country = CountryField(_("Country"))

    is_bulk_buyer = models.BooleanField(default=False,
        help_text=mark_safe(_("Enable GroupBuy ("\
        "<a href=\"https://www.djaodjin.com/docs/faq/#group-billing\""\
        " target=\"_blank\">what is it?</a>)")))
    is_provider = models.BooleanField(default=False,
        help_text=_("The profile can fulfill the provider side"\
        " of a subscription."))
    default_timezone = models.CharField(
        max_length=100, default=settings.TIME_ZONE,
        help_text=_("Timezone to use when reporting metrics"))
    # 2083 number is used because it is a safe option to choose based
    # on some older browsers behavior
    # https://stackoverflow.com/q/417142/1491475
    picture = models.URLField(_("Profile picture"), max_length=2083, null=True,
        blank=True, help_text=_("URL location of the profile picture"))

    # Payment Processing
    # ------------------
    # Implementation Note: Software developpers using the Django admin
    # panel to bootstrap their database will have an issue if the processor
    # is not optional. This is because the processor ``Organization`` does
    # not itself reference a processor.
    # 2nd note: We could support multiple payment processors at the same
    # time by having a relation to a separate table. For simplicity we only
    # allow one processor per organization at a time.
    subscribes_to = models.ManyToManyField('saas.Plan',
        related_name='subscribers', through='saas.Subscription')
    billing_start = models.DateField(null=True,
        help_text=_("Date at which the next automatic charge"\
        " will be generated (in ISO format)"))

    funds_balance = models.PositiveIntegerField(default=0,
        help_text=_("Funds escrowed in currency unit"))
    nb_renewal_attempts = models.PositiveIntegerField(default=0,
        help_text=_("Number of successive failed charges"))
    processor = models.ForeignKey(
        settings.ORGANIZATION_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='processes',)
    processor_card_key = models.SlugField(max_length=255, null=True, blank=True)
    processor_deposit_key = models.SlugField(max_length=255, null=True,
        blank=True,
        help_text=_("Used to deposit funds to the organization bank account"))
    processor_priv_key = models.SlugField(max_length=255, null=True, blank=True)
    processor_pub_key = models.SlugField(max_length=255, null=True, blank=True)
    processor_refresh_token = models.SlugField(max_length=255, null=True,
        blank=True)

    extra = get_extra_field_class()(null=True, blank=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    class Meta:
        abstract = True

    def __str__(self):
        return str(self.slug)

    @property
    def is_broker(self):
        """
        Returns ``True`` if the organization is the hosting platform
        for the service.
        """
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_is_broker'):
            # We do a string compare here because both ``Organization`` might
            # come from a different db.
            self._is_broker = is_broker(self)
        return self._is_broker

    def get_active_subscriptions(self, at_time=None):
        """
        Returns the set of active subscriptions for this organization
        at time *at_time* or now if *at_time* is not specified.
        """
        at_time = datetime_or_now(at_time)
        return Subscription.objects.valid_for(
            organization=self, ends_at__gte=at_time)

    def get_ends_at_by_plan(self, at_time=None):
        """
        Returns the set of churned subscriptions for this organization
        at time *at_time* or now if *at_time* is not specified.
        """
        at_time = datetime_or_now(at_time)
        return Subscription.objects.valid_for(
            organization=self).values('plan__slug').annotate(
                Max('ends_at')).distinct()

    def get_changes(self, update_fields):
        changes = {}
        for field_name in ('slug', 'full_name', 'email', 'phone',
            'street_address', 'locality', 'region', 'postal_code', 'country',
            'is_bulk_buyer', 'is_provider', 'default_timezone'):
            pre_value = getattr(self, field_name, None)
            post_value = update_fields.get(field_name, None)
            if post_value is not None and pre_value != post_value:
                # The changes will be used to trigger a signal and notification
                # to the primary contact that can then check for potential
                # nefarious activity. It is also possible the notification
                # is used to keep a separate service (CRM, etc.) in sync.
                if field_name == 'is_bulk_buyer':
                    changes['GroupBuy'] = {
                        'pre': _('enabled') if pre_value else _('disabled'),
                        'post': _('enabled') if post_value else _('disabled')}
                else:
                    changes[field_name] = {
                        'pre': pre_value, 'post': post_value}
        return changes

    def validate_processor(self):
        #pylint:disable=no-member,access-member-before-definition
        #pylint:disable=attribute-defined-outside-init
        organization_model = get_organization_model()
        if not self.processor_id:
            try:
                self.processor = organization_model.objects.get(
                    pk=settings.PROCESSOR_ID)
            except organization_model.DoesNotExist:
                # If the processor organization does not exist yet, it means
                # we are inserting the first record to bootstrap the db.
                self.processor_id = settings.PROCESSOR_ID
                self.pk = settings.PROCESSOR_ID #pylint:disable=invalid-name
        return self.processor


    def save(self, *args, force_insert=False, force_update=False, using=None,
             update_fields=None):
        self.validate_processor()
        if self.slug:
            with transaction.atomic():
                # Starting with Django 5, we need a `pk` for the organization
                # before we can call `attached_user`.
                super(AbstractOrganization, self).save(*args,
                    force_insert=force_insert, force_update=force_update,
                    using=using, update_fields=update_fields)
                user = self.attached_user()
                if user:
                    # When dealing with a personal profile, keep the login
                    # user in sync with the billing profile.
                    save_user = False
                    first_name, _, last_name \
                        = full_name_natural_split(self.full_name)
                    if user.first_name != first_name:
                        user.first_name = first_name
                        save_user = True
                    if user.last_name != last_name:
                        user.last_name = last_name
                        save_user = True
                    if user.email != self.email and (user.email or self.email):
                        # When registering with a phone number only,
                        # self.email might be ''. We don't want to override
                        # `user.email is None`.
                        user.email = self.email
                        save_user = True
                    if save_user:
                        user.save()
                return
        max_length = self._meta.get_field('slug').max_length
        if self.full_name:
            slug_base = slugify(self.full_name)
        else:
            slug_base = _clean_field(
                self.__class__, 'slug', self.email.split('@', maxsplit=1)[0])
        if len(slug_base) > (max_length - 7 - 1):
            slug_base = slug_base[:(max_length - 7 - 1)]
        if slug_base:
            self.slug = slug_base
            slug_base += '-'
        else:
            self.slug = generate_random_slug(
                length=min(max_length, len(slug_base) + 7))
        for idx in range(1, 10): #pylint:disable=unused-variable
            try:
                try:
                    with transaction.atomic():
                        super(AbstractOrganization, self).save(
                            *args,
                            force_insert=force_insert,
                            force_update=force_update,
                            using=using, update_fields=update_fields)
                        user = self.attached_user()
                        if user:
                            user.first_name, _, user.last_name \
                                = full_name_natural_split(self.full_name)
                            if self.email:
                                user.email = self.email
                            user.save()
                        return
                except IntegrityError as err:
                    handle_uniq_error(err)
            except ValidationError as err:
                if not (isinstance(err.detail, dict) and 'slug' in err.detail):
                    raise err
                self.slug = generate_random_slug(
                    length=min(max_length, len(slug_base) + 7),
                    prefix=slug_base)
        raise ValidationError({'detail':
            "Unable to create a unique URL slug from '%s'" % self.full_name})

    @property
    def printable_name(self):
        """
        Insures we can actually print a name visible on paper.
        """
        if self.full_name:
            return self.full_name
        return self.slug

    @property
    def has_profile_completed(self):
        return self.full_name and \
            self.email and \
            self.phone and \
            self.street_address and \
            self.locality and \
            self.region and \
            self.postal_code and \
            self.country

    @property
    def has_plan(self):
        return Plan.objects.filter(
            organization=self).count() > 0

    @property
    def has_bank_account(self):
        if self.is_broker:
            processor_backend = self.processor_backend
            return processor_backend.pub_key and processor_backend.priv_key
        return self.processor_deposit_key

    @property
    def natural_interval(self):
        plan_periods = self.plans.values('period_type').distinct()
        interval = Plan.MONTHLY
        if plan_periods.exists():
            interval = Plan.YEARLY
            for period in plan_periods:
                interval = min(interval, period['period_type'])
        return interval

    @property
    def natural_subscription_period(self):
        plan_periods = self.subscribes_to.values('period_type').distinct()
        period_type = Plan.MONTHLY
        if plan_periods.exists():
            period_type = Plan.YEARLY
            for period in plan_periods:
                period_type = min(period_type, period['period_type'])
        return Plan.get_natural_period(1, period_type)

    @property
    def processor_backend(self):
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_processor_backend'):
            self._processor_backend = get_processor_backend(self)
        return self._processor_backend

    def get_role_description(self, role_slug):
        return RoleDescription.objects.db_manager(using=self._state.db).get(
            Q(organization=self) | Q(organization__isnull=True),
            slug=RoleDescription.normalize_slug(role_slug))

    def get_role_descriptions(self):
        """
        Queryset of roles a ``User`` can take on this ``Organization``.
        """
        return RoleDescription.objects.filter(
            Q(organization=self) | Q(organization__isnull=True)).order_by('pk')

    def get_roles(self, role_descr=None):
        kwargs = {}
        if role_descr:
            if not isinstance(role_descr, RoleDescription):
                role_descr = self.get_role_description(role_descr)
            kwargs = {'role_description': role_descr}
        # OK to use ``filter`` here since we want to see all pending grants
        # and requests.
        return get_role_model().objects.db_manager(using=self._state.db).filter(
            organization=self, **kwargs)

    def add_role_grant(self, user, role_descr,
                       grant_key=None, force_skip_optin=False,
                       extra=None, at_time=None):
        """
        Grants a ``role_descr`` (ex: manager) to ``user`` on the profile.

        If ``user`` already had a role on the organization, it is replaced
        to only keep one role per user per organization.

        When ``grant_key`` is specified, it will be set on the role, regardless
        of the ``role_descr.skip_optin_on_grant`` value.
        """
        #pylint:disable=too-many-arguments
        # Implementation Note:
        # Django get_or_create will call router.db_for_write without
        # an instance so the using database will be lost. The following
        # code saves the relation in the correct database associated
        # with the organization.
        if not isinstance(role_descr, RoleDescription):
            role_descr = self.get_role_description(role_descr)
        # OK to use ``filter`` in both subsequent queries as we are dealing
        # with the whole QuerySet related to a user.
        queryset = get_role_model().objects.db_manager(
            using=self._state.db).filter(organization=self, user=user)
        if queryset.exists():
            # We have a role for the user on this organization. Let's update it.
            m2m = queryset.get()
            force_insert = False
        else:
            m2m = get_role_model()(organization=self, user=user)
            force_insert = True

        m2m.request_key = None
        m2m.role_description = role_descr
        if extra:
            m2m.extra = extra
        if at_time:
            m2m.created_at = at_time

        if force_skip_optin:
            m2m.grant_key = None
        elif grant_key:
            m2m.grant_key = grant_key
        elif role_descr.skip_optin_on_grant or (self.slug == user.username and
            role_descr == self.get_role_description(settings.MANAGER)):
            # We are granting manager role to a personal profile, so let's not
            # get into a weird use case where we have to accept a request
            # to our own profile.
            m2m.grant_key = None
        elif force_insert and not m2m.grant_key:
            m2m.grant_key = generate_random_slug()

        m2m.save(using=self._state.db, force_insert=force_insert)
        LOGGER.info("Grant role '%s' to user '%s' on organization '%s'",
            m2m.role_description, m2m.user, m2m.organization,
            extra={'event': 'grant-role', 'user': m2m.user.username,
                'organization': m2m.organization.slug,
                'role': str(m2m.role_description)})
        return m2m, force_insert

    def add_role_request(self, user, at_time=None, role_descr=None):
        force_insert = False
        at_time = datetime_or_now(at_time)
        if role_descr and not isinstance(role_descr, RoleDescription):
            role_descr = self.get_role_description(role_descr)
        # OK to use ``filter`` in both subsequent queries as we are dealing
        # with the whole QuerySet related to a user.
        queryset = get_role_model().objects.db_manager(
            using=self._state.db).filter(organization=self, user=user)
        if queryset.exists():
            # We have a role for the user on this organization, or a grant
            # or request was previously sent.
            m2m = queryset.get()
            if m2m.request_key:
                # We already have a request, so just update the role_descr.
                m2m.role_description = role_descr
                m2m.created_at = at_time
                m2m.save()
            elif m2m.grant_key and (
                    not role_descr or role_descr == m2m.role_description):
                # We have a pending grant to the role requested,
                # or an unspecified role requested.
                m2m.grant_key = None
                m2m.created_at = at_time
                m2m.save()
            elif role_descr and role_descr != m2m.role_description:
                # This is an active role (i.e. not a pending grant nor request)
                # XXX This will de-active current role until request
                #     is accepted. should we do better?
                m2m.request_key = generate_random_slug()
                m2m.role_description = role_descr
                m2m.created_at = at_time
                m2m.save()
        else:
            m2m = get_role_model()(created_at=at_time, organization=self,
                user=user, role_description=role_descr,
                request_key=generate_random_slug())
            m2m.save(using=self._state.db, force_insert=True)
            force_insert = True
        LOGGER.info("Request %s for user '%s' on organization '%s'",
            ("unspecified role" if not m2m.role_description
             else "role '%s'" % m2m.role_description),
            m2m.user, m2m.organization,
            extra={'event': 'grant-role', 'user': m2m.user.username,
                'organization': m2m.organization.slug,
                'role': str(m2m.role_description)})
        return m2m, force_insert

    def add_manager(self, user, extra=None, at_time=None):
        """
        Convienence to add a manager role during onboarding scenarios
        """
        return self.add_role_grant(user, settings.MANAGER,
            force_skip_optin=True, extra=extra, at_time=at_time)

    def remove_role(self, user, role_name):
        """
        Remove user as a *role_name* (ex: manager) to organization.
        """
        relation = self.get_roles(role_name).get(user=user)
        relation.delete()

    def with_role(self, role_name):
        """
        Returns all users with a *role_name* to organization.
        """
        return get_user_model().objects.db_manager(using=self._state.db).filter(
            pk__in=self.get_roles(role_name).values('user')).distinct()

    def attached_user(self):
        """
        Returns the only ``User`` attached to the ``Organization`` or
        ``None`` if more than one ``User`` has access rights
        to the organization.

        This method is used to implement personal registration, where
        from a customer perspective user auth and billing profile are
        one and the same.
        """
        return get_user_model().objects.db_manager(
            using=self._state.db).filter(
            role__organization=self, username=self.slug).first()

    def last_payment(self):
        """
        Returns the Transaction that corresponds to the last payment
        by the organization.
        """
        return Transaction.objects.filter(
            orig_organization=self,
            orig_account=Transaction.LIABILITY,
            dest_organization=self.processor,
            dest_account=Transaction.FUNDS).order_by('-created_at').first()

    def last_unpaid_orders(self, subscription=None, at_time=None):
        """
        Returns the set of payable transactions that happened
        after the last payment.
        """
        kwargs = {}
        if subscription:
            kwargs.update({'event_id': get_sub_event_id(subscription)})
        if at_time:
            kwargs.update({'created_at__lt': at_time})
        last_payment = self.last_payment()
        if last_payment:
            kwargs.update({'created_at__gt': last_payment.created_at})
        queryset = Transaction.objects.filter(
            dest_organization=self,
            dest_account=Transaction.PAYABLE,
            orig_account=Transaction.RECEIVABLE,
            **kwargs).order_by('-created_at')
        return queryset

    def receivables(self):
        """
        Returns all ``Transaction`` for payments that are due to a *provider*.
        """
        return Transaction.objects.filter(
            orig_organization=self,
            orig_account=Transaction.RECEIVABLE).exclude(
                dest_account=Transaction.CANCELED)

    def update_bank(self, bank_token):
        if bank_token is None:
            self.processor_deposit_key = None
            self.processor_priv_key = None
            self.processor_pub_key = None
            self.processor_refresh_token = None
            self.save()
        else:
            self.processor_backend.update_bank(self, bank_token)
            LOGGER.info("Processor deposit key for %s updated to %s",
                self, self.processor_deposit_key,
                extra={'event': 'update-deposit', 'organization': self.slug,
                    'processor_deposit_key': self.processor_deposit_key})
        signals.bank_updated.send(self)

    def delete_card(self):
        broker = get_broker()
        broker.processor_backend.delete_card(self, broker=broker)
        self.processor_card_key = None
        self.save()
        LOGGER.info("Processor debit key for %s was deleted.",
            self, extra={'event': 'delete-debit', 'organization': self.slug})

    def update_card(self, card_token, user, provider=None):
        broker = get_broker()
        new_card = broker.processor_backend.create_or_update_card(
            self, card_token, user=user, provider=provider, broker=broker)
        self.nb_renewal_attempts = 0  # reset off-session failures counter
        # The following ``save`` will be rolled back in ``checkout``
        # if there is any ProcessorError.
        self.save()
        LOGGER.info("Processor debit key for %s updated to %s",
            self, self.processor_card_key,
            extra={'event': 'update-debit', 'organization': self.slug,
                'processor_card_key': self.processor_card_key})
        return new_card

    def execute_order(self, invoicables, user):
        """
        Records and executes the order described by *invoicables*

        This method takes *invoicables* (a dictionnary structured
        by the checkout API JSON format) and a *user* cart.
        It records
        `Transaction` for the order, and creates or extends
        `Subscription` and `SubscriptionUse` for profiles already
        in the system, while generating claim codes for other cart items,
        after a generated 100% discount coupon as been attached to them.
        These claim codes can then be shared with profiles to register
        and access "free" (i.e. paid by this profile) subscriptions.

        This method then returns the list of `Transaction` recorded
        for the order, and a list of (claim_code, `Organization`) pairs
        for profiles to invite to the system.

        **Examples**

        .. code-block:: python

        invoiceables = [{
           'subscription': Subscription(
               organization='xia170', plan='club170-basic',
               ends_at='2024-12-09 19:41:20.555505+00:00'),
           'lines': [
             Transaction(descr='Subscription to club170-basic'\
                 ' until 2025/12/09 (12 months) - a 10% discount'),
             Transaction(descr='Buy 1 club170-basic Requests')
             Transaction(descr='Buy 1 club170-basic Storage')
           ],
           'name': 'cart-club170-basic',
           'descr': 'Club170 Basic from Club170'
         }]

        """
        #pylint:disable=too-many-locals,too-many-statements
        order_executed_items = [] # list of `Transaction` recording the order
        nb_invites_by_plans = {}  # list nb of coupon use indexed by `Plan.id`
        # `invites_by_profiles` collects the 'organization', 'cart_items' and
        # 'claim_code' for profiles which are not present in the database.
        invites_by_profiles = {}
        for invoicable in invoicables:
            subscription = invoicable['subscription']
            key = subscription.organization.email
            # If the invoicable we are checking out is somehow related to
            # a user shopping cart, we mark that cart item as recorded
            # unless the organization does not exist in the database,
            # in which case we will create a claim_code for it.
            cart_items = CartItem.objects.get_cart(user, plan=subscription.plan)
            if subscription.organization.id:
                sync_on_cart_items = cart_items.filter(
                    Q(sync_on=key) | Q(sync_on="") | Q(sync_on__isnull=True))
                # We have an organization in the database, but it might
                # be a new subscription.
                for invoiced_item in invoicable['lines']:
                    if (invoiced_item.is_sub_event_id and
                        not invoiced_item.is_sub_use_event_id):
                        subscription.extends(
                          subscription.plan.period_number(invoiced_item.descr))
                        break
                # If it exists in the invoicable line items, the subscription
                # is now recorded in the database, hence as a `pk`.
                sub_event_id = get_sub_event_id(subscription)
                for invoiced_item in invoicable['lines']:
                    # We rely on `get_sub_event_id` to create a generic 'sub_0/'
                    # prefix for subscription which have not yet been committed
                    # to the database.
                    invoiced_item.event_id = re.sub(r'^sub_0/',
                        sub_event_id, invoiced_item.event_id)
                    invoiced_item.save()
                    order_executed_items += [invoiced_item]
                    look = re.match(r'^sub_(\d+)/(\d+)/',
                        invoiced_item.event_id)
                    if not look:
                        continue
                    use_charge = UseCharge.objects.get(pk=int(look.group(2)))
                    cart_item = sync_on_cart_items.filter(use=use_charge).get()
                    quantity = cart_item.quantity
                    if not quantity:
                        quantity = 1
                    try:
                        usage = SubscriptionUse.objects.get(
                            subscription=subscription, use=use_charge)
                        usage.rollover_quota += quantity
                    except SubscriptionUse.DoesNotExist:
                        SubscriptionUse.objects.create(
                            subscription=subscription, use=use_charge,
                            expiring_quota=use_charge.quota,
                            rollover_quota=quantity)
                sync_on_cart_items.update(recorded=True)

            else:
                # When the organization does not exist into the database,
                # we will create a random (i.e. hard to guess) claim code
                # that will be emailed to the expected subscriber.
                sync_on_cart_items = list(cart_items.filter(
                    sync_on__iexact=key))
                if not key in invites_by_profiles:
                    invites_by_profiles.update({
                        key: {
                            'organization': subscription.organization,
                            'cart_items': sync_on_cart_items,
                            'claim_code': None
                    }})
                else:
                    invites_by_profiles[key]['cart_items'] += sync_on_cart_items
                if subscription.plan not in nb_invites_by_plans:
                    nb_invites_by_plans.update({subscription.plan: 1})
                else:
                    nb_invites_by_plans[subscription.plan] += 1

        # At this point we have gathered all the ``Organization``
        # which have yet to be registered. For these no ``Subscription``
        # has been created yet. We create a claim_code that will
        # be emailed to the expected subscribers such that it will populate
        # their cart automatically.
        coupons = {} # list of `Coupon` indexed by `Plan.id`
        for plan, nb_attempts in six.iteritems(nb_invites_by_plans):
            coupon = Coupon.objects.create(
                code='cpn_%s' % generate_random_slug(),
                organization=plan.organization,
                discount_type=Coupon.PERCENTAGE, discount_value=10000,
                ends_at=None,
                plan=plan,
                nb_attempts=nb_attempts,
                description=('Auto-generated after payment by %s'
                    % self.printable_name))
            LOGGER.info('Auto-generated Coupon %s for %s',
                coupon.code, plan.organization,
                extra={'event': 'create-coupon',
                'coupon': coupon.code, 'auto': True,
                'provider': plan.organization.slug})
            coupons.update({plan.pk: coupon})

        for key, invite in six.iteritems(invites_by_profiles):
            claim_code = generate_random_slug()
            invite['claim_code'] = claim_code
            for cart_item in invite['cart_items']:
                cart_item.sync_on = ""
                cart_item.user = None
                cart_item.full_name = self.printable_name
                cart_item.claim_code = claim_code
                cart_item.coupon = coupons[cart_item.plan.pk]
                cart_item.save()
            nb_cart_items = len(cart_items)
            LOGGER.info("Generated claim code '%s' for %d cart items",
                claim_code, nb_cart_items, extra={
                    'event': 'create-claim',
                    'claim_code': claim_code,
                    'nb_cart_items': nb_cart_items})

        # We now either have a ``subscription.id`` (subscriber present
        # in the database) or a ``Coupon`` (subscriber absent from
        # the database).
        for invoicable in invoicables:
            subscription = invoicable['subscription']
            if not subscription.organization.id:
                coupon = coupons[subscription.plan.pk]
                # Coupon.code will be the `cpn_` prefixed event_id as it was
                # generated earlier.
                for invoiced_item in invoicable['lines']:
                    invoiced_item.event_id = coupon.code
                    invoiced_item.save()
                    order_executed_items += [invoiced_item]

        if order_executed_items:
            signals.order_executed.send(
                sender=__name__, invoiced_items=order_executed_items, user=user)

        return (order_executed_items,
            [(invite['claim_code'], invite['organization'])
            for invite in six.itervalues(invites_by_profiles)])


    def checkout(self, invoicables, user, token=None, remember_card=True):
        """
        Executes an order, then charge a payment method

        This method takes *invoicables* (a dictionnary structured
        by the checkout API JSON format) and a user cart.

        **Examples**

        .. code-block:: python

        invoiceables = [{
           'subscription': Subscription(
               organization='xia170', plan='club170-basic',
               ends_at='2024-12-09 19:41:20.555505+00:00'),
           'lines': [
             Transaction(descr='Subscription to club170-basic'\
                 ' until 2025/12/09 (12 months) - a 10% discount'),
             Transaction(descr='Buy 1 club170-basic Requests')
             Transaction(descr='Buy 1 club170-basic Storage')
           ],
           'name': 'cart-club170-basic',
           'descr': 'Club170 Basic from Club170'
         }]

        It will then charge the balance for that order to the payment method
        referenced by *token*, or the payment method on file for the profile
        if *token* is `None`.

        The method returns the `Charge` object created.
        """
        charge = None
        with transaction.atomic():
            invoiced_items, invited_organizations = self.execute_order(
                invoicables, user)
            charges = Charge.objects.create_charges_by_processor(
                self, invoiced_items, user=user)
            for charge in charges:
                charge.execute(token, user, remember_card=remember_card)
        if charges:
            # It is possible we are subscribing to a free plan.
            charge = charges[0]

        # We email users which have yet to be registerd after the charge
        # is created, just that we don't inadvertently email new subscribers
        # in case something goes wrong.
        for claim_code, organization in invited_organizations:
            signals.claim_code_generated.send(sender=__name__,
                subscriber=organization, claim_code=claim_code, user=user)

        return charge


    def paylater(self, invoicables, user):
        """
        Executes an order

        This method takes *invoicables* (a dictionnary structured
        by the checkout API JSON format) and a user cart.

        **Examples**

        .. code-block:: python

        invoiceables = [{
           'subscription': Subscription(
               organization='xia170', plan='club170-basic',
               ends_at='2024-12-09 19:41:20.555505+00:00'),
           'lines': [
             Transaction(descr='Subscription to club170-basic'\
                 ' until 2025/12/09 (12 months) - a 10% discount'),
             Transaction(descr='Buy 1 club170-basic Requests')
             Transaction(descr='Buy 1 club170-basic Storage')
           ],
           'name': 'cart-club170-basic',
           'descr': 'Club170 Basic from Club170'
         }]

        The method returns an invoice (`Charge`) for the balance for that order.
        """
        charge = None
        with transaction.atomic():
            invoiced_items, invited_organizations = self.execute_order(
                invoicables, user)
            charges = Charge.objects.create_charges_by_processor(
                self, invoiced_items, user=user)
            if charges:
                # It is possible we are subscribing to a free plan.
                # XXX works only when we have a single processor?
                charge = charges[0]

        # We email users which have yet to be registerd after the charge
        # is created, just that we don't inadvertently email new subscribers
        # in case something goes wrong.
        for claim_code, organization in invited_organizations:
            signals.claim_code_generated.send(sender=__name__,
                subscriber=organization, claim_code=claim_code, user=user)

        return charge


    def update_address_if_empty(self, country=None, region=None, locality=None,
        street_address=None, postal_code=None):
        #pylint:disable=too-many-arguments
        if not (self.country or self.region) and country and region:
            self.country = country
            self.region = region
        if not self.locality and locality:
            self.locality = locality
        if not self.street_address and street_address:
            self.street_address = street_address
        if not self.postal_code and postal_code:
            self.postal_code = postal_code

    def get_deposit_context(self):
        return self.processor_backend.get_deposit_context()

    def retrieve_bank(self, includes_balance=True):
        """
        Returns associated bank account as a dictionnary.
        """
        context = self.processor_backend.retrieve_bank(
            self, get_broker(), includes_balance=includes_balance)
        available_amount = context.get('balance_amount', "N/A")
        if includes_balance and isinstance(available_amount, six.integer_types):
            # The processor could return "N/A" if the organization is not
            # connected to a processor account.
            balance = Transaction.objects.get_balance(
                organization=self, account=Transaction.FUNDS)
            available_amount = min(balance['amount'], available_amount)
            transfer_fee = self.processor_backend.prorate_transfer(
                available_amount, self)
            if available_amount > transfer_fee:
                available_amount -= transfer_fee
            else:
                available_amount = 0
        context.update({'balance_amount': available_amount})
        return context

    def retrieve_card(self):
        """
        Returns associated credit card.
        """
        broker = get_broker()
        return broker.processor_backend.retrieve_card(self, broker=broker)

    def get_transfers(self, reconcile=True):
        """
        Returns a ``QuerySet`` of ``Transaction`` after it has been
        reconcile with the withdrawals that happened in the processor
        backend.
        """
        if reconcile:
            after = datetime_or_now() - relativedelta(months=1)
            # We want to avoid looping through too many calls to the Stripe API.
            queryset = Transaction.objects.filter(
                orig_organization=self,
                orig_account=Transaction.FUNDS,
                dest_account__startswith=Transaction.WITHDRAW)
            most_recent = queryset.aggregate(
                Max('created_at'))['created_at__max']
            if most_recent:
                after = max(most_recent, after)
            self.processor_backend.reconcile_transfers(self, after,
                limit_to_one_request=True)
        return Transaction.objects.by_organization(self)

    def withdraw_funds(self, amount, user):
        if amount == 0:
            # Nothing to do.
            return
        descr = "withdraw from %s" % self.printable_name
        if user:
            descr += ' (%s)' % user.username
        self.processor_backend.create_transfer(
            self, amount, currency=settings.DEFAULT_UNIT, descr=descr)
        # We will wait on a call to ``reconcile_transfers`` to create
        # those ``Trnansaction`` in the database.

    def create_withdraw_transactions(self, event_id, amount, unit, descr,
                                     created_at=None, dry_run=False):
        """
        Withdraw funds from the site into the provider's bank account.

        We record one straightforward ``Transaction`` for the withdrawal
        and an additional one in case there is a processor transfer fee::

            yyyy/mm/dd po_***** withdrawal to provider bank account
                processor:Withdraw                       amount
                provider:Funds

            ; With StripeConnect there are no processor fees anymore
            ; for Payouts.
            yyyy/mm/dd processor fee paid by provider
                processor:Funds                          processor_fee
                provider:Funds

        Example::

            2014/09/10 withdraw from cowork
                stripe:Withdraw                          $174.52
                cowork:Funds
       """
        #pylint:disable=too-many-arguments
        # We use ``get_or_create`` here because the method is also called
        # when transfers are reconciled with the payment processor.
        dry_run_prefix = "(dryrun) " if dry_run else ""
        self.validate_processor()
        with transaction.atomic():
            created = False
            if amount > 0:
                #pylint:disable=protected-access
                #pylint:disable=attribute-defined-outside-init
                Transaction.objects._for_write = True
                # The get() needs to be targeted at the write database in order
                # to avoid potential transaction consistency problems.
                try:
                    _ = Transaction.objects.get(
                        event_id=event_id,
                        descr=descr,
                        created_at=created_at,
                        dest_unit=unit,
                        dest_amount=amount,
                        dest_account=Transaction.WITHDRAW,
                        dest_organization=self.processor,
                        orig_unit=unit,
                        orig_amount=amount,
                        orig_account=Transaction.FUNDS,
                        orig_organization=self)
                    LOGGER.debug("%s  %s payout %d %s (funds=%d)",
                        dry_run_prefix, created_at, amount, unit,
                        self.funds_balance)
                except Transaction.DoesNotExist:
                    if not dry_run:
                        _ = Transaction.objects.create(
                            event_id=event_id,
                            descr=descr,
                            created_at=created_at,
                            dest_unit=unit,
                            dest_amount=amount,
                            dest_account=Transaction.WITHDRAW,
                            dest_organization=self.processor,
                            orig_unit=unit,
                            orig_amount=amount,
                            orig_account=Transaction.FUNDS,
                            orig_organization=self)
                    LOGGER.debug("%s+ %s payout %d %s (funds=%d)",
                        dry_run_prefix, created_at, amount, unit,
                        self.funds_balance)
                    created = True
            elif amount < 0:
                # When there is not enough funds in the Stripe account,
                # Stripe will draw back from the bank account to cover
                # a refund, etc.
                #pylint:disable=protected-access
                #pylint:disable=attribute-defined-outside-init
                Transaction.objects._for_write = True
                # The get() needs to be targeted at the write database in order
                # to avoid potential transaction consistency problems.
                try:
                    _ = Transaction.objects.get(
                        event_id=event_id,
                        descr=descr,
                        created_at=created_at,
                        dest_unit=unit,
                        dest_amount=- amount,
                        dest_account=Transaction.FUNDS,
                        dest_organization=self,
                        orig_unit=unit,
                        orig_amount=- amount,
                        orig_account=Transaction.WITHDRAW,
                        orig_organization=self.processor)
                    LOGGER.debug("%s  %s payout %d %s (funds=%d)",
                        dry_run_prefix, created_at, amount, unit,
                        self.funds_balance)
                except Transaction.DoesNotExist:
                    if not dry_run:
                        _ = Transaction.objects.create(
                            event_id=event_id,
                            descr=descr,
                            created_at=created_at,
                            dest_unit=unit,
                            dest_amount=- amount,
                            dest_account=Transaction.FUNDS,
                            dest_organization=self,
                            orig_unit=unit,
                            orig_amount=- amount,
                            orig_account=Transaction.WITHDRAW,
                            orig_organization=self.processor)
                    LOGGER.debug("%s+ %s payout %d %s (funds=%d)",
                        dry_run_prefix, created_at, amount, unit,
                        self.funds_balance)
                    created = True
            if created and not dry_run:
                # Add processor fee for transfer.
                transfer_fee = self.processor_backend.prorate_transfer(
                    amount, self)
                self.create_processor_fee(transfer_fee, Transaction.FUNDS,
                    event_id=event_id, created_at=created_at)
                if self.funds_balance > amount:
                    self.funds_balance -= amount
                else:
                    # While testing, we reset the database but do not remove
                    # test transactions on Stripe so the payouts are always
                    # bigger than the funds available we have tracked so far.
                    # This issue was silent until Django 2.2.
                    LOGGER.error(
                        "payout at %s of %d %s greater than funds available"\
                        " (%d) in create_withdraw_transactions",
                        created_at, amount, unit, self.funds_balance)
                    self.funds_balance = 0
                self.save()

    def create_processor_fee(self, fee_amount, processor_account,
                             event_id=None, created_at=None, descr=None):
        #pylint: disable=too-many-arguments
        if fee_amount:
            self.validate_processor()
            funds_unit = 'usd' # XXX currency on receipient bank account
            created_at = datetime_or_now(created_at)
            if not descr:
                descr = 'Processor fee'
            if event_id:
                descr += ' for %s' % str(event_id)
            Transaction.objects.create(
                event_id=event_id,
                descr=descr,
                created_at=created_at,
                dest_unit=funds_unit,
                dest_amount=fee_amount,
                dest_account=processor_account,
                dest_organization=self.processor,
                orig_unit=funds_unit,
                orig_amount=fee_amount,
                orig_account=Transaction.FUNDS,
                orig_organization=self)
            self.funds_balance -= fee_amount
            self.save()

    def create_cancel_transactions(self, subscription, amount, dest_unit,
                                   descr=None, created_at=None, user=None):
        """
        Sometimes, a provider will give up and assume receivables cannot
        be recovered from a subscriber. At that point the receivables are
        written off.::

            yyyy/mm/dd sub_***** balance ledger
                subscriber:Liability                       payable_amount
                subscriber:Payable

            yyyy/mm/dd sub_***** write off liability
                provider:Writeoff                          liability_amount
                subscriber:Liability

            yyyy/mm/dd sub_***** write off receivable
                subscriber:Canceled                        liability_amount
                provider:Receivable

        Example::

            2014/09/10 balance ledger
                xia:Liability                             $179.99
                xia:Payable

            2014/09/10 write off liability
                cowork:Writeoff                           $179.99
                xia:Liability

            2014/09/10 write off receivable
                xia:Canceled                              $179.99
                cowork:Receivable
        """
        #pylint:disable=too-many-arguments
        assert amount > 0
        at_time = datetime_or_now(created_at)
        sub_event_id = get_sub_event_id(subscription)
        descr_liability = humanize.DESCRIBE_WRITEOFF_LIABILITY % {
            'event': subscription}
        descr_receivable = humanize.DESCRIBE_WRITEOFF_RECEIVABLE % {
            'event': subscription}
        if descr:
            descr_liability = descr
            descr_receivable = descr
        event_balance = Transaction.objects.get_event_balance(
            sub_event_id, account=Transaction.PAYABLE)
        balance_payable = event_balance['amount']
        with transaction.atomic():
            if balance_payable > 0:
                # Example:
                # 2016/08/16 keep a balanced ledger
                #     xia:Liability                            15800
                #     xia:Payable
                Transaction.objects.create(
                    event_id=sub_event_id,
                    created_at=at_time,
                    descr=humanize.DESCRIBE_DOUBLE_ENTRY_MATCH,
                    dest_unit=dest_unit,
                    dest_amount=balance_payable,
                    dest_account=Transaction.LIABILITY,
                    dest_organization=subscription.organization,
                    orig_unit=dest_unit,
                    orig_amount=balance_payable,
                    orig_account=Transaction.PAYABLE,
                    orig_organization=subscription.organization)
            # Example:
            # 2016/08/16 write off liability
            #     cowork:Writeoff                              15800
            #     xia:Liability
            Transaction.objects.create(
                event_id=sub_event_id,
                created_at=at_time,
                descr=descr_liability,
                dest_unit=dest_unit,
                dest_amount=amount,
                dest_account=Transaction.WRITEOFF,
                dest_organization=subscription.plan.organization,
                orig_unit=dest_unit,
                orig_amount=amount,
                orig_account=Transaction.LIABILITY,
                orig_organization=subscription.organization)
            # Example:
            # 2016/08/16 write off receivable
            #     xia:Cancelled                             15800
            #     cowork:Receivable
            Transaction.objects.create(
                event_id=sub_event_id,
                created_at=at_time,
                descr=descr_receivable,
                dest_unit=dest_unit,
                dest_amount=amount,
                dest_account=Transaction.CANCELED,
                dest_organization=subscription.organization,
                orig_unit=dest_unit,
                orig_amount=amount,
                orig_account=Transaction.RECEIVABLE,
                orig_organization=subscription.plan.organization)
            LOGGER.info("%s cancel balance due of %d for %s.",
                user, amount, self,
                extra={'event': 'cancel-balance',
                    'username': user.username,
                    'organization': self.slug,
                    'amount': amount})


@python_2_unicode_compatible
class Organization(AbstractOrganization):

    class Meta(AbstractOrganization.Meta):
        swappable = 'SAAS_ORGANIZATION_MODEL'

    def __str__(self):
        return str(self.slug)


@python_2_unicode_compatible
class RoleDescription(SlugTitleMixin, models.Model):
    """
    By default, when a ``User`` grants a ``Role`` on an ``Organization``
    to another ``User``, the grantee is required to opt-in the relationship
    unless ``skip_optin_on_grant`` is ``True``. Then the newly created
    relationship is effective immediately.

    In ``Plan`` instances, ``plan.organization`` cannot be ``None`` so
    in a SaaS Web application setting, plans belongs to the broker explicitely.
    In ``RoleDescription`` instances, When ``role_description.organization``
    is ``None``, it is a role description available to all profiles. It
    is thus possible to define role descriptions that are broker-specific.
    """

    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time of creation (in ISO format)"))
    slug = models.SlugField(unique=True,
        help_text=_("Unique identifier shown in the URL bar"))
    organization = models.ForeignKey(
        settings.ORGANIZATION_MODEL, null=True, on_delete=models.CASCADE,
        related_name="role_descriptions")
    title = models.CharField(max_length=20,
        help_text=_("Short description of the role. Grammatical rules to"\
        " pluralize the title might be used in User Interfaces."))
    skip_optin_on_grant = models.BooleanField(default=False,
        help_text=_("Automatically grants the role without requiring a user"\
        " to accept it."))
    implicit_create_on_none = models.BooleanField(default=False,
        help_text=_("Automatically adds the role when a user and profile share"\
        " the same e-mail domain."))
    otp_required = models.BooleanField(default=False,
        help_text=_("Requires users with the role to sign-in using an"\
        " OTP code as a multi-factor authentication."))
    extra = get_extra_field_class()(null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    class Meta:
        unique_together = ('slug', 'organization')

    def __str__(self):
        if self.organization is not None:
            return '%s-%s' % (str(self.slug), str(self.organization))
        return str(self.slug)

    def is_global(self):
        return self.organization is None

    @staticmethod
    def normalize_slug(slug):
        slug = slug.lower()
        if slug.endswith('s'):
            slug = slug[:-1]
        return slug


class RoleManager(models.Manager):

    def accessible_by(self, user, force_personal=False, at_time=None):
        """
        Returns a `Role` queryset with all roles for `user`, either
        vallid, pending grants or pending requests.
        """
        at_time = datetime_or_now(at_time)

        # Add implicit grants, which can either be a personal profile
        # or natural profiles based on a user work e-mail, when those roles
        # don't already exists in the database.
        self.create_implicit_roles(user,
            force_personal=force_personal, at_time=at_time)

        # We have added all the implicit grants, now let's accept the grant
        # with a `skip_optin_on_grant`.
        # Implementation Note: we are expecting the record in the database
        # to be well formed (i.e. `request_key is None` and
        # `role_descr is not None`).
        queryset = self.filter(
            Q(ends_at__isnull=True) | Q(ends_at__gt=at_time), user=user)
        pending_grants = queryset.filter(grant_key__isnull=False)
        for role in pending_grants:
            assert role.request_key is None
            assert role.role_description is not None
            if role.role_description.skip_optin_on_grant:
                role.grant_key = None
                role.save()

        queryset = self.filter(
            Q(ends_at__isnull=True) | Q(ends_at__gt=at_time), user=user)
        return queryset

    def create_implicit_roles(self, user, force_personal=False, at_time=None):
        organization_model = get_organization_model()
        at_time = datetime_or_now(at_time)

        # Check if we should add a personal profile in the implicit grants.
        if force_personal and not self.filter(
                user=user, organization__slug=user.username).exists():
            # We don't have a personal profile, but we selected some
            # cart items that require it.
            organization_model.objects.create_organization_from_user(user)

        # Find a RoleDescription we can implicitely grant to the user,
        # and the natural profiles based on the user work e-mail address.
        if user.email:
            nb_candidates = 0
            email_parts = user.email.lower().split('@')
            domain = email_parts[-1]
            nb_candidates = organization_model.objects.filter(
                email__iexact=user.email).count()
            if not is_mail_provider_domain(domain):
                nb_candidates += \
                    organization_model.objects.find_candidates_by_domain(
                        domain).count()

            if nb_candidates < settings.MAX_TYPEAHEAD_CANDIDATES:
                # If we have too many candidates for implicit grants, bail out.
                candidates = list(organization_model.objects.filter(
                    email__iexact=user.email).exclude(role__user=user))
                if not is_mail_provider_domain(domain):
                    candidates += list(
                        organization_model.objects.find_candidates_by_domain(
                            domain).exclude(role__user=user))
                for profile in candidates:
                    try:
                        role_descr = RoleDescription.objects.filter(
                            organization=profile,
                            implicit_create_on_none=True).get()
                        profile.add_role_grant(
                            user, role_descr, at_time=at_time)
                        continue
                    except RoleDescription.DoesNotExist:
                        LOGGER.debug(
                            "'%s' does not have a role on any profile but"
                            " we cannot grant one implicitely because there is"
                            " no profile role description that permits it.",
                            user)
                    except RoleDescription.MultipleObjectsReturned:
                        LOGGER.debug(
                            "'%s' does not have a role on any profile but we"
                            " cannot grant one implicitely because we have"
                            " multiple profile role description"
                            " that permits it. Ambiguous.", user)
                    try:
                        role_descr = RoleDescription.objects.filter(
                            organization__isnull=True,
                            implicit_create_on_none=True).get()
                        profile.add_role_grant(
                            user, role_descr, at_time=at_time)
                        continue
                    except RoleDescription.DoesNotExist:
                        LOGGER.debug(
                            "'%s' does not have a role on any profile but"
                            " we cannot grant one implicitely because there is"
                            " no global role description that permits it.",
                            user)
                    except RoleDescription.MultipleObjectsReturned:
                        LOGGER.debug(
                            "'%s' does not have a role on any profile but we"
                            " cannot grant one implicitely because we have"
                            " multiple global role description"
                            " that permits it. Ambiguous.", user)


    def role_on_subscriber(self, user, plan, role_descr=None):
        user_model = get_user_model()
        if not isinstance(user, user_model):
            user = user_model.objects.get(username=user)
        if role_descr:
            if isinstance(role_descr, RoleDescription):
                kwargs = {'role_description': role_descr}
            else:
                kwargs = {'role_description__slug': role_descr}
        return self.filter(
            user=user, organization__subscribes_to=plan, **kwargs)


    def valid_for(self, includes_personal=True, **kwargs):
        """
        Returns a `Role` queryset that are valid and filtered by arguments
        in `kwargs`. When `includes_personal` is `True`, the returned
        queryset includes a role for the personal profile if it exists.
        """
        queryset = self.filter(Q(ends_at__isnull=True) |
            Q(ends_at__gt=datetime_or_now()),
            grant_key=None, request_key=None, **kwargs)
        if not includes_personal:
            queryset = queryset.exclude(organization__slug=F('user__username'))
        return queryset


@python_2_unicode_compatible
class AbstractRole(models.Model):

    objects = RoleManager()

    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time of creation (in ISO format)"))
    organization = models.ForeignKey(settings.ORGANIZATION_MODEL,
        on_delete=models.CASCADE, related_name='role')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        db_column='user_id', related_name='role')
    role_description = models.ForeignKey(RoleDescription, null=True,
        on_delete=models.CASCADE)
    request_key = models.SlugField(max_length=40, null=True, blank=True,
        help_text=_("Key to identify the request for the role"))
    grant_key = models.SlugField(max_length=40, null=True, blank=True,
        help_text=_("Key to identify the grant of the role"))
    extra = get_extra_field_class()(null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))
    ends_at = models.DateTimeField(null=True, blank=True,
        help_text=_('Date/time when the role ends'))
    class Meta:
        abstract = True
        unique_together = ('organization', 'user')

    def __str__(self):
        return '%s-%s-%s' % (str(self.role_description),
                             str(self.organization), str(self.user))


@python_2_unicode_compatible
class Role(AbstractRole):

    class Meta(AbstractRole.Meta):
        swappable = 'SAAS_ROLE_MODEL'

    def __str__(self):
        return '%s-%s-%s' % (str(self.role_description),
            str(self.organization), str(self.user))


@python_2_unicode_compatible
class Agreement(models.Model):

    slug = models.SlugField(unique=True,
        help_text=_("Unique identifier shown in the URL bar"))
    title = models.CharField(max_length=150, unique=True,
        help_text=_("Short description of the agreement"))
    updated_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time the agreement was last updated (in ISO format)"))

    def __str__(self):
        return str(self.slug)


class SignatureManager(models.Manager):

    def create_signature(self, agreement, user):
        if isinstance(agreement, six.string_types):
            #pylint: disable=no-member
            agreement = Agreement.objects.db_manager(self.db).get(
                slug=agreement)
        try:
            sig = self.get(agreement=agreement, user=user)
            sig.last_signed = datetime_or_now()
            sig.save()
        except Signature.DoesNotExist:
            sig = self.create(agreement=agreement, user=user)
        return sig

    def has_been_accepted(self, agreement, user):
        if isinstance(agreement, six.string_types):
            agreement = Agreement.objects.get(slug=agreement)
        try:
            sig = self.get(agreement=agreement, user=user)
            if sig.last_signed < agreement.updated_at:
                return False
        except Signature.DoesNotExist:
            return False
        return True


@python_2_unicode_compatible
class Signature(models.Model):

    objects = SignatureManager()

    last_signed = models.DateTimeField(auto_now_add=True)
    agreement = models.ForeignKey(Agreement, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, db_column='user_id',
        related_name='signatures', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('agreement', 'user')

    def __str__(self):
        return '%s-%s' % (self.user, self.agreement)


class ChargeManager(models.Manager):

    def by_customer(self, organization):
        return self.filter(customer=organization)

    def get_by_event_id(self, event_id):
        """
        Returns a `Charge` based on a `Transaction.event_id` key.
        """
        if not event_id:
            return None
        look = re.match(r'^cha_(\d+)/', event_id)
        if not look:
            return None
        try:
            return self.get(pk=int(look.group(1)))
        except Charge.DoesNotExist:
            pass
        return None


    def in_progress_for_customer(self, organization):
        return self.by_customer(organization).filter(
            state=Charge.CREATED).exclude(processor_key__isnull=True)


    def settle_customer_payments(self, organization):
        """
        This will call the processor backend to attempt to settle charges
        into a success or failed state.
        """
        for charge in self.in_progress_for_customer(organization):
            charge.retrieve()

    def create_charge(self, customer, transactions, amount, unit,
                      user=None, created_at=None):
        #pylint: disable=too-many-arguments
        assert amount > 0
        created_at = datetime_or_now(created_at)
        with transaction.atomic():
            charge = self.create(
                claim_code=generate_random_slug(),
                amount=amount, unit=unit, customer=customer,
                created_at=created_at, created_by=user)
            for invoiced in transactions:
                # XXX Here we need to associate the (invoice_key, sync_on)
                # to the ChargeItem.
                ChargeItem.objects.create(invoiced=invoiced, charge=charge,
                    invoice_key=getattr(invoiced, 'invoice_key', None),
                    sync_on=getattr(invoiced, 'sync_on', None))
            LOGGER.info("  %s create charge %s of %d %s to %s",
                charge.created_at, charge.claim_code,
                charge.amount, charge.unit, customer,
                extra={'event': 'create-charge',
                    'charge': charge.claim_code,
                    'organization': customer.slug,
                    'amount': charge.amount, 'unit': charge.unit})
        return charge

    def create_charges_by_processor(self, customer, transactions,
                                    user=None, created_at=None):
        #pylint: disable=too-many-arguments
        created_at = datetime_or_now(created_at)
        charges = []
        balances = sum_dest_amount(transactions)
        if len(balances) > 1:
            raise ValueError(_("balances with multiple currency units (%s)") %
                str(balances))
        # `sum_dest_amount` guarentees at least one result.
        amount = balances[0]['amount']
        if amount == 0:
            return []
        for invoice_items in six.itervalues(
                Transaction.objects.by_processor_key(transactions)):
            balances = sum_dest_amount(invoice_items)
            if len(balances) > 1:
                raise ValueError(
                    _("balances with multiple currency units (%s)") % str(
                    balances))
            # `sum_dest_amount` guarentees at least one result.
            amount = balances[0]['amount']
            unit = balances[0]['unit']
            if amount == 0:
                continue
            charges += [self.create_charge(customer, invoice_items,
                amount, unit, user=user, created_at=created_at)]

        return charges


@python_2_unicode_compatible
class Charge(models.Model):
    """
    Keep track of charges that have been emitted by the app.
    We save the name of the card, last4 and expiration date so we are able
    to present a receipt usable for expenses re-imbursement.
    """
    #pylint:disable=too-many-instance-attributes
    CREATED = 0
    DONE = 1
    FAILED = 2
    DISPUTED = 3
    CHARGE_STATES = (
        (CREATED, 'created'),
        (DONE, 'done'),
        (FAILED, 'failed'),
        (DISPUTED, 'disputed')
    )

    objects = ChargeManager()

    claim_code = models.SlugField(db_index=True, null=True,
        help_text=_("Unique code used to retrieve the invoice / charge"))
    created_at = models.DateTimeField(
        help_text=_("Date/time of creation (in ISO format)"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT,
        db_column='user_id')
    amount = models.PositiveIntegerField(default=0,
        help_text=_("Total amount in currency unit"))
    unit = models.CharField(max_length=3, default=settings.DEFAULT_UNIT,
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))
    customer = models.ForeignKey(settings.ORGANIZATION_MODEL,
        on_delete=models.PROTECT,
        help_text=_("Organization charged"))
    description = models.TextField(null=True,
        help_text=_("Description for the charge as appears on billing"\
            " statements"))
    last4 = models.PositiveSmallIntegerField(null=True,
        help_text=_("Last 4 digits of the credit card used"))
    exp_date = models.DateField(null=True,
        help_text=_("Expiration date of the credit card used"))
    card_name = models.CharField(max_length=50, null=True)
    processor = models.ForeignKey(settings.ORGANIZATION_MODEL, null=True,
        on_delete=models.PROTECT, related_name='charges')
    processor_key = models.SlugField(max_length=255, unique=True, null=True,
        db_index=True,
        help_text=_("Unique identifier returned by the payment processor"))
    state = models.PositiveSmallIntegerField(
        choices=CHARGE_STATES, default=CREATED,
        help_text=_("Current state (i.e. created, done, failed, disputed)"))
    extra = get_extra_field_class()(null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    # XXX unique together paid and invoiced.
    # customer and invoiced_items account payble should match.

    def __str__(self):
        return (str(self.processor_key) if self.processor_key
            else str(self.claim_code))

    def get_last4_display(self):
        return "%04d" % self.last4 if self.last4 else ""

    @property
    def broker_fee_amount(self):
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_broker_fee_amount'):
            self._broker_fee_amount = 0
            for charge_item in self.charge_items.all():
                invoiced_item = charge_item.invoiced
                if invoiced_item.subscription:
                    self._broker_fee_amount += \
                        invoiced_item.subscription.plan.prorate_transaction(
                            invoiced_item.dest_amount)
        return self._broker_fee_amount

    @property
    def price(self):
        return Price(self.amount, self.unit)

    @property
    def state_string(self):
        return self.get_state_display()

    @property
    def line_items(self):
        """
        In most cases, use the ``line_items`` property instead of
        the ``charge_items`` because the order in which the records
        are returned is not guarenteed by SQL.
        This is important when identifying line items by an index.
        """
        return self.charge_items.order_by('id')

    @property
    def line_items_grouped_by_subscription(self):
        """
        Returns line items in a format compatible with the checkout API
        """
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_line_items_grouped_by_subscription'):
            by_subscriptions = {}
            for line in self.charge_items.order_by('invoiced__event_id'):
                subscription = line.subscription
                if subscription:
                    lines = by_subscriptions.get(subscription, [])
                    if not lines:
                        by_subscriptions.update({subscription: lines})
                    lines += [line.invoiced]
            self._line_items_grouped_by_subscription = []
            for subscription, lines in six.iteritems(by_subscriptions):
                self._line_items_grouped_by_subscription += [{
                    'subscription': subscription,
                    'lines': lines
                }]
        return self._line_items_grouped_by_subscription

    @property
    def processor_backend(self):
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_processor_backend'):
            # XXX We should load the backend from `self.processor`.
            #     As long we do not change processor, this workaround
            #     will do.
            self._processor_backend = get_broker().processor_backend
        return self._processor_backend

    @property
    def invoiced_total(self):
        """
        Returns the total amount and unit of all invoiced items.
        """
        balances = sum_dest_amount(Transaction.objects.filter(
            invoiced_item__charge=self))
        if len(balances) > 1:
            raise ValueError(_("balances with multiple currency units (%s)") %
                str(balances))
        # `sum_dest_amount` guarentees at least one result.
        amount = balances[0]['amount']
        unit = balances[0]['unit']
        return Price(amount, unit)

    @property
    def invoiced_total_after_refund(self):
        """
        Returns the total amount and unit charged after refunds
        have been deducted.
        """
        invoiced_total = self.invoiced_total
        refund_balances = sum_orig_amount(self.refunded)
        if len(refund_balances) > 1:
            raise ValueError(
                _("balances with multiple currency units (%s)") %
                str(refund_balances))
        # `sum_dest_amount` guarentees at least one result.
        refund_amount = refund_balances[0]['amount']
        refund_unit = refund_balances[0]['unit']
        if refund_amount and invoiced_total.unit != refund_unit:
            raise ValueError(
                _("charge and refunds have different units"\
" (%(unit)s vs. %(refund_unit)s)") % (
                {'unit': invoiced_total.unit, 'refund_unit': refund_unit}))
        return Price(invoiced_total.amount - refund_amount, invoiced_total.unit)

    @property
    def is_disputed(self):
        return self.state == self.DISPUTED

    @property
    def is_failed(self):
        return self.state == self.FAILED

    @property
    def is_paid(self):
        return self.state == self.DONE

    @property
    def is_progress(self):
        return self.state == self.CREATED

    @property
    def refunded(self):
        """
        All ``Transaction`` which are part of a refund for this ``Charge``.
        """
        return Transaction.objects.by_charge(self).filter(
            orig_account=Transaction.REFUNDED)

    def capture(self):
        # XXX Create transaction
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    @property
    def provider(self):
        """
        All the invoiced items on this charge must be related to the same
        broker ``Organization``.
        """
        #pylint: disable=no-member
        organization_model = get_organization_model()
        providers = organization_model.objects.receivable_providers([
            charge_item.invoiced for charge_item in self.charge_items.all()])
        nb_providers = len(providers)
        assert nb_providers <= 1
        if nb_providers == 1:
            return providers[0]
        # So it does not look weird when we are testing receipts
        return get_broker()

    def dispute_created(self):
        #pylint: disable=too-many-locals
        assert self.state == self.DONE
        created_at = datetime_or_now()
        balances = sum_orig_amount(self.refunded)
        if len(balances) > 1:
            raise ValueError(_("balances with multiple currency units (%s)") %
                str(balances))
        # `sum_orig_amount` guarentees at least one result.
        previously_refunded = balances[0]['amount']
        refund_available = self.amount - previously_refunded
        charge_available_amount, provider_unit, \
            charge_processor_fee_amount, processor_unit, \
            charge_broker_fee_amount, broker_unit \
            = self.processor_backend.charge_distribution(self, get_broker())
        corrected_available_amount = charge_available_amount
        corrected_processor_fee_amount = charge_processor_fee_amount
        corrected_broker_fee_amount = charge_broker_fee_amount
        providers = set([])
        with transaction.atomic():
            updated = Charge.objects.select_for_update(nowait=True).filter(
                pk=self.pk, state=self.DONE).update(state=self.DISPUTED)
            if not updated:
                raise DatabaseError(
                    "Charge is currently being updated by another transaction")
            for charge_item in self.line_items:
                refunded_amount = min(refund_available,
                    charge_item.invoiced.dest_amount)
                provider = charge_item.invoiced.orig_organization
                if not provider in providers:
                    provider.create_processor_fee(
                        self.processor_backend.dispute_fee(self.amount),
                        Transaction.CHARGEBACK,
                        event_id=get_charge_event_id(self),
                        created_at=created_at)
                    providers |= set([provider])
                charge_item.create_refund_transactions(
                    refunded_amount,
                    Price(charge_available_amount, provider_unit),
                    Price(charge_processor_fee_amount, processor_unit),
                    Price(charge_broker_fee_amount, broker_unit),
                    Price(corrected_available_amount, provider_unit),
                    Price(corrected_processor_fee_amount, processor_unit),
                    Price(corrected_broker_fee_amount, broker_unit),
                    created_at=created_at, refund_type=Transaction.CHARGEBACK)
                refund_available -= refunded_amount
        # We did a `select_for_update` earlier on but that did not change
        # in state of the `self` currently in memory.
        self.state = self.DISPUTED
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def dispute_updated(self):
        with transaction.atomic():
            Charge.objects.select_for_update(nowait=True).filter(
                pk=self.pk).update(state=self.DISPUTED)
        # We did a `select_for_update` earlier on but that did not change
        # in state of the `self` currently in memory.
        self.state = self.DISPUTED
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def dispute_lost(self):
        with transaction.atomic():
            Charge.objects.select_for_update(nowait=True).filter(
                pk=self.pk).update(state=self.FAILED)
        # We did a `select_for_update` earlier on but that did not change
        # in state of the `self` currently in memory.
        self.state = self.FAILED
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def dispute_won(self):
        assert self.state == self.DISPUTED
        with transaction.atomic():
            updated = Charge.objects.select_for_update(nowait=True).filter(
                pk=self.pk, state=self.DISPUTED).update(state=self.DONE)
            if not updated:
                raise DatabaseError(
                    "Charge is currently being updated by another transaction")
            for reverted in Transaction.objects.by_charge(self).filter(
                    dest_account=Transaction.CHARGEBACK):
                Transaction.objects.create(
                    event_id=reverted.event_id,
                    descr='%s - reverted' % reverted.descr,
                    created_at=reverted.created_at,
                    dest_unit=reverted.orig_unit,
                    dest_amount=reverted.orig_amount,
                    dest_account=reverted.orig_account,
                    dest_organization=reverted.orig_organization,
                    orig_unit=reverted.dest_unit,
                    orig_amount=reverted.dest_amount,
                    orig_account=reverted.dest_account,
                    orig_organization=reverted.dest_organization)
        # We did a `select_for_update` earlier on but that did not change
        # in state of the `self` currently in memory.
        self.state = self.DONE
        signals.charge_updated.send(sender=__name__, charge=self, user=None)


    def execute(self, token=None, user=None,
                descr=None, remember_card=True, created_at=None):
        #pylint:disable=too-many-arguments
        created_at = datetime_or_now(created_at)
        broker = get_broker()
        provider = self.provider
        self.processor = provider.validate_processor()
        prev_processor_card_key = self.customer.processor_card_key

        try:
            if token and remember_card:
                self.customer.update_card(token, user, provider=provider)
                token = self.customer.processor_card_key
            if not token:
                token = self.customer.processor_card_key

            if token:
                (processor_charge_key, created_at,
                 receipt_info) = provider.processor_backend.create_payment(
                     self.amount, self.unit, token,
                     descr=descr, created_at=created_at, provider=provider,
                     broker_fee_amount=self.broker_fee_amount, broker=broker)
            else:
                raise ProcessorError(_("The profile doesn't have a payment"\
                    " method on file, and no payment token was passed."))

            # Update the record of the charge in our database
            self.processor_key = processor_charge_key
            self.last4 = receipt_info.get('last4')
            if self.last4:
                self.last4 = int(self.last4)
            self.exp_date = receipt_info.get('exp_date')
            self.card_name = receipt_info.get('card_name', "")
            self.description = humanize.DESCRIBE_CHARGED_CARD % {
                'charge': processor_charge_key,
                'organization': self.card_name}
            if user:
                self.description += ' (%s)' % user.username
            self.save()
        except CardError as err:
            # Implementation Note:
            # We are going to rollback because of the ``transaction.atomic``
            # in ``checkout``. There is two choices here:
            #   1) We persist the created ``Stripe.Customer``
            #      in ``checkout`` after the rollback.
            #   2) We forget about the created ``Stripe.Customer`` and
            #      reset the processor_card_key.
            # We implement (2) because the UI feedback to a user looks
            # strange when the Card is persisted while an error message
            # is displayed.
            self.customer.processor_card_key = prev_processor_card_key
            LOGGER.info('error: CardError "%s" processing charge'\
                ' %s of %d %s to %s',
                err.processor_details(), err.charge_processor_key,
                self.amount, self.unit, self.customer,
                extra={'event': 'card-error',
                    'charge': err.charge_processor_key,
                    'detail': err.processor_details(),
                    'organization': self.customer.slug,
                    'amount': self.amount, 'unit': self.unit})
            raise
        except ProcessorSetupError as err:
            # When a provider Stripe account is not connected correctly,
            # it is not obviously a problem with the broker. So we send
            # a signal to alert the provider instead of triggering an error
            # that needs to be investigated by the broker hosting platform.
            LOGGER.info('error: ProcessorSetupError "%s" processing charge'\
                ' of %d %s to %s',
                err.processor_details(), self.amount, self.unit, self.customer,
                extra={'event': 'processor-setup-error',
                    'detail': err.processor_details(),
                    'provider': str(err.provider),
                    'organization': self.customer.slug,
                    'amount': self.amount, 'unit': self.unit})
            signals.processor_setup_error.send(sender=__name__,
                provider=err.provider, error_message=str(err),
                customer=self.customer)
            raise
        except ProcessorError as err:
            # An error from the processor which indicates the logic might be
            # incorrect, the network down, etc. We want to know about it
            # right away.
            LOGGER.exception("ProcessorError for charge of %d %s to %s: %s",
                self.amount, self.unit, self.customer, err)
            # We are going to rollback because of the ``transaction.atomic``
            # in ``checkout`` so let's reset the processor_card_key.
            self.customer.processor_card_key = prev_processor_card_key
            raise


    def failed(self, receipt_info=None):
        assert self.state == self.CREATED
        kwargs = {}
        if receipt_info:
            self.last4 = int(receipt_info.get('last4'))
            self.exp_date = receipt_info.get('exp_date')
            self.card_name = receipt_info.get('card_name', "")
            kwargs.update({
                'last4': self.last4,
                'exp_date': self.exp_date,
                'card_name': self.card_name
            })
        with transaction.atomic():
            updated = Charge.objects.select_for_update(nowait=True).filter(
                pk=self.pk, state=self.CREATED).update(
                    state=self.FAILED, **kwargs)
            if not updated:
                raise DatabaseError(
                    "Charge is currently being updated by another transaction")
        # We did a `select_for_update` earlier on but that did not change
        # in state of the `self` currently in memory.
        self.state = self.FAILED
        signals.charge_updated.send(sender=__name__, charge=self, user=None)

    def payment_successful(self, receipt_info=None):
        """
        When a charge through the payment processor is sucessful,
        a unique ``Transaction`` records the charge through the processor.
        The amount of the charge is then redistributed to the providers
        (minus processor fee)::

            ; Record the charge

            yyyy/mm/dd cha_***** charge event
                processor:Funds                          charge_amount
                subscriber:Liability

            ; Compensate for atomicity of charge record (when necessary)

            yyyy/mm/dd sub_***** invoiced-item event
                subscriber:Liability           min(invoiced_item_amount,
                subscriber:Payable                      balance_payable)

            ; Distribute processor fee and funds to the provider

            yyyy/mm/dd cha_***** processor fee paid by broker for provider
                broker:Expenses                          processor_fee
                processor:Backlog

            yyyy/mm/dd cha_***** broker fee paid by provider
                provider:Expenses                        broker_fee_amount
                broker:Backlog

            yyyy/mm/dd cha_***** distribution to broker
                broker:Funds                             broker_fee_amount
                processor:Funds

            yyyy/mm/dd sub_***** distribution to provider (backlog accounting)
                provider:Receivable                      plan_amount
                provider:Backlog

            yyyy/mm/dd cha_***** distribution to provider
                provider:Funds                           distribute_amount
                processor:Funds

        Example::

            2014/09/10 Charge ch_ABC123 on credit card of xia
                stripe:Funds                           $179.99
                xia:Liability

            2014/09/10 Keep a balanced ledger
                xia:Liability                          $179.99
                xia:Payable

            2014/09/10 Charge ch_ABC123 broker fee to cowork
                cowork:Expenses                        $17.99
                broker:Backlog

            2014/09/10 Charge ch_ABC123 distribution due to cowork
                broker:Funds                           $17.99
                stripe:Funds

            2014/09/10 Charge ch_ABC123 processor fee for open-space
                cowork:Expenses                         $5.22
                stripe:Backlog

            2014/09/10 Charge ch_ABC123 distribution for open-space
                cowork:Receivable                     $179.99
                cowork:Backlog

            2014/09/10 Charge ch_ABC123 distribution for open-space
                cowork:Funds                          $156.78
                stripe:Funds
        """
        #pylint: disable=too-many-locals,too-many-statements
        assert self.state == self.CREATED
        kwargs = {}
        if receipt_info:
            self.last4 = int(receipt_info.get('last4'))
            self.exp_date = receipt_info.get('exp_date')
            self.card_name = receipt_info.get('card_name', "")
            kwargs.update({
                'last4': self.last4,
                'exp_date': self.exp_date,
                'card_name': self.card_name
            })
        with transaction.atomic():
            # up at the top of this method so that we bail out quickly, before
            # we start to mistakenly enter the charge and distributions a second
            # time on two rapid fire `Charge.retrieve()` calls.
            updated = Charge.objects.select_for_update(nowait=True).filter(
                pk=self.pk, state=self.CREATED).update(
                    state=self.DONE, **kwargs)
            if not updated:
                raise DatabaseError(
                    "Charge is currently being updated by another transaction")

            # Example:
            # 2014/01/15 charge on xia card
            #     stripe:Funds                                 15800
            #     xia:Liability
            broker = get_broker()
            orig_total = self.amount
            orig_broker_fee = self.broker_fee_amount
            charge_available_amount, funds_unit, \
                charge_processor_fee_amount, processor_funds_unit, \
                charge_broker_fee_amount, broker_funds_unit \
                = self.processor_backend.charge_distribution(self, broker,
                    orig_total_broker_fee_amount=orig_broker_fee)
            charge_amount = (charge_available_amount
                + charge_processor_fee_amount + charge_broker_fee_amount)
            assert isinstance(charge_amount, six.integer_types)

            dest_total = charge_amount
            dest_distribute = charge_available_amount
            dest_broker_fee = charge_broker_fee_amount
            # dest_processor_fee = charge_processor_fee_amount

            charge_transaction = Transaction.objects.create(
                event_id=get_charge_event_id(self),
                descr=self.description,
                created_at=self.created_at,
                dest_unit=self.unit,
                # XXX provider and processor must have same units.
                dest_amount=orig_total,
                dest_account=Transaction.FUNDS,
                dest_organization=self.processor,
                orig_unit=self.unit,
                orig_amount=orig_total,
                orig_account=Transaction.LIABILITY,
                orig_organization=self.customer)

            # Once we have created a transaction for the charge, let's
            # redistribute the funds to their rightful owners.
            for charge_item in self.charge_items.all():
                invoiced_item = charge_item.invoiced
                item_orig_total = invoiced_item.dest_amount
                item_orig_unit = invoiced_item.dest_unit

                # If there is still an amount on the ``Payable`` account,
                # we create Payable to Liability transaction in order to correct
                # the accounts amounts. This is a side effect of the atomicity
                # requirement for a ``Transaction`` associated to a ``Charge``.
                balance = Transaction.objects.get_event_balance(
                    invoiced_item.event_id, account=Transaction.PAYABLE)
                balance_payable = balance['amount']
                if balance_payable > 0:
                    available = min(item_orig_total, balance_payable)
                    # Example:
                    # 2014/01/15 keep a balanced ledger
                    #     xia:Liability                                 15800
                    #     xia:Payable
                    Transaction.objects.create(
                        event_id=invoiced_item.event_id,
                        created_at=self.created_at,
                        descr=humanize.DESCRIBE_DOUBLE_ENTRY_MATCH,
                        dest_unit=invoiced_item.dest_unit,
                        dest_amount=available,
                        dest_account=Transaction.LIABILITY,
                        dest_organization=invoiced_item.dest_organization,
                        orig_unit=invoiced_item.dest_unit,
                        orig_amount=available,
                        orig_account=Transaction.PAYABLE,
                        orig_organization=invoiced_item.dest_organization)

                # XXX event_id is used for provider and in description.
                event = None
                event_id = invoiced_item.event_id
                item_orig_broker_fee = 0
                event = invoiced_item.get_event() # Subscription,
                                                  # or Coupon (i.e. Group buy)
                if event:
                    # XXX event shouldn't be anything but a Subscription here.
                    # How could it be Coupon?
                    provider = event.provider
                    if isinstance(event, Subscription):
                        item_orig_broker_fee = event.plan.prorate_transaction(
                            item_orig_total)
                else:
                    provider = broker
                # orig_total = item_orig_total_1 + item_orig_total_2
                # item_orig_total_1 = (item_orig_distribute_1
                #     + item_orig_processor_fee_1 + item_orig_broker_fee_1)

                # As long as we have only one item and charge/funds are using
                # same unit, multiplication and division are carefully crafted
                # to keep full precision.
                # XXX to check with transfer btw currencies and multiple items.
                # integer divisions
                item_orig_distribute = (
                    item_orig_total * dest_distribute // dest_total)
                item_orig_processor_fee = (item_orig_total
                    - item_orig_distribute - item_orig_broker_fee)

                assert isinstance(item_orig_processor_fee, six.integer_types)
                assert isinstance(item_orig_broker_fee, six.integer_types)
                assert isinstance(item_orig_distribute, six.integer_types)

                # integer divisions
                item_dest_total = item_orig_total * dest_total // orig_total

                # The charge_broker_fee_amount must be split amongst all items
                # with a broker fee rather than equaly amongst all items.
                if orig_broker_fee:
                    item_dest_broker_fee = (
                      item_orig_broker_fee * dest_broker_fee // orig_broker_fee)
                else:
                    item_dest_broker_fee = 0
                item_dest_distribute = (
                    item_dest_total * dest_distribute // dest_total)
                item_dest_processor_fee = (item_dest_total
                    - item_dest_distribute - item_dest_broker_fee)

                assert isinstance(item_dest_processor_fee, six.integer_types)
                assert isinstance(item_dest_broker_fee, six.integer_types)
                assert isinstance(item_dest_distribute, six.integer_types)

                LOGGER.debug("payment_successful(charge=%s)"\
                    " distribute: %d %s (%d %s),"\
                    " broker fee: %d %s (%d %s),"\
                    " processor fee: %d %s (%d %s) out of total"\
                    " distribute: %d %s,"\
                    " broker fee: %d %s (%d %s),"\
                    " processor fee: %d %s",
                    self.processor_key,
                    item_dest_distribute, funds_unit,
                    item_orig_distribute, item_orig_unit,
                    item_dest_broker_fee, broker_funds_unit,
                    item_orig_broker_fee, item_orig_unit,
                    item_dest_processor_fee, processor_funds_unit,
                    item_orig_processor_fee, item_orig_unit,
                    charge_available_amount, funds_unit,
                    charge_broker_fee_amount, broker_funds_unit,
                    orig_broker_fee, item_orig_unit,
                    charge_processor_fee_amount, processor_funds_unit)

                if item_dest_processor_fee > 0:
                    # Example:
                    # 2014/01/15 processor fee to cowork
                    #     cowork:Expenses                             900
                    #     stripe:Backlog
                    charge_item.invoiced_processor_fee = \
                        Transaction.objects.create(
                        created_at=self.created_at,
                        descr=humanize.DESCRIBE_CHARGED_CARD_PROCESSOR % {
                            'charge': self.processor_key, 'event': event_id},
                        event_id=get_charge_event_id(self),
                        dest_unit=funds_unit,
                        dest_amount=item_dest_processor_fee,
                        dest_account=Transaction.EXPENSES,
                        dest_organization=broker,
                        orig_unit=self.unit,
                        orig_amount=item_orig_processor_fee,
                        orig_account=Transaction.BACKLOG,
                        orig_organization=self.processor)
                    # pylint:disable=no-member
                    self.processor.funds_balance += item_dest_processor_fee
                    self.processor.save()

                if item_dest_broker_fee > 0:
                    # Example:
                    # 2014/01/15 broker fee to cowork
                    #     cowork:Expenses                             900
                    #     broker:Backlog
                    #
                    # 2014/01/15 distribution due to broker
                    #     broker:Funds                               7000
                    #     stripe:Funds
                    charge_item.invoiced_broker_fee = \
                        Transaction.objects.create(
                        created_at=self.created_at,
                        descr=humanize.DESCRIBE_CHARGED_CARD_BROKER % {
                            'charge': self.processor_key, 'event': event_id},
                        event_id=get_charge_event_id(self),
                        dest_unit=funds_unit,
                        dest_amount=item_dest_total - item_dest_distribute,
                        dest_account=Transaction.EXPENSES,
                        dest_organization=provider,
                        orig_unit=self.unit,
                        orig_amount=item_orig_total - item_orig_distribute,
                        orig_account=Transaction.BACKLOG,
                        orig_organization=broker)
                    Transaction.objects.create(
                        event_id=get_charge_event_id(self),
                        created_at=self.created_at,
                        descr=humanize.DESCRIBE_CHARGED_CARD_BROKER % {
                                'charge': self.processor_key, 'event': event},
                        dest_unit=funds_unit,
                        dest_amount=item_dest_broker_fee,
                        dest_account=Transaction.FUNDS,
                        dest_organization=broker,
                        orig_unit=self.unit,
                        orig_amount=item_orig_broker_fee,
                        orig_account=Transaction.FUNDS,
                        orig_organization=self.processor)
                    broker.funds_balance += item_dest_broker_fee
                    broker.save()

                # Example:
                # 2014/01/15 distribution due to cowork
                #     cowork:Receivable                             8000
                #     cowork:Backlog
                #
                # 2014/01/15 distribution due to cowork
                #     cowork:Funds                                  7000
                #     stripe:Funds

                # XXX Just making sure we don't screw up rounding
                # when using the same unit.
                Transaction.objects.create(
                    event_id=event_id,
                    created_at=self.created_at,
                    # Implementation Note: We use `event` here instead
                    # of `event_id` such that the plan name shows up
                    # in the description. This was the previous behavior
                    # and customers are relying on this do their accounting.
                    descr=humanize.DESCRIBE_CHARGED_CARD_PROVIDER % {
                            'charge': self.processor_key, 'event': event},
                    dest_unit=self.unit,
                    dest_amount=item_orig_total,
                    dest_account=Transaction.RECEIVABLE,
                    dest_organization=provider,
                    orig_unit=funds_unit,
                    orig_amount=item_dest_total,
                    orig_account=Transaction.BACKLOG,
                    orig_organization=provider)

                # See comment above for use of `event`.
                if self.unit == funds_unit:
                    assert item_orig_distribute == item_dest_distribute
                charge_item.invoiced_distribute = Transaction.objects.create(
                    event_id=get_charge_event_id(self),
                    created_at=self.created_at,
                    descr=humanize.DESCRIBE_CHARGED_CARD_PROVIDER % {
                            'charge': self.processor_key, 'event': event},
                    dest_unit=funds_unit,
                    dest_amount=item_dest_distribute,
                    dest_account=Transaction.FUNDS,
                    dest_organization=provider,
                    orig_unit=self.unit,
                    orig_amount=item_orig_distribute,
                    orig_account=Transaction.FUNDS,
                    orig_organization=self.processor)
                charge_item.save()
                provider.funds_balance += item_dest_distribute
                provider.save()

            invoiced_amount = self.invoiced_total.amount
            if invoiced_amount > orig_total:
                raise IntegrityError("The total amount of invoiced items for "\
                    "charge %s exceed the amount of the charge." %
                    self.processor_key)
            # We did a `select_for_update` earlier on but that did not change
            # in state of the `self` currently in memory.
            self.state = self.DONE
        signals.charge_updated.send(sender=__name__, charge=self, user=None)
        return charge_transaction

    def refund(self, linenum, refunded_amount=None, created_at=None, user=None):
        # XXX We donot currently supply a *description* for the refund.
        #pylint:disable=too-many-locals
        assert self.state == self.DONE

        # We do all computation and checks before starting to modify
        # the database to minimize the chances of getting into
        # an inconsistent state.
        #pylint: disable=no-member
        charge_item = self.line_items[linenum]
        invoiced_item = charge_item.invoiced
        if refunded_amount is None:
            refunded_amount = invoiced_item.dest_amount
        invoiced_broker_fee = charge_item.invoiced_broker_fee
        refunded_broker_fee_amount = 0
        if invoiced_broker_fee:
            # XXX partial refunds with refunded_amount
            refunded_broker_fee_amount = invoiced_broker_fee.orig_amount

        balances = sum_orig_amount(charge_item.refunded)
        if len(balances) > 1:
            raise ValueError(_("balances with multiple currency units (%s)") %
                str(balances))
        # `sum_orig_amount` guarentees at least one result.
        previously_refunded = balances[0]['amount']
        refund_available = max(
            invoiced_item.dest_amount - previously_refunded, 0)
        if refunded_amount > refund_available:
            raise InsufficientFunds(_("Cannot refund %(refund_required)s"\
" while there is only %(refund_available)s available on the line item.")
% {'refund_available': humanize.as_money(refund_available, self.unit),
   'refund_required': humanize.as_money(refunded_amount, self.unit)})

        broker = get_broker()
        charge_available_amount, provider_unit, \
            charge_processor_fee_amount, processor_unit, \
            charge_broker_fee_amount, broker_unit \
            = self.processor_backend.charge_distribution(
                self, broker, refunded=previously_refunded)

        # We execute the refund on the processor backend here such that
        # the following call to ``processor_backend.charge_distribution``
        # returns the correct ``corrected_available_amount`` and
        # ``corrected_processor_fee_amount``.
        self.processor_backend.refund_charge(
            self, refunded_amount, refunded_broker_fee_amount)

        corrected_available_amount, provider_unit, \
            corrected_processor_fee_amount, processor_unit, \
            corrected_broker_fee_amount, broker_unit \
            = self.processor_backend.charge_distribution(
                self, broker, refunded=previously_refunded + refunded_amount)

        charge_item.create_refund_transactions(
            refunded_amount,
            Price(charge_available_amount, provider_unit),
            Price(charge_processor_fee_amount, processor_unit),
            Price(charge_broker_fee_amount, broker_unit),
            Price(corrected_available_amount, provider_unit),
            Price(corrected_processor_fee_amount, processor_unit),
            Price(corrected_broker_fee_amount, broker_unit),
            created_at=created_at)
        username = str(user) if user is not None else '-'
        LOGGER.info("%s refunds %d %s on line item %d of charge %s to %s.",
            username, refunded_amount, self.unit, linenum, self, self.customer,
            extra={'event': 'refund', 'username': username,
                'customer': self.customer.slug,
                'charge': self.processor_key, 'linenum': linenum,
                'amount': refunded_amount, 'unit': self.unit})
        signals.charge_updated.send(sender=__name__, charge=self, user=user)

    def retrieve(self):
        """
        Retrieve the state of charge from the processor.
        """
        if self.processor_key:
            self.processor_backend.retrieve_charge(self, get_broker())
        return self


class ChargeItemManager(models.Manager):

    def to_sync(self, user):
        """
        Returns charges which have been paid and a 3rd party asked
        to be notified about.
        """
        results = self.filter(Q(sync_on__iexact=user.email) |
            # We don't do case-insensitive search here (i.e. `sync_on__in`)
            # because we assume the case for sync_on field and username/slug
            # are in sync here.
            Q(sync_on=user.username) |
            Q(sync_on__in=get_organization_model().objects.accessible_by(
                user).values('slug').distinct()),
            charge__state=Charge.DONE, invoice_key__isnull=False)
        return results


@python_2_unicode_compatible
class ChargeItem(models.Model):
    """
    Keep track of each item invoiced within a ``Charge``.

    The pair (invoice_key, sync_on) is used by 3rd party services that
    need to synchronize their own database on the status of a charge been paid.
    The ``invoice_key`` is created by the 3rd party service and stored at the
    time the charge is created. When a ``User`` affiliated to the ``sync_on``
    account logs in, notification of the charge status are generated.
    """
    objects = ChargeItemManager()

    charge = models.ForeignKey(Charge, on_delete=models.PROTECT,
        related_name='charge_items')
    # XXX could be a ``Subscription`` or a balance.
    invoiced = models.ForeignKey('Transaction', on_delete=models.PROTECT,
        related_name='invoiced_item',
        help_text=_("Transaction invoiced through this charge"))
    invoiced_processor_fee = models.ForeignKey('Transaction', null=True,
        on_delete=models.PROTECT,
        related_name='invoiced_processor_fee_item',
        help_text=_("Fee transaction to processor in order to process"\
            " the transaction invoiced through this charge"))
    invoiced_broker_fee = models.ForeignKey('Transaction', null=True,
        on_delete=models.PROTECT,
        related_name='invoiced_broker_fee_item',
        help_text=_("Fee transaction to broker in order to process"\
            " the transaction invoiced through this charge"))
    invoiced_distribute = models.ForeignKey('Transaction', null=True,
        on_delete=models.PROTECT,
        related_name='invoiced_distribute',
        help_text=_("Transaction recording the distribution from processor"\
" to provider."))

    # 3rd party notification
    invoice_key = models.SlugField(db_index=True, null=True, blank=True)
    sync_on = models.CharField(max_length=255, null=True)

    class Meta:
        unique_together = ('charge', 'invoiced')

    def __str__(self):
        return '%s-%s' % (str(self.charge), str(self.invoiced))

    @property
    def available_amount(self):
        """
        Returns the total amount and unit charged after refunds
        have been deducted.
        """
        invoiced_amount = self.invoiced.dest_amount
        refund_balances = sum_orig_amount(self.refunded)
        if len(refund_balances) > 1:
            raise ValueError(
                _("balances with multiple currency units (%s)") %
                str(refund_balances))
        # `sum_dest_amount` guarentees at least one result.
        refund_amount = refund_balances[0]['amount']
        refund_unit = refund_balances[0]['unit']
        if refund_amount and self.invoiced.dest_unit != refund_unit:
            raise ValueError(
                _("charge item and refunds have different units"\
" (%(unit)s vs. %(refund_unit)s)") % (
                {'unit': self.invoiced.dest_unit, 'refund_unit': refund_unit}))
        return invoiced_amount - refund_amount


    @property
    def refunded(self):
        """
        All ``Transaction`` which are part of a refund for this ``ChargeItem``.
        """
        return Transaction.objects.filter(
            event_id=get_charge_event_id(self.charge, self),
            orig_account=Transaction.REFUNDED)

    @property
    def subscription(self):
        """
        Returns the `Subscription` object associated to the `ChargeItem`
        or `None` if it could not be deduced from the `invoiced.event_id`.
        """
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_subscription'):
            self._subscription = Subscription.objects.get_by_event_id(
                self.invoiced.event_id)
            if not self._subscription:
                coupon = Coupon.objects.get_by_event_id(self.invoiced.event_id)
                if coupon:
                    organization_model = get_organization_model()
                    self._subscription = Subscription.objects.new_instance(
                        organization_model(email=self.sync_on), coupon.plan)
        return self._subscription


    def create_refund_transactions(self, refunded_amount,
        charge_available, charge_processor_fee, charge_broker_fee,
        corrected_available, corrected_processor_fee, corrected_broker_fee,
        created_at=None, refund_type=None):
        """
        Each ``ChargeItem`` can be partially refunded::

            yyyy/mm/dd cha_*****_*** refund to subscriber
                provider:Refund                          refunded_amount
                subscriber:Refunded

            yyyy/mm/dd cha_*****_*** refund of processor fee
                processor:Refund                         processor_fee
                processor:Funds

            yyyy/mm/dd cha_*****_*** refund of broker fee
                processor:Refund                         broker_fee
                broker:Funds

            yyyy/mm/dd cha_*****_*** cancel distribution
                processor:Refund                         distribute_amount
                provider:Funds

        ``Refund`` is replaced by ``Chargeback`` if the refund was initiated
        by a chargeback event.

        Example::

            2014/09/10 Charge ch_ABC123 refund for subscribe to open-space plan
                cowork:Refund                            $179.99
                xia:Refunded

            2014/09/10 Charge ch_ABC123 refund processor fee
                stripe:Refund                              $5.22
                stripe:Funds

            2014/09/10 Charge ch_ABC123 refund broker fee
                stripe:Refund                             $17.99
                broker:Funds

            2014/09/10 Charge ch_ABC123 cancel distribution
                stripe:Refund                            $156.78
                cowork:Funds
        """
        #pylint:disable=too-many-locals,too-many-arguments,too-many-statements
        #pylint:disable=no-member
        created_at = datetime_or_now(created_at)
        if not refund_type:
            refund_type = Transaction.REFUND

        charge_available_amount = charge_available.amount
        charge_processor_fee_amount = charge_processor_fee.amount
        charge_broker_fee_amount = charge_broker_fee.amount
        provider_unit = charge_available.unit
        processor_unit = charge_processor_fee.unit
        broker_unit = charge_broker_fee.unit

        corrected_available_amount = corrected_available.amount
        corrected_processor_fee_amount = corrected_processor_fee.amount
        corrected_broker_fee_amount = corrected_broker_fee.amount

        charge = self.charge
        processor = charge.processor
        invoiced_item = self.invoiced
        broker = get_broker()
        provider = invoiced_item.orig_organization
        customer = invoiced_item.dest_organization

        invoiced_processor_fee = self.invoiced_processor_fee
        refunded_processor_fee_amount = 0
        if invoiced_processor_fee:
            refunded_processor_fee_amount = min(
                charge_processor_fee_amount - corrected_processor_fee_amount,
                invoiced_processor_fee.orig_amount)

        invoiced_broker_fee = self.invoiced_broker_fee
        refunded_broker_fee_amount = 0
        if invoiced_broker_fee:
            refunded_broker_fee_amount = min(
                charge_broker_fee_amount - corrected_broker_fee_amount,
                invoiced_broker_fee.orig_amount)

        invoiced_distribute = self.invoiced_distribute
        refunded_distribute_amount = \
            charge_available_amount - corrected_available_amount
        if invoiced_distribute:
            orig_distribute = "%d %s" % (invoiced_distribute.dest_amount,
                invoiced_distribute.dest_unit)
            refunded_distribute_amount = min(refunded_distribute_amount,
                invoiced_distribute.dest_amount)
        else:
            orig_distribute = 'N/A'
        # Implementation Note:
        # refunded_amount = (refunded_distribute_amount
        #     + refunded_processor_fee_amount + refunded_broker_fee_amount)
        LOGGER.debug(
            "create_refund_transactions(charge=%s, refund_amount=%d %s)"\
            " distribute: %d %s,"\
            " broker fee: %d %s,"\
            " processor fee: %d %s out of total"\
            " distribute: %d %s, "\
            " orig_distribute: %s",
            charge.processor_key, refunded_amount, charge.unit,
            refunded_distribute_amount, provider_unit,
            refunded_broker_fee_amount, broker_unit,
            refunded_processor_fee_amount, processor_unit,
            charge_available_amount, provider_unit,
            orig_distribute)

        if refunded_distribute_amount > provider.funds_balance:
            raise InsufficientFunds(
                _("%(provider)s has %(funds_available)s of funds available."\
" %(funds_required)s are required to refund '%(descr)s'") % {
    'provider': provider,
    'funds_available': humanize.as_money(provider.funds_balance, provider_unit),
    'funds_required': humanize.as_money(
        refunded_distribute_amount, provider_unit),
    'descr': invoiced_item.descr})

        dest_refunded_amount = (
            refunded_distribute_amount + refunded_processor_fee_amount
            + refunded_broker_fee_amount)

        with transaction.atomic():
            # Record the refund from provider to subscriber
            descr = humanize.DESCRIBE_CHARGED_CARD_REFUND % {
                'charge': charge.processor_key,
                'refund_type': refund_type.lower(),
                'descr': invoiced_item.descr}
            Transaction.objects.create(
                event_id=get_charge_event_id(self.charge, self),
                descr=descr,
                created_at=created_at,
                dest_unit=provider_unit,
                dest_amount=dest_refunded_amount,
                dest_account=refund_type,
                dest_organization=provider,
                orig_unit=charge.unit,
                orig_amount=refunded_amount,
                orig_account=Transaction.REFUNDED,
                orig_organization=customer)

            if invoiced_processor_fee:
                # Refund the processor fee (if exists)
                Transaction.objects.create(
                    event_id=get_charge_event_id(self.charge, self),
                    # The Charge id is already included in the description here.
                    descr=invoiced_processor_fee.descr.replace(
                        'processor fee', 'refund processor fee'),
                    created_at=created_at,
                    dest_unit=processor_unit,
                    dest_amount=refunded_processor_fee_amount,
                    dest_account=refund_type,
                    dest_organization=processor,
                    orig_unit=processor_unit,
                    orig_amount=refunded_processor_fee_amount,
                    orig_account=Transaction.FUNDS,
                    orig_organization=processor)
                processor.funds_balance -= refunded_processor_fee_amount
                processor.save()

            if invoiced_broker_fee:
                # Refund the processor fee (if exists)
                Transaction.objects.create(
                    event_id=get_charge_event_id(self.charge, self),
                    # The Charge id is already included in the description here.
                    descr=invoiced_broker_fee.descr.replace(
                        'broker fee', 'refund broker fee'),
                    created_at=created_at,
                    dest_unit=processor_unit,
                    dest_amount=refunded_broker_fee_amount,
                    dest_account=refund_type,
                    dest_organization=processor,
                    orig_unit=processor_unit,
                    orig_amount=refunded_broker_fee_amount,
                    orig_account=Transaction.FUNDS,
                    orig_organization=broker)
                broker.funds_balance -= refunded_broker_fee_amount
                broker.save()

            # cancel payment to provider
            Transaction.objects.create(
                event_id=get_charge_event_id(self.charge, self),
                descr=descr,
                created_at=created_at,
                dest_unit=processor_unit,
                dest_amount=refunded_distribute_amount,
                dest_account=refund_type,
                dest_organization=processor,
                orig_unit=provider_unit,
                orig_amount=refunded_distribute_amount,
                orig_account=Transaction.FUNDS,
                orig_organization=provider)
            provider.funds_balance -= refunded_distribute_amount
            provider.save()


class PlanManager(models.Manager):

    def as_buy_periods(self, descr):
        """
        Returns a triplet (plan, ends_at, nb_periods) from a string
        formatted with DESCRIBE_BUY_PERIODS.
        """
        plan = None
        nb_periods = 0
        ends_at = datetime_or_now()
        look = re.match(humanize.DESCRIBE_BUY_PERIODS % {
                'plan': r'(?P<plan>\S+)',
                'ends_at': r'(?P<ends_at>\d\d\d\d/\d\d/\d\d)',
                'humanized_periods': r'(?P<nb_periods>\d+).*'}, descr)
        if look:
            try:
                plan = self.get(slug=look.group('plan'))
            except Plan.DoesNotExist:
                plan = None
            ends_at = datetime_or_now(datetime.datetime.strptime(
                look.group('ends_at'), '%Y/%m/%d'))
            nb_periods = int(look.group('nb_periods'))
        return (plan, ends_at, nb_periods)

    @staticmethod
    def provider(plans):
        """
        If all plans are from the same provider, return it otherwise
        return the site broker.
        """
        result = None
        for plan in plans:
            if not result:
                result = plan.organization
            elif result != plan.organization:
                result = get_broker()
                break
        if not result:
            result = get_broker()
        return result


@python_2_unicode_compatible
class Plan(SlugTitleMixin, models.Model):
    """
    Recurring billing plan.

    The ``slug`` field is used as a unique identifier for the ``Plan`` when
    interacting with the external World (i.e. URLs). The ``title`` and
    ``description`` fields are human-readable information about the ``Plan``.

    By default, any organization can subscribe to a plan through the checkout
    pipeline. In cases where a manager of the provider must approve
    the subscription before the subscriber can continue, ``optin_on_request``
    should be set to ``True``. Reciprocally when a provider's manager initiates
    the subscription of an organization to one of the provider's plan,
    the subscription, it is effective immediately when ``skip_optin_on_grant``
    is ``True``, otherwise the subscription is effective only
    after the subscriber explicitely accepts the grant.
    """
    objects = PlanManager()

    UNSPECIFIED = 0
    HOURLY = humanize.HOURLY
    DAILY = humanize.DAILY
    WEEKLY = humanize.WEEKLY
    MONTHLY = humanize.MONTHLY
    YEARLY = humanize.YEARLY

    INTERVAL_CHOICES = [
        (HOURLY, "HOURLY"),
        (DAILY, "DAILY"),
        (WEEKLY, "WEEKLY"),
        (MONTHLY, "MONTHLY"),
        (YEARLY, "YEARLY"),
        ]

    ONE_TIME = 0
    AUTO_RENEW = 1
    REPEAT = 2

    RENEWAL_CHOICES = [
        (ONE_TIME, "ONE-TIME"),
        (AUTO_RENEW, "AUTO-RENEW"),
        (REPEAT, "REPEAT")]

    PRICE_ROUND_NONE = 0
    PRICE_ROUND_WHOLE = 1
    PRICE_ROUND_99 = 2

    slug = models.SlugField(unique=True,
        help_text=_("Unique identifier shown in the URL bar"))
    title = models.CharField(max_length=50, null=True,
        help_text=_("Short description of the plan"))
    description = models.TextField(
        help_text=_("Long description of the plan"))
    is_active = models.BooleanField(default=False,
        help_text=_("True when a profile can subscribe to the plan"))
    is_not_priced = models.BooleanField(default=False,
        help_text=_("True if the plan has no pricing (i.e. contact us)"))
    is_personal = models.BooleanField(default=False,
        help_text=_("True when the plan is meant for personal profiles"\
        " first and foremost"))
    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time of creation (in ISO format)"))
    discontinued_at = models.DateTimeField(null=True, blank=True,
        help_text=_("Date/time the plan was discountinued (in ISO format)"))
    organization = models.ForeignKey(settings.ORGANIZATION_MODEL,
        on_delete=models.CASCADE, related_name='plans',
        help_text=_("Profile the plan belongs to"))
    unit = models.CharField(max_length=3, default=settings.DEFAULT_UNIT,
        help_text=_("Three-letter ISO 4217 code for currency unit (ex: usd)"))
    # on creation of a subscription
    skip_optin_on_grant = models.BooleanField(default=False,
        help_text=_("True requires a subscriber to accept the subscription"\
        " when created by the provider"))
    optin_on_request = models.BooleanField(default=False,
        help_text=_("True requires a provider to accept the subscription"\
        " when created by the subscriber"))
    setup_amount = models.PositiveIntegerField(default=0,
        help_text=_("One-time charge amount in currency unit"))
    # period billing
    period_amount = models.PositiveIntegerField(default=0,
        help_text=_("Recurring amount per period in currency unit"))
    period_type = models.PositiveSmallIntegerField(
        choices=INTERVAL_CHOICES, default=YEARLY,
        help_text=_("Natural period length of a subscription to the plan"\
        " (hourly, daily, weekly, monthly, yearly)"))
    period_length = models.PositiveSmallIntegerField(default=1,
        help_text=_("Number of periods for a subscription to the plan"\
        " (defaults to 1)"))
    broker_fee_percent = models.PositiveIntegerField(
        default=settings.BROKER_FEE_PERCENTAGE,
        help_text=_("Broker fee per transaction (in per 10000)."))

    unlock_event = models.CharField(max_length=128, null=True, blank=True,
        help_text=_("Payment required to access full service"))
    # end game
    length = models.PositiveSmallIntegerField(null=True, blank=True,
        help_text=_("Number of natural periods before a subscription to"\
        " the plan ends (default to 1)"))
    renewal_type = models.PositiveSmallIntegerField(
        choices=RENEWAL_CHOICES, default=AUTO_RENEW,
        help_text=_("What happens at the end of a subscription period"\
        " (one-time, auto-renew, repeat)"))
    # Pb with next : maybe create an other model for it
    next_plan = models.ForeignKey("Plan", null=True, on_delete=models.CASCADE,
        blank=True)
    extra = get_extra_field_class()(null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    class Meta:
        unique_together = ('slug', 'organization')

    def __str__(self):
        return str(self.slug)

    @property
    def natural_period(self):
        return self.get_natural_period(1, self.period_type)

    @property
    def period_price(self):
        return Price(self.period_amount, self.unit)

    @property
    def setup_price(self):
        return Price(self.setup_amount, self.unit)

    def get_discounted_period_amount(self, coupon):
        return self.period_amount - coupon.get_discount_amount(
            period_amount=self.period_amount)

    def get_discounted_period_price(self, coupon):
        return Price(self.get_discounted_period_amount(coupon), self.unit)

    @staticmethod
    def get_natural_period(nb_periods, period_type):
        result = None
        if period_type == Plan.HOURLY:
            result = relativedelta(hours=1 * nb_periods)
        elif period_type == Plan.DAILY:
            result = relativedelta(days=1 * nb_periods)
        elif period_type == Plan.WEEKLY:
            result = relativedelta(days=7 * nb_periods)
        elif period_type == Plan.MONTHLY:
            result = relativedelta(months=1 * nb_periods)
        elif period_type == Plan.YEARLY:
            result = relativedelta(years=1 * nb_periods)
        return result

    def end_of_period(self, start_time, nb_periods=1, period_type=None):
        result = start_time
        if nb_periods:
            # In case of a ``SETTLED``, *nb_periods* will be ``None``
            # since the description does not (should not) allow us to
            # extend the subscription length.
            if not period_type:
                period_type = self.period_type
            natural = self.get_natural_period(nb_periods, period_type)
            if natural:
                result += natural
        return result

    @property
    def printable_name(self):
        """
        Returns a printable human-readable title for the plan.
        """
        if self.title:
            return self.title
        return self.slug

    def period_number(self, text):
        """
        This method is the reverse of ``humanize_period``. It will extract
        a number of periods from a text.
        """
        result = None
        if self.period_type == self.HOURLY:
            pat = r'(\d+)(\s|-)hour'
        elif self.period_type == self.DAILY:
            pat = r'(\d+)(\s|-)day'
        elif self.period_type == self.WEEKLY:
            pat = r'(\d+)(\s|-)week'
        elif self.period_type == self.MONTHLY:
            pat = r'(\d+)(\s|-)month'
        elif self.period_type == self.YEARLY:
            pat = r'(\d+)(\s|-)year'
        else:
            raise ValueError(_("period type %d is not defined.")
                % self.period_type)
        look = re.search(pat, text)
        if look:
            try:
                result = int(look.group(1))
            except ValueError:
                pass
        return result

    def prorate_transaction(self, amount):
        """
        Hosting service paid through a transaction fee.
        """
        # integer division
        return (amount * self.broker_fee_percent) // 10000

    def prorate_period(self, start_time, end_time):
        """
        Return the pro-rate recurring amount for a period
        [start_time, end_time[.

        If end_time - start_time >= interval period, the value
        returned is undefined.
        """
        if self.period_type == self.HOURLY:
            # Hourly: fractional period is in minutes.
            # XXX integer division?
            fraction = (end_time - start_time).seconds // 3600
        elif self.period_type == self.DAILY:
            # Daily: fractional period is in hours.
            # XXX integer division?
            fraction = ((end_time - start_time).seconds // (3600 * 24))
        elif self.period_type == self.WEEKLY:
            # Weekly, fractional period is in days.
            # XXX integer division?
            fraction = (end_time.date() - start_time.date()).days // 7
        elif self.period_type == self.MONTHLY:
            # Monthly: fractional period is in days.
            # We divide by the maximum number of days in a month to
            # the advantage of a customer.
            # XXX integer division?
            fraction = (end_time.date() - start_time.date()).days // 31
        elif self.period_type == self.YEARLY:
            # Yearly: fractional period is in days.
            # We divide by the maximum number of days in a year to
            # the advantage of a customer.
            # XXX integer division?
            fraction = (end_time.date() - start_time.date()).days // 366
        # Round down to the advantage of a customer.
        return int(self.period_amount * fraction)


@receiver(post_save, sender=Plan)
def on_plan_post_save(sender, instance, created, raw, **kwargs):
    #pylint:disable=unused-argument
    if not raw:
        if created:
            signals.plan_created.send(sender=sender, plan=instance)
        else:
            signals.plan_updated.send(sender=sender, plan=instance)


@python_2_unicode_compatible
class AdvanceDiscount(models.Model):
    """
    Discounts for advance payments
    """
    UNSPECIFIED = 0
    PERCENTAGE = humanize.DISCOUNT_PERCENTAGE
    CURRENCY = humanize.DISCOUNT_CURRENCY
    PERIOD = humanize.DISCOUNT_PERIOD

    DISCOUNT_CHOICES = [
        (PERCENTAGE, "Percentage"),
        (CURRENCY, "Currency"),
        (PERIOD, "Period")]

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE,
        related_name='advance_discounts')
    discount_type = models.PositiveSmallIntegerField(
        choices=DISCOUNT_CHOICES, default=PERCENTAGE)
    discount_value = models.PositiveIntegerField(default=0,
        help_text=_('Amount of the discount'))
    length = models.PositiveSmallIntegerField(default=1,
      help_text=_("Contract length associated with the period (defaults to 1)"))

    def __str__(self):
        return "%s-%s-%d" % (self.plan, slugify(
            self.DISCOUNT_CHOICES[self.discount_type - 1][1]),
            int(self.discount_value))

    @property
    def full_periods_amount(self):
        """
        Returns the full amount for the length of the subscription
        when no discount is applied.
        """
        assert self.length > 0
        nb_periods = self.length
        return self.plan.period_amount * nb_periods

    def get_discount_amount(self, prorated_amount=0,
            rounding=Plan.PRICE_ROUND_WHOLE):
        if self.discount_type == self.CURRENCY:
            return self.discount_value
        if self.discount_type == self.PERIOD:
            return self.plan.period_amount * self.discount_value
        # discount percentage
        full_amount = prorated_amount + self.full_periods_amount
        discount_percent = self.discount_value
        discount_amount = (full_amount * discount_percent) // 10000
        if rounding == Plan.PRICE_ROUND_WHOLE:
            if (full_amount - discount_amount) % 100:
                discount_amount += (full_amount - discount_amount) % 100
        elif rounding == Plan.PRICE_ROUND_99:
            if (full_amount - discount_amount - 99) % 100:
                discount_amount += (full_amount - discount_amount - 99) % 100
        return discount_amount


class CouponManager(models.Manager):

    def active(self, organization, code, plan=None, at_time=None):
        at_time = datetime_or_now(at_time)
        filter_args = Q(ends_at__isnull=True) | Q(ends_at__gt=at_time)
        if plan:
            filter_args |= Q(plan__isnull=True) | Q(plan=plan)
        return self.filter(filter_args,
            code__iexact=code, # case incensitive search.
            organization=organization)

    def get_by_event_id(self, event_id):
        """
        Returns a `Coupon` based on a `Transaction.event_id` key.
        """
        if not event_id:
            return None
        look = re.match(r'^cpn_(\S+)', event_id)
        if not look:
            return None
        try:
            return self.get(code=event_id)
        except Coupon.DoesNotExist:
            pass
        return None


@python_2_unicode_compatible
class Coupon(models.Model):
    """
    Coupons are used on invoiced to give a rebate to a customer.
    """
    UNSPECIFIED = 0
    PERCENTAGE = humanize.DISCOUNT_PERCENTAGE
    CURRENCY = humanize.DISCOUNT_CURRENCY
    PERIOD = humanize.DISCOUNT_PERIOD

    DISCOUNT_CHOICES = [
        (PERCENTAGE, "percentage"),
        (CURRENCY, "currency"),
        (PERIOD, "period")]

    objects = CouponManager()

    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time of creation (in ISO format)"))
    code = models.SlugField(
        help_text=_("Unique identifier per provider, typically used in URLs"))
    description = models.TextField(null=True, blank=True,
        help_text=_("Free-form text description for the %(object)s") % {
            'object': 'coupon'})
    discount_type = models.PositiveSmallIntegerField(
        choices=DISCOUNT_CHOICES, default=PERCENTAGE)
    discount_value = models.PositiveIntegerField(default=0,
        help_text=_('Amount of the discount'))
    # restrict use in scope
    organization = models.ForeignKey(settings.ORGANIZATION_MODEL, on_delete=models.CASCADE,
        help_text=_("Coupon will only apply to purchased plans"\
            " from this provider"))
    plan = models.ForeignKey('saas.Plan', on_delete=models.CASCADE, null=True,
        blank=True, help_text=_("Coupon will only apply to this plan"))
    # restrict use in time and count.
    ends_at = models.DateTimeField(null=True, blank=True,
        help_text=_("Date/time at which the coupon code expires"\
        " (in ISO format)"))
    nb_attempts = models.IntegerField(null=True, blank=True,
        help_text=_("Number of times the coupon can be used"))
    extra = get_extra_field_class()(null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    class Meta:
        unique_together = ('organization', 'code')

    def __str__(self):
        return '%s-%s' % (self.organization, self.code)

    @property
    def provider(self):
        return self.organization

    def get_discount_amount(self, prorated_amount=0, period_amount=0,
                            advance_amount=0, rounding=Plan.PRICE_ROUND_NONE):
        if self.discount_type == self.CURRENCY:
            return self.discount_value
        # discount percentage
        full_amount = prorated_amount + period_amount + advance_amount
        discount_percent = self.discount_value
        discount_amount = (full_amount * discount_percent) // 10000
        if rounding == Plan.PRICE_ROUND_WHOLE:
            if (full_amount - discount_amount) % 100:
                discount_amount += (full_amount - discount_amount) % 100
        elif rounding == Plan.PRICE_ROUND_99:
            if (full_amount - discount_amount - 99) % 100:
                discount_amount += (full_amount - discount_amount - 99) % 100
        return discount_amount

    def is_valid(self, plan, at_time=None):
        """
        Returns ``True`` if the ``Coupon`` can sucessfuly be applied
        to purchase this plan.
        """
        at_time = datetime_or_now(at_time)
        valid_plan = (not self.plan or self.plan == plan)
        valid_time = (not self.ends_at or at_time < self.ends_at)
        valid_attempts = (self.nb_attempts is None or self.nb_attempts > 0)
        valid_organization = (self.organization == plan.organization)
        return (valid_plan and valid_time and valid_attempts
            and valid_organization)

    def save(self, *args, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.created_at:
            self.created_at = datetime_or_now()
        # Implementation Note:
        # We want ``ends_at`` on a newly created ``Coupon`` to defaults
        # to an expiration date, yet we want to force an update on the Coupon
        # to enable a "never" expiration date. We can't enable both semantics
        # through ``ends_at == None``, so the serializer ``perform_update``
        # explicitely set ends_at to 'never' (not a datetime instance).
        if self.ends_at:
            if str(self.ends_at) == 'never':
                self.ends_at = None
        else:
            # Coupon expires in 30 days by default.
            self.ends_at = self.created_at + datetime.timedelta(days=30)

        super(Coupon, self).save(force_insert=force_insert,
             force_update=force_update, using=using,
             update_fields=update_fields)


@python_2_unicode_compatible
class UseCharge(SlugTitleMixin, models.Model):
    """
    Additional use charges on a ``Plan``.
    """

    slug = models.SlugField(unique=True,
        help_text=_("Unique identifier shown in the URL bar"))
    title = models.CharField(max_length=50, null=True,
        help_text=_("Short description of the use charge"))
    description = models.TextField(
        help_text=_("Long description of the use charge"))
    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time of creation (in ISO format)"))
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE,
        related_name='use_charges',
        help_text=_("Plan the use chage is related to"))
    use_amount = models.PositiveIntegerField(default=0,
        help_text=_("Amount per unit defined by the provider"\
            " of the use charge in plan currency unit (ex: $0.01/request)"))
    quota = models.PositiveIntegerField(default=0,
        help_text=_("Usage included in the plan"\
            " (in units defined by the provider)"))
    maximum_limit = models.PositiveIntegerField(default=0, null=True,
        help_text=_("Maximum spend limit per period above which"\
            " the subscriber is notified (in currency unit)"))
    extra = get_extra_field_class()(null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    class Meta:
        unique_together = ('slug', 'plan')

    def __str__(self):
        return str(self.slug)

    @property
    def use_price(self):
        return Price(self.use_amount, self.plan.unit)


class CartItemManager(models.Manager):

    def get_cart(self, user, *args, **kwargs):
        # Order by plan then id so the order is consistent between
        # billing/cart(-.*)/ pages.
        return self.filter(user=user, recorded=False,
            *args, **kwargs).order_by('plan', 'sync_on', 'id')

    def get_personal_cart(self, user):
        return self.get_cart(user).filter(plan__is_personal=True)

    def by_claim_code(self, claim_code, *args, **kwargs):
        # Order by plan then id so the order is consistent between
        # billing/cart(-.*)/ pages.
        return self.filter(claim_code=claim_code, recorded=False,
            user__isnull=True, *args, **kwargs).order_by('plan', 'id')

    @staticmethod
    def provider(cart_items):
        return Plan.objects.provider(
            [cart_item.plan for cart_item in cart_items])

    def redeem(self, user, coupon_code, created_at=None):
        """
        Apply a *coupon* to all items in a cart that accept it.
        """
        at_time = datetime_or_now(created_at)
        coupon_applied = False
        for item in self.get_cart(user):
            redeemed = Coupon.objects.active(
                item.plan.organization, coupon_code, at_time=at_time).first()
            if redeemed and redeemed.is_valid(item.plan, at_time=at_time):
                coupon_applied = True
                item.coupon = redeemed
                item.save()
        if coupon_applied:
            if redeemed.nb_attempts is not None and redeemed.nb_attempts > 0:
                redeemed.nb_attempts -= 1
                redeemed.save()
        return coupon_applied


@python_2_unicode_compatible
class CartItem(models.Model):
    """
    A user (authenticated or anonymous) shops for plans by adding them
    to her cart. When placing an order, the user is presented with the billing
    account (``Organization``) those items apply to.

    Historical Note: The billing account was previously required at the time
    the item is added to the cart. The ``cart_items`` is the only extra state
    kept in the session, and kept solely for anonymous users. We do not store
    the billing account in the session. It is retrieved from the url. As a
    result the billing account (i.e. an ``Organization``) is set when an
    order is placed, not when the item is added to the cart.

    Another Historical Note: If we allow a user to buy more periods at
    a bargain price, then ('user', 'plan', 'sync_on') should not be unique
    together. There should only be one ``CartItem`` not yet recorded
    with ('user', 'plan', 'sync_on') unique together.
    """
    objects = CartItemManager()

    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time of creation (in ISO format)"))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
        on_delete=models.CASCADE,
        db_column='user_id', related_name='cart_items',
        help_text=_("User who added the item to the cart (``None`` means"\
" the item could be claimed)"))
    plan = models.ForeignKey(Plan, null=True,
        on_delete=models.CASCADE,
        help_text=_("Item in the cart (if plan)"))
    use = models.ForeignKey(UseCharge, null=True,
        on_delete=models.CASCADE,
        help_text=_("Item added to the cart (if use charge)"))
    coupon = models.ForeignKey(Coupon, null=True,
        on_delete=models.CASCADE,
        blank=True, help_text=_("Coupon to apply to the order"))
    recorded = models.BooleanField(default=False,
        help_text=_("Whever the item has been checked out or not"))

    # The following fields are for number of periods pre-paid in advance
    # or a quantity in UseCharge units.
    quantity = models.PositiveIntegerField(default=0,
        help_text=_("Number of periods to be paid in advance"))

    # The following field is an index for a selected option which can be
    # a number of prepaid periods in advance, a balance due payment, etc.
    # 0 means not selected yet. In order to retrieve the actual option,
    # the index is decremented and then used to access the element in
    # options list, which is usually generated by `get_balance_options()`
    # or `get_cart_options()`.
    option = models.PositiveIntegerField(default=0,
        help_text=_("Index in the list of discounts for advance payments"))

    # The following fields are used for the GroupBuy feature. They do not
    # refer to a User nor Organization key because those might not yet exist
    # at the time the CartItem is created.
    #
    # Items paid by user on behalf of a subscriber, that might or might not
    # already exist in the database, can be redeemed through a claim_code.
    # claim_code is also the field 3rd parties can use to store an invoice_key
    # that will be passed back on successful charge notifications.
    # `sync_on`` will be used for notifications. It needs to be a valid
    # User or Organization slug or an e-mail address.
    full_name = models.CharField(_('Full name'), max_length=150, blank=True,
        help_text=_("Full name of the person that will benefit from"\
            " the subscription (GroupBuy)"))
    email = models.CharField(max_length=255, null=True, blank=True,
        help_text=_("e-mail of the person that will benefit from"\
            " the subscription (GroupBuy)"))
    # XXX Explain sync_on and claim_code
    sync_on = models.CharField(max_length=255, null=True, blank=True,
        help_text=_("identifier of the person that will benefit from"\
            " the subscription (GroupBuy)"))
    claim_code = models.SlugField(db_index=True, null=True, blank=True,
        help_text=_("Code used to assign the cart item to a user in group buy"))

    def __str__(self):
        user_plan = '%s-%s' % (self.user, self.plan)
        return '%s-%s' % (user_plan, self.use) if self.use else user_plan

    @property
    def descr(self):
        result = '%s from %s' % (
            self.plan.printable_name, self.plan.organization.printable_name)
        if self.sync_on:
            full_name = self.full_name.strip()
            result = 'Subscribe %s (%s) to %s' % (full_name,
                self.sync_on, result)
        return result

    @property
    def name(self):
        result = 'cart-%s' % self.plan.slug
        if self.use:
            result = '%s-%s' % (result, self.use)
        if self.sync_on:
            result = '%s-%s' % (result, urlquote(self.sync_on))
        return result

    def merge_invoicable(self, cart_item):
        result = bool(self.plan == cart_item.plan)
        if self.sync_on and cart_item.sync_on:
            result = bool(result and self.sync_on == cart_item.sync_on)
        return result


class SubscriptionQuerySet(models.QuerySet):

    def active_with(self, provider, ends_at=None, **kwargs):
        """
        Returns a list of active subscriptions for which provider
        is the owner of the plan.
        """
        ends_at = datetime_or_now(ends_at)
        if isinstance(provider, get_organization_model()):
            return self.valid_for(
                plan__organization=provider, ends_at__gte=ends_at, **kwargs)
        return self.valid_for(
            plan__organization__slug=str(provider), ends_at__gte=ends_at,
            **kwargs)

    def valid_for(self, **kwargs):
        """
        Returns valid (i.e. fully opted-in) subscriptions.
        """
        return self.filter(grant_key=None, request_key=None, **kwargs)

    def unsubscribe(self, at_time=None):
        at_time = datetime_or_now(at_time)
        self.update(ends_at=at_time, auto_renew=False)


class SubscriptionManager(models.Manager):

    def get_queryset(self):
        return SubscriptionQuerySet(self.model, using=self._db)

    def active_at(self, at_time, **kwargs):
        return self.valid_for(
            created_at__lte=at_time, ends_at__gt=at_time, **kwargs)

    def active_for(self, organization, ends_at=None, **kwargs):
        """
        Returns active subscriptions for *organization*
        """
        ends_at = datetime_or_now(ends_at)
        if isinstance(organization, get_organization_model()):
            return self.valid_for(
                organization=organization, ends_at__gte=ends_at, **kwargs)
        return self.valid_for(
            organization__slug=str(organization), ends_at__gt=ends_at, **kwargs)

    def active_with(self, provider, ends_at=None, **kwargs):
        """
        Returns a list of active subscriptions for which provider
        is the owner of the plan.
        """
        return self.get_queryset().active_with(
            provider, ends_at=ends_at, **kwargs)

    def churn_in_period(self, start_period, end_period, **kwargs):
        return self.valid_for(
            ends_at__gte=start_period, ends_at__lt=end_period, **kwargs)

    def create(self, **kwargs):
        if 'ends_at' not in kwargs:
            created_at = datetime_or_now(kwargs.get('created_at', None))
            plan = kwargs.get('plan')
            return super(SubscriptionManager, self).create(
                ends_at=plan.end_of_period(created_at), **kwargs)
        return super(SubscriptionManager, self).create(**kwargs)

    def from_cart_item(self, cart_item, at_time=None):
        """
        Returns a candidate Subscription based on a cart_item.
        """
        if cart_item.sync_on:
            return self.get(
                Q(organization__slug=cart_item.sync_on)
                | Q(organization__email__iexact=cart_item.sync_on),
                plan=cart_item.plan,
                ends_at__gt=datetime_or_now(at_time))
        raise Subscription.DoesNotExist()

    def get_by_event_id(self, event_id):
        """
        Returns a `Subscription` based on a `Transaction.event_id` key.
        """
        if not event_id:
            return None
        look = re.match(r'^sub_(\d+)/', event_id)
        if not look:
            return None
        sub_id = int(look.group(1))
        if not sub_id:
            return None
        try:
            return self.get(pk=sub_id)
        except Subscription.DoesNotExist:
            pass
        return None

    def new_instance(self, organization, plan, ends_at=None):
        """
        New ``Subscription`` instance which is explicitely not in the db.
        """
        if ends_at is None:
            ends_at = plan.end_of_period(
                datetime_or_now(), nb_periods=plan.period_length)
        return Subscription(organization=organization, plan=plan,
            auto_renew=plan.renewal_type == plan.AUTO_RENEW, ends_at=ends_at)

    def valid_for(self, **kwargs):
        """
        Returns valid (i.e. fully opted-in) subscriptions.
        """
        return self.get_queryset().valid_for(**kwargs)


@python_2_unicode_compatible
class Subscription(models.Model):
    """
    ``Subscription`` represent a service contract (``Plan``) between
    two ``Organization``, a subscriber and a provider, that is paid
    by the subscriber to the provider over the lifetime of the subscription.

    When ``auto_renew`` is True, ``extend_subscriptions`` (usually called
    from a cron job) will invoice the organization for an additional period
    once the date reaches currenct end of subscription.

    Implementation Note:
    Even through (organization, plan) should be unique at any point in time,
    it is a little much to implement with PostgreSQL that for each
    (organization, plan), there should not be overlapping timeframe
    [created_at, ends_at[.
    """
    SEP = ':' # The separator must be a character which cannot be used in slugs.

    ACCEPTED = "ACCEPTED"
    DENIED = "DENIED"

    objects = SubscriptionManager()

    auto_renew = models.BooleanField(default=True,
        help_text=_("The subscription is set to auto-renew at the end of"\
        " the period"))
    created_at = models.DateTimeField(auto_now_add=True,
        help_text=_("Date/time of creation (in ISO format)"))
    ends_at = models.DateTimeField(
        help_text=_("Date/time when the subscription period currently ends"\
        " (in ISO format)"))
    description = models.TextField(null=True, blank=True,
        help_text=_("Free-form text description for the subscription"))
    organization = models.ForeignKey(settings.ORGANIZATION_MODEL,
        on_delete=models.CASCADE,
        help_text=_("Profile subscribed to the plan"),
        related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE,
        help_text=_("Plan the organization is subscribed to"))
    request_key = models.SlugField(max_length=40, null=True, blank=True,
        help_text=_("Unique key generated when a request is initiated"))
    grant_key = models.SlugField(max_length=40, null=True, blank=True,
        help_text=_("Unique key generated when a grant is initiated"))
    extra = get_extra_field_class()(null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    def __str__(self):
        return '%s%s%s' % (str(self.organization), Subscription.SEP,
            str(self.plan))

    @property
    def is_locked(self):
        Charge.objects.settle_customer_payments(self.organization)
        balance, _ = \
            Transaction.objects.get_subscription_statement_balance(self)
        return balance > 0

    @property
    def provider(self):
        return self.plan.organization

    def clipped_period_for(self, at_time=None, period_type=None):
        # Both lower and upper fall on an exact period multiple
        # from ``created_at``. This might not be the case for ``ends_at``.
        lower, upper = self.period_for(at_time=at_time, period_type=period_type)
        return (min(lower, self.ends_at), min(upper, self.ends_at))

    def period_for(self, at_time=None, period_type=None):
        """
        Returns the period [beg,end[ which includes ``at_time``.
        """
        if not period_type:
            period_type = self.plan.period_type
        at_time = datetime_or_now(at_time)
        delta = at_time - self.created_at
        if period_type == Plan.HOURLY:
            estimated = relativedelta(hours=delta.total_seconds() // 3600)
            period = relativedelta(hours=1)
        elif period_type == Plan.DAILY:
            estimated = relativedelta(days=delta.days)
            period = relativedelta(days=1)
        elif period_type == Plan.WEEKLY:
            # XXX integer division?
            estimated = relativedelta(days=delta.days // 7)
            period = relativedelta(days=7)
        elif period_type == Plan.MONTHLY:
            estimated = relativedelta(at_time, self.created_at)
            estimated.normalized()
            estimated = relativedelta(
                months=estimated.years * 12 + estimated.months)
            period = relativedelta(months=1)
        elif period_type == Plan.YEARLY:
            estimated = relativedelta(at_time, self.created_at)
            estimated.normalized()
            estimated = relativedelta(years=estimated.years)
            period = relativedelta(years=1)
        else:
            raise ValueError(_("period type %(period_type)d is not defined.")
                % {'period_type': period_type})
        lower = self.created_at + estimated # rough estimate to start
        upper = self.created_at + (estimated + period)
        while not (lower <= at_time and at_time < upper):
            if at_time < lower:
                upper = lower
                lower = lower - period
            elif at_time >= upper:
                lower = upper
                upper = upper + period
        return lower, upper

    def _period_fraction(self, start, until, start_lower, start_upper,
                         period_type=None):
        """
        Returns a [start, until[ interval as a fraction of the plan period.
        This method will not return the correct answer if [start, until[
        is longer than a plan period. Use ``nb_periods`` instead.
        """
        #pylint:disable=too-many-arguments
        if not period_type:
            period_type = self.plan.period_type
        delta = relativedelta(until, start)
        if period_type == Plan.HOURLY:
            fraction = (until - start).total_seconds() / 3600.0
        elif period_type == Plan.DAILY:
            fraction = delta.hours / 24.0
        elif period_type == Plan.WEEKLY:
            fraction = delta.days / 7.0
        elif period_type == Plan.MONTHLY:
            # The number of days in a month cannot be reliably computed
            # from [start_lower, start_upper[ if those bounds cross the 1st
            # of a month.
            fraction = ((until - start).total_seconds()
                / (start_upper - start_lower).total_seconds())
        elif period_type == Plan.YEARLY:
            fraction = delta.months / 12.0
        return fraction

    def nb_periods(self, start=None, until=None, period_type=None):
        """
        Returns the number of completed periods at datetime ``until``
        since the subscription was created.
        """
        #pylint:disable=too-many-locals
        if start is None:
            start = self.created_at
        if not period_type:
            period_type = self.plan.period_type
        until = datetime_or_now(until)
        assert start < until
        start_lower, start_upper = self.period_for(
            start, period_type=period_type)
        until_lower, until_upper = self.period_for(
            until, period_type=period_type)
        LOGGER.debug("[%s,%s[ starts in period [%s,%s[ and ends in period"\
" [%s,%s[", start, until, start_lower, start_upper, until_lower, until_upper)
        partial_start_period = 0
        partial_end_period = 0
        if start_upper <= until_lower:
            delta = relativedelta(until_lower, start_upper) # XXX inverted
            if period_type == Plan.HOURLY:
                # Integer division?
                estimated = (start_upper - until_lower).total_seconds() // 3600
            elif period_type == Plan.DAILY:
                estimated = (start_upper - until_lower).days
            elif period_type == Plan.WEEKLY:
                # Integer division?
                estimated = (start_upper - until_lower).days // 7
            elif period_type == Plan.MONTHLY:
                estimated = delta.years * 12 + delta.months
            elif period_type == Plan.YEARLY:
                estimated = delta.years
            upper = self.plan.end_of_period(
                start_upper, nb_periods=estimated, period_type=period_type)
            if upper < until_lower:
                full_periods = estimated + 1
            else:
                full_periods = estimated
            # partial-at-start + full periods + partial-at-end
            partial_start_period_seconds = (start_upper - start).total_seconds()
            if partial_start_period_seconds > 0:
                partial_start_period = self._period_fraction(
                    start, start_upper, start_lower, start_upper,
                    period_type=period_type)
            partial_end_period_seconds = (until - until_lower).total_seconds()
            if partial_end_period_seconds > 0:
                partial_end_period = self._period_fraction(
                    until_lower, until, until_lower, until_upper,
                    period_type=period_type)
        else:
            # misnommer. We are returning a fraction of a period here since
            # [start,until[ is fully included in a single period.
            full_periods = self._period_fraction(
                start, until, start_lower, start_upper,
                period_type=period_type)
        LOGGER.debug("[nb_periods] %s + %s + %s",
            partial_start_period, full_periods, partial_end_period)
        return partial_start_period + full_periods + partial_end_period

    def charge_in_progress(self):
        queryset = Charge.objects.in_progress_for_customer(self.organization)
        if queryset.exists():
            return queryset.first()
        return None

    def extends(self, nb_periods=1):
        """
        Extends a Subscription by a number of periods

        The Subscription might not have been recorded in the database yet
        """
        self.ends_at = self.plan.end_of_period(
            self.ends_at if self.ends_at else self.created_at, nb_periods)
        if self.pk is None and self.plan.optin_on_request:
            self.request_key = generate_random_slug()
        LOGGER.info(
            "extends subscription of %s to %s until %s",
            self.organization, self.plan,
            self.ends_at, extra={
                'event': 'upsert-subscription',
                'organization': self.organization.slug,
                'plan': self.plan.slug,
                'ends_at': self.ends_at})
        self.save()


    def save(self, *args, force_insert=False, force_update=False, using=None,
             update_fields=None):
        super(Subscription, self).save(force_insert=force_insert,
            force_update=force_update, using=using, update_fields=update_fields)
        if not self.organization.billing_start:
            # If we don't have an automatic invoicing schedule yet,
            # let's create one.
            self.organization.billing_start = (
                self.created_at + relativedelta(months=1))
            self.organization.save()


class SubscriptionUseManager(models.Manager):

    def get_by_event_id(self, event_id):
        """
        Returns a `SubscriptionUse` based on a `Transaction.event_id` key.
        """
        if not event_id:
            return None
        look = re.match(r'^sub_(\d+)/(\d+)/', event_id)
        if not look:
            return None
        sub_id = int(look.group(1))
        if not sub_id:
            return None
        try:
            use_id = int(look.group(2))
            return self.get(subscription__pk=sub_id, use__pk=use_id)
        except Subscription.DoesNotExist:
            pass
        return None


@python_2_unicode_compatible
class SubscriptionUse(models.Model):
    """
    Tracks ``UseCharge`` on a ``Subscription``
    """
    objects = SubscriptionUseManager()

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE,
        help_text=_("Subscription usage is added to"), related_name='uses')
    use = models.ForeignKey(UseCharge, on_delete=models.CASCADE,
        help_text=_("UseCharge refered to"))
    expiring_quota = models.PositiveIntegerField(default=0,
        help_text=_("Number of use events that expire at the end of the current period"))
    rollover_quota = models.PositiveIntegerField(default=0,
        help_text=_("Number of use events that rollover to the next period"))
    used_quantity = models.PositiveIntegerField(default=0,
        help_text=_("Number of use events generated over the life"\
        " of the subscription"))
    extra = get_extra_field_class()(null=True,
        help_text=_("Extra meta data (can be stringify JSON)"))

    def __str__(self):
        return '%s%s%s' % (str(self.subscription), Subscription.SEP,
            str(self.use))

    def extends(self):
        """
        Extends a SubscriptionUse by one period will replentish the quota
        for the period.
        """
        self.expiring_quota = self.use.quota
        self.save()

    @property
    def provider(self):
        return self.subscription.provider


class TransactionQuerySet(models.QuerySet):
    """
    Custom ``QuerySet`` for ``Transaction`` that provides useful queries.
    """

    def get_statement_balances(self, organization, until=None):
        """
        Returns a dictionnary keyed by event_id of dictionnaries keyed by
        currency unit.

        Example:

            {
                'sub_4/': {'usd': 0},
                'sub_437/': {'usd': 3490}
            }

        Note that the event_id can be `None` if a one-time charge was created,
        and it wasn't associated to a specific subscription.

        Example:

            {
                'sub_437/': {'usd': 3490},
                None:  {'usd': 2500}
            }
        """
        #pylint:disable=too-many-locals
        until = datetime_or_now(until)
        # We use the fact that all orders (and only orders) will have
        # a destination of `subscriber:Payable`.
        dest_balances = self.filter(
            Q(dest_account=Transaction.PAYABLE),
            dest_organization=organization,
            created_at__lt=until).values(
                'event_id', 'dest_unit').annotate(
                dest_balance=Sum('dest_amount'),
                last_activity_at=Max('created_at')).order_by(
                    'last_activity_at')
        dest_balance_per_events = {}
        for dest_balance in dest_balances:
            event_id = dest_balance['event_id']
            if event_id not in dest_balance_per_events:
                dest_balance_per_events.update({event_id: {}})
            dest_balance_per_events[event_id].update({
                dest_balance['dest_unit']: dest_balance['dest_balance']})

        # If the subscription is extended by a group buyer, `dest_organization`
        # will be the group buyer, not the final subscriber. On the other hand
        # `orig_balances` (BACKLOG to RECEIVABLE) references the provider.
        groupbuy_dest_balances = self.filter(
            Q(dest_account=Transaction.PAYABLE),
            event_id__in=dest_balance_per_events.keys(),
            created_at__lt=until).exclude(
                dest_organization=organization).values(
                'event_id', 'dest_unit').annotate(
                dest_balance=Sum('dest_amount'),
                last_activity_at=Max('created_at')).order_by(
                    'last_activity_at')
        for dest_balance in groupbuy_dest_balances:
            event_id = dest_balance['event_id']
            by_units = dest_balance_per_events.get(event_id, {})
            balance_amount = (by_units.get(dest_balance['dest_unit'], 0) +
                dest_balance['dest_balance'])
            by_units.update({dest_balance['dest_unit']: balance_amount})
            if event_id not in dest_balance_per_events:
                dest_balance_per_events.update({event_id: by_units})

        # Then all payments for these orders will either be of the form:
        #     yyyy/mm/dd sub_***** distribution to provider (backlog accounting)
        #        provider:Receivable                      plan_amount
        #        provider:Backlog
        # (payment_successful and offline_payment), or:
        #    yyyy/mm/dd sub_***** write off receivable
        #        subscriber:Canceled                        liability_amount
        #        provider:Receivable
        # (create_cancel_transactions).
        orig_balances = self.filter(
            (Q(orig_account=Transaction.BACKLOG)
             & Q(dest_account=Transaction.RECEIVABLE)) |
            (Q(orig_account=Transaction.RECEIVABLE)
             & Q(dest_account=Transaction.CANCELED)),
            event_id__in=dest_balance_per_events.keys(),
            created_at__lt=until).values(
                'event_id', 'dest_unit').annotate(
                orig_balance=Sum('dest_amount'),
                last_activity_at=Max('created_at')).order_by(
                    'last_activity_at', '-event_id')
        for orig_balance in orig_balances:
            orig_amount = orig_balance['orig_balance']
            orig_unit = orig_balance['dest_unit']
            event_id = orig_balance['event_id']
            # We could have subscription or group-buy (coupon codes) events
            # in both dest_balances and orig_balances.
            balance_by_units = dest_balance_per_events.get(event_id, {})
            if orig_unit in balance_by_units:
                balance_by_units.update({
                    orig_unit: balance_by_units[orig_unit] - orig_amount})

        balances = {}
        for event_id, balance in six.iteritems(dest_balance_per_events):
            amount_by_units = {}
            for unit, amount in six.iteritems(balance):
                if amount != 0:
                    amount_by_units.update({unit: amount})
            if amount_by_units:
                balances.update({event_id: amount_by_units})
        return balances

    def get_statement_balance(self, organization, until=None):
        balances_per_unit = {}
        for val in six.itervalues(self.get_statement_balances(
                organization, until=until)):
            for unit, amount in six.iteritems(val):
                balances_per_unit.update({
                    unit: balances_per_unit.get(unit, 0) + amount
                })
        balances = {}
        for unit, balance in six.iteritems(balances_per_unit):
            if balance != 0:
                balances.update({unit: balance})
        if len(balances) > 1:
            raise ValueError(
'Multiple balances at %s for %s with different units %s is not supported.' % (
    until, organization, ','.join(six.iterkeys(balances))))
        if balances:
            for unit, balance in six.iteritems(balances):
                # return first and only element
                return balance, unit
        return 0, settings.DEFAULT_UNIT


class TransactionManager(models.Manager):

    def get_queryset(self):
        return TransactionQuerySet(self.model, using=self._db)

    def by_charge(self, charge):
        """
        Returns all transactions associated to a charge.
        """
        return self.filter(event_id__in=[get_charge_event_id(charge)] + [
            get_charge_event_id(charge, item)
            for item in charge.charge_items.all()])

    def by_customer(self, organization):
        """
        Return transactions related to this organization, as a customer.
        """
        # If we include ``dest_account=Transaction.LIABILITY``, the entries
        # used to balance the ledger will also appear. We exclude all
        # entries with ``orig_account=Transaction.PAYABLE`` to compensate.
        return self.filter(
            (Q(dest_organization=organization)
             & (Q(dest_account=Transaction.PAYABLE)
                |Q(dest_account=Transaction.LIABILITY)))
            |(Q(orig_organization=organization)
              & (Q(orig_account=Transaction.LIABILITY)
                 | Q(orig_account=Transaction.REFUNDED)))).exclude(
                     orig_account=Transaction.PAYABLE)

    def by_organization(self, organization, account=None):
        """
        Returns all ``Transaction`` going in or out of an *account*
        for an *organization*.
        """
        if not account:
            account = Transaction.FUNDS
        return self.filter(
            # All transactions involving Funds
            ((Q(orig_organization=organization)
              & Q(orig_account=account))
            | (Q(dest_organization=organization)
              & Q(dest_account=account))))

    def by_subsciptions(self, subscriptions, at_time=None):
        """
        Returns a ``QuerySet`` of all transactions related to a set
        of subscriptions.
        """
        queryset = self.filter(
            dest_account=Transaction.PAYABLE,
            event_id__in=[get_sub_event_id(subscription)
                for subscription in subscriptions])
        if at_time:
            queryset = queryset.filter(created_at=at_time)
        return queryset.order_by('created_at')

    def offline_payment(self, subscription, amount, payment_event_id=None,
                        descr=None, created_at=None, user=None):
        #pylint: disable=too-many-arguments
        """
        For an offline payment, we will record a sequence of ``Transaction``
        as if we went through ``payment_successful`` and ``withdraw_funds``
        while bypassing the processor.

        Thus an offline payment is recorded as follow::

            ; Record the off-line payment

            yyyy/mm/dd check_***** charge event
                provider:Funds                           amount
                subscriber:Liability

            ; Compensate for atomicity of charge record (when necessary)

            yyyy/mm/dd sub_***** invoiced-item event
                subscriber:Liability           min(invoiced_item_amount,
                subscriber:Payable                      balance_payable)

            ; Distribute funds to the provider

            yyyy/mm/dd sub_***** distribution to provider (backlog accounting)
                provider:Receivable                      amount
                provider:Backlog

            yyyy/mm/dd check_***** mark the amount as offline payment
                provider:Offline                         amount
                provider:Funds

        Example::

            2014/09/10 Check received off-line
                cowork:Funds                            $179.99
                xia:Liability

            2014/09/10 Keep a balanced ledger
                xia:Liability                           $179.99
                xia:Payable

            2014/09/10 backlog accounting
                cowork:Receivable                       $179.99
                cowork:Backlog

            2014/09/10 mark payment as processed off-line
                cowork:Offline                          $179.99
                cowork:Funds
        """
        results = []
        if descr is None:
            descr = humanize.DESCRIBE_OFFLINE_PAYMENT
        if user:
            descr += ' (%s)' % user.username
        created_at = datetime_or_now(created_at)
        if not payment_event_id:
            payment_event_id = generate_random_slug(prefix='check_')
        with transaction.atomic():
            subscription_event_id = get_sub_event_id(subscription)
            results.append(self.create(
                created_at=created_at,
                descr=descr,
                event_id=payment_event_id,
                dest_amount=amount,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.FUNDS,
                dest_organization=subscription.plan.organization,
                orig_amount=amount,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.LIABILITY,
                orig_organization=subscription.organization))

            # If there is still an amount on the ``Payable`` account,
            # we create Payable to Liability transaction in order to correct
            # the accounts amounts. This is a side effect of the atomicity
            # requirement for a ``Transaction`` associated to offline payment.
            balance = self.get_event_balance(
                subscription_event_id, account=Transaction.PAYABLE)
            balance_payable = balance['amount']
            if balance_payable > 0:
                available = min(amount, balance_payable)
                results.append(self.create(
                    event_id=subscription_event_id,
                    created_at=created_at,
                    descr=humanize.DESCRIBE_DOUBLE_ENTRY_MATCH,
                    dest_amount=available,
                    dest_unit=subscription.plan.unit,
                    dest_account=Transaction.LIABILITY,
                    dest_organization=subscription.organization,
                    orig_amount=available,
                    orig_unit=subscription.plan.unit,
                    orig_account=Transaction.PAYABLE,
                    orig_organization=subscription.organization))

            results.append(self.create(
                created_at=created_at,
                descr=descr,
                event_id=subscription_event_id,
                dest_amount=amount,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.RECEIVABLE,
                dest_organization=subscription.plan.organization,
                orig_amount=amount,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.BACKLOG,
                orig_organization=subscription.plan.organization))

            results.append(self.create(
                created_at=created_at,
                descr="%s - %s" % (descr, humanize.DESCRIBE_DOUBLE_ENTRY_MATCH),
                event_id=payment_event_id,
                dest_amount=amount,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.OFFLINE,
                dest_organization=subscription.plan.organization,
                orig_amount=amount,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.FUNDS,
                orig_organization=subscription.plan.organization))

            return results


    def distinct_accounts(self):
        return ({val['orig_account']
                 for val in self.all().values('orig_account').distinct()}
                | {val['dest_account']
                    for val in self.all().values('dest_account').distinct()})


    def get_invoiceables(self, organization, until=None):
        """
        Returns a set of payable or liability ``Transaction`` since
        the last successful payment by or writeoff to an ``organization``.
        """
        until = datetime_or_now(until)
        last_payment = self.filter(
            Q(orig_account=Transaction.PAYABLE)
            | Q(orig_account=Transaction.LIABILITY),
            Q(dest_account=Transaction.FUNDS)
            | Q(dest_account=Transaction.WRITEOFF),
            orig_organization=organization,
            created_at__lt=until).order_by('-created_at').first()
        kwargs = {'created_at__lte': until}
        if last_payment:
            # Use ``created_at`` strictly greater than last payment date
            # otherwise we pick up the last payment itself.
            kwargs.update({'created_at__gt':last_payment.created_at})
        return self.filter(
            Q(dest_account=Transaction.PAYABLE)
            | Q(dest_account=Transaction.LIABILITY),
            dest_organization=organization, **kwargs)

    def get_capture(self, order):
        """
        Returns ``Transaction`` that corresponds to the capture
        of the Receivable generated by *order*.
        """
        return self.filter(event_id=order.event_id,
            orig_account=Transaction.BACKLOG,
            dest_account=Transaction.RECEIVABLE,
            created_at__gte=order.created_at).order_by('created_at').first()

    def get_balance(self, organization=None, account=None, like_account=None,
                    starts_at=None, ends_at=None, **kwargs):
        """
        Returns the balance ``until`` a certain date (Today by default).
        The balance can be constraint to a single organization and/or
        for a specific account. The account can be fully qualified or
        a selector pattern.
        """
        #pylint:disable=too-many-locals,too-many-arguments
        dest_params = {}
        orig_params = {}
        dest_params.update(kwargs)
        orig_params.update(kwargs)
        if starts_at:
            dest_params.update({'created_at__gte': starts_at})
            orig_params.update({'created_at__gte': starts_at})
        if ends_at:
            dest_params.update({'created_at__lt': ends_at})
            orig_params.update({'created_at__lt': ends_at})
        if organization is not None:
            dest_params.update({'dest_organization': organization})
            orig_params.update({'orig_organization': organization})
        if account is not None:
            dest_params.update({'dest_account': account})
            orig_params.update({'orig_account': account})
        elif like_account is not None:
            dest_params.update({'dest_account__icontains': like_account})
            orig_params.update({'orig_account__icontains': like_account})
        dest_balances = sum_dest_amount(self.filter(**dest_params))
        orig_balances = sum_orig_amount(self.filter(**orig_params))
        return sum_balance_amount(dest_balances, orig_balances)

    def get_statement_balances(self, organization, until=None):
        return self.get_queryset().get_statement_balances(
            organization, until=until)

    def get_statement_balance(self, organization, until=None):
        return self.get_queryset().get_statement_balance(
            organization, until=until)

    def get_subscription_statement_balance(self, subscription, until=None):
        # XXX A little long but no better so far.
        #pylint:disable=invalid-name
        """
        Returns the balance of ``Payable`` and ``Liability`` treated
        as a single account for a subscription.

        The balance on a subscription is used to determine when
        a subscription is locked (balance due) or unlocked (no balance).
        """
        balances = self.get_statement_balances(
            subscription.organization, until=until)
        subscription_event_id = get_sub_event_id(subscription)
        dest_amount = 0
        dest_unit = None
        for event_id, balance in six.iteritems(balances):
            # subscription_event_id endswith a '/' which is garenteed
            # to be a terminal character.
            if event_id and event_id.startswith(subscription_event_id):
                if len(balance) > 1:
                    raise ValueError(
                        _("balance with multiple currency units (%s)") %
                        str(balance))
                try:
                    balance_unit, balance_amount = next(six.iteritems(balance))
                    dest_amount += balance_amount
                    if dest_unit and balance_unit != dest_unit:
                        raise ValueError(
                            _("balances with multiple currency units"\
                              " (%(dest_unit)s, %(balance_unit)s)") % (
                                dest_unit, balance_unit))
                    dest_unit = balance_unit
                except StopIteration:
                    pass
        if not dest_unit:
            dest_unit = settings.DEFAULT_UNIT
        return dest_amount, dest_unit

    def get_event_balance(self, event_id,
                          account=None, starts_at=None, ends_at=None):
        """
        Returns the balance on a *event_id* for an *account*
        for the period [*starts_at*, *ends_at*[ as a tuple (amount, unit).
        """
        return self.get_balance(event_id=event_id, account=account,
            starts_at=starts_at, ends_at=ends_at)

    def get_subscription_income_balance(self, subscription,
                                        starts_at=None, ends_at=None):
        """
        Returns the recognized income balance on a subscription
        for the period [starts_at, ends_at[ as a tuple (amount, unit).
        """
        event_id = get_sub_event_id(subscription)
        return self.get_event_balance(event_id,
            account=Transaction.INCOME, starts_at=starts_at, ends_at=ends_at)

    def get_use_charge_balance(self, subscription, use_charge,
                                        starts_at=None, ends_at=None):
        """
        Returns the recognized income balance on a use charge
        for the period [starts_at, ends_at[ as a tuple (amount, unit).
        """
        event_id = get_sub_event_id(subscription, use_charge)
        return self.get_event_balance(event_id,
            account=Transaction.INCOME, starts_at=starts_at, ends_at=ends_at)

    def get_subscription_invoiceables(self, subscription, until=None):
        """
        Returns a set of payable or liability ``Transaction`` since
        the last successful payment on a subscription.
        """
        until = datetime_or_now(until)
        event_id = get_sub_event_id(subscription)
        last_payment = self.filter(
            Q(orig_account=Transaction.PAYABLE)
            | Q(orig_account=Transaction.LIABILITY),
            event_id=event_id,
            orig_organization=subscription.organization,
            dest_account=Transaction.FUNDS,
            created_at__lt=until).order_by('created_at').first()
        if last_payment:
            # Use ``created_at`` strictly greater than last payment date
            # otherwise we pick up the last payment itself.
            kwargs = {'created_at__gt':last_payment.created_at}
        else:
            kwargs = {}
        return self.filter(
            Q(dest_account=Transaction.PAYABLE)
            | Q(dest_account=Transaction.LIABILITY),
            event_id=event_id,
            dest_organization=subscription.organization, **kwargs)

    def get_subscription_receivable(self, subscription,
                                    starts_at=None, until=None):
        """
        Returns the receivable transactions on a subscription
        in the period [starts_at, ends_at[.
        """
        kwargs = {}
        if starts_at:
            kwargs.update({'created_at__gte': starts_at})
        until = datetime_or_now(until)
        return self.filter(
            orig_account=Transaction.RECEIVABLE,
            event_id=get_sub_event_id(subscription),
            created_at__lt=until, **kwargs).order_by('created_at')

    def new_use_charge(self, subscription, use_charge, quantity,
                       custom_amount=None, created_at=None, descr=None):
        """
        Each time a subscriber places an order through
        the /billing/:organization/cart/ page, a ``Transaction``
        is recorded as follow::

            yyyy/mm/dd sub_*****_*** description
                subscriber:Payable                       amount
                provider:Receivable

        Example::

            2014/09/10 additional charge for 1,000 sheet of paper
                xia:Payable                              $39.99
                cowork:Receivable
        """
        #pylint:disable=too-many-arguments
        if quantity <= 0:
            # Minimum quantity for a use charge is one.
            quantity = 1
        if custom_amount is not None:
            amount = custom_amount * quantity
        else:
            amount = use_charge.use_amount * quantity
        if not descr:
            descr = humanize.describe_buy_use(use_charge, quantity)
        # If the subscription has not yet been recorded in the database
        # we don't have an id for it (see order/checkout pages). We store
        # a 'sub_0/{user_charge.pk}' event_id. The 'sub_0/' prefix can later
        # be replaced once the subscription is committed to the database.
        event_id = get_sub_event_id(subscription, use_charge)
        return self.new_payable(
            subscription.organization, Price(amount, subscription.plan.unit),
            subscription.plan.organization, descr,
            event_id=event_id, created_at=created_at)

    def new_subscription_order(self, subscription,
        amount=None, descr=None, created_at=None):
        #pylint: disable=too-many-arguments
        """
        Each time a subscriber places an order through
        the /billing/:organization/cart/ page, a ``Transaction``
        is recorded as follow::

            yyyy/mm/dd sub_***** description
                subscriber:Payable                       amount
                provider:Receivable

        Example::

            2014/09/10 subscribe to open-space plan
                xia:Payable                             $179.99
                cowork:Receivable
        """
        created_at = datetime_or_now(created_at)
        if amount is None:
            amount = subscription.plan.period_amount
            nb_periods = subscription.plan.period_length
            ends_at = subscription.plan.end_of_period(
                subscription.ends_at, nb_periods)
            # descr will later be use to recover the ``period_number``,
            # so we need to use The true ``nb_periods`` and not the number
            # of natural periods.
            full_name = None
            if not subscription.organization.attached_user():
                full_name = subscription.organization.printable_name
            descr = humanize.describe_buy_periods(
                subscription.plan, ends_at, nb_periods,
                full_name=full_name) # full_name without a coupon
        elif not descr:
            LOGGER.warning("creating a `new_subscription_order` for %s"\
                " with amount %d has no description.",
                subscription, amount)
        # If the subscription has not yet been recorded in the database
        # we don't have an id for it (see order/checkout pages). We thus
        # record a 'sub_0/' event id that can later be replaced once
        # the subscription is committed to the database.
        event_id = get_sub_event_id(subscription)
        return self.new_payable(
            subscription.organization,
            Price(amount, subscription.plan.unit),
            subscription.plan.organization, descr,
            event_id=event_id, created_at=created_at)

    @staticmethod
    def new_payable(customer, price, provider, descr,
                    event_id=None, created_at=None):
        #pylint:disable=too-many-arguments
        created_at = datetime_or_now(created_at)
        return Transaction(
            created_at=created_at,
            descr=descr,
            event_id=event_id,
            dest_amount=price.amount,
            dest_unit=price.unit,
            dest_account=Transaction.PAYABLE,
            dest_organization=customer,
            orig_amount=price.amount,
            orig_unit=price.unit,
            orig_account=Transaction.RECEIVABLE,
            orig_organization=provider)

    def new_subscription_later(self, subscription, created_at=None):
        """
        Returns a ``Transaction`` for the subscription balance
        to be paid later.
        """
        return self.new_subscription_statement(subscription,
            created_at=created_at,
            descr_pat=humanize.DESCRIBE_BALANCE + '- Pay later',
            balance_now=0)

    def new_subscription_statement(self, subscription, created_at=None,
                                   descr_pat=None, balance_now=None):
        """
        Since the ordering system is tightly coupled to the ``Transaction``
        ledger, we create special "none" transaction that are referenced
        when a ``Charge`` is created for payment of a balance due
        by a subcriber::

            yyyy/mm/dd sub_***** description
                subscriber:Settled                        amount
                provider:Settled

        Example::

            2014/09/10 balance due
                xia:Settled                             $179.99
                cowork:Settled
        """
        created_at = datetime_or_now(created_at)
        balance, unit = self.get_subscription_statement_balance(
            subscription, until=created_at)
        if balance_now is None:
            balance_now = balance
        if descr_pat is None:
            descr_pat = humanize.DESCRIBE_BALANCE
        return Transaction(
            event_id=get_sub_event_id(subscription),
            created_at=created_at,
            descr=descr_pat % {'amount': humanize.as_money(balance, unit),
                'plan': subscription.plan},
            dest_unit=unit,
            dest_amount=balance_now,
            dest_account=Transaction.SETTLED,
            dest_organization=subscription.organization,
            orig_unit=unit,
            orig_amount=balance_now,
            orig_account=Transaction.SETTLED,
            orig_organization=subscription.plan.organization)

    def create_period_started(self, subscription, created_at=None):
        """
        When a period starts and we have a payable balance
        for a subscription, we transfer it to a ``Liability``
        account, recorded as follow::

            yyyy/mm/dd sub_***** description
                subscriber:Liability                     period_amount
                subscriber:Payable

        Example::

            2014/09/10 past due for period 2014/09/10 to 2014/10/10
                xia:Liability                             $179.99
                xia:Payable
        """
        created_at = datetime_or_now(created_at)
        amount = subscription.plan.period_amount
        return self.create(
            created_at=created_at,
            descr=humanize.DESCRIBE_LIABILITY_START_PERIOD,
            dest_amount=amount,
            dest_unit=subscription.plan.unit,
            dest_account=Transaction.LIABILITY,
            dest_organization=subscription.organization,
            orig_amount=amount,
            orig_unit=subscription.plan.unit,
            orig_account=Transaction.PAYABLE,
            orig_organization=subscription.organization,
            event_id=get_sub_event_id(subscription))

    def create_income_recognized(self, subscription,
        amount=0, starts_at=None, ends_at=None, descr=None,
        event_id=None, dry_run=False):
        """
        When a period ends and we either have a ``Backlog`` (payment
        was made before the period starts) or a ``Receivable`` (invoice
        is submitted after the period ends). Either way we must recognize
        income for that period since the subscription was serviced::

            yyyy/mm/dd sub_***** When payment was made at begining of period
                provider:Backlog                   period_amount
                provider:Income

            yyyy/mm/dd sub_***** When service is invoiced after period ends
                provider:Receivable                period_amount
                provider:Income

        Example::

            2014/09/10 recognized income for period 2014/09/10 to 2014/10/10
                cowork:Backlog                         $179.99
                cowork:Income
        """
        #pylint:disable=unused-argument,too-many-arguments,too-many-locals
        created_transactions = []
        ends_at = datetime_or_now(ends_at)
        if not event_id:
            event_id = get_sub_event_id(subscription)
        # ``created_at`` is set just before ``ends_at``
        # so we do not include the newly created transaction
        # in the subsequent period.
        created_at = ends_at - relativedelta(seconds=1)
        balance = self.get_event_balance(event_id,
            account=Transaction.BACKLOG, ends_at=ends_at)
        backlog_amount = - balance['amount'] # def. balance must be negative
        balance = self.get_event_balance(event_id,
            account=Transaction.RECEIVABLE, ends_at=ends_at)
        receivable_amount = - balance['amount'] # def. balance must be negative
        LOGGER.debug("recognize %dc(%s) with %dc(%s) backlog available,"\
            " %dc(%s) receivable available at %s",
            amount, amount.__class__, backlog_amount, backlog_amount.__class__,
            receivable_amount, receivable_amount.__class__, ends_at)
        assert backlog_amount >= 0 or receivable_amount >= 0
        if amount > 0 and backlog_amount > 0:
            backlog_remain = backlog_amount - amount
            if backlog_remain > 0 and backlog_remain < 50:
                # Dealing with rounding approximations: If there would be less
                # than 50c left of backlog, we include it as recognized income.
                amount = backlog_amount
            available = min(amount, backlog_amount)
            LOGGER.info(
                'RECOGNIZE BACKLOG %dc of %dc for %s at %s',
                available, backlog_amount, subscription, created_at)
            recognized = Transaction(
                created_at=created_at,
                descr=descr,
                event_id=event_id,
                dest_amount=available,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.BACKLOG,
                dest_organization=subscription.plan.organization,
                orig_amount=available,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.INCOME,
                orig_organization=subscription.plan.organization)
            if not dry_run:
                recognized.save()
            created_transactions += [recognized]
            amount -= available
        if amount > 0 and receivable_amount > 0:
            receivable_remain = receivable_amount - amount
            if receivable_remain > 0 and receivable_remain < 50:
                # Dealing with rounding approximations: If there would be less
                # than 50c left of receivable, we recognize it this period.
                amount = receivable_amount
            available = min(amount, receivable_amount)
            LOGGER.info(
                'RECOGNIZE RECEIVABLE %dc of %dc for %s at %s',
                available, receivable_amount, subscription, created_at)
            recognized = Transaction(
                created_at=created_at,
                descr=descr,
                event_id=event_id,
                dest_amount=available,
                dest_unit=subscription.plan.unit,
                dest_account=Transaction.RECEIVABLE,
                dest_organization=subscription.plan.organization,
                orig_amount=available,
                orig_unit=subscription.plan.unit,
                orig_account=Transaction.INCOME,
                orig_organization=subscription.plan.organization)
            if not dry_run:
                recognized.save()
            created_transactions += [recognized]
            amount -= available
        #pylint:disable=protected-access
        assert amount == 0, (
            "[%s] amount(%dc) should be zero for subscription %d" % (
                subscription._state.db, amount, subscription.pk))
        return created_transactions

    @staticmethod
    def by_processor_key(invoiced_items):
        """
        Returns a dictionnary {processor_key: [invoiced_item ...]}
        such that all invoiced_items appear under a processor_key.
        """
        results = {}
        default_processor_key = get_broker().processor_backend.pub_key
        for invoiced_item in invoiced_items:
            event = invoiced_item.get_event() # Subscription, SubscriptionUse,
                                              # or Coupon (i.e. Group buy)
            if event:
                processor_key = event.provider.processor_backend.pub_key
                if not processor_key:
                    processor_key = default_processor_key
            else:
                processor_key = default_processor_key
            if not processor_key in results:
                results[processor_key] = []
            results[processor_key] += [invoiced_item]
        return results


@python_2_unicode_compatible
class Transaction(models.Model):
    """
    The Transaction table stores entries in the double-entry bookkeeping
    ledger.

    'Invoiced' comes from the service. We use for acrual tax reporting.
    We have one 'invoiced' for each job? => easy to reconciliate.

    'Balance' is amount due.

    use 'ledger register' for tax acrual tax reporting.
    """
    # provider side
    FUNDS = 'Funds'           # "Cash" account.
    WITHDRAW = 'Withdraw'     # >= 0
    REFUND = 'Refund'         # >= 0
    CHARGEBACK = 'Chargeback'
    CANCELED = 'Canceled'
    WRITEOFF = 'Writeoff'
    RECEIVABLE = 'Receivable' # always <= 0
    BACKLOG = 'Backlog'       # always <= 0
    INCOME = 'Income'         # always <= 0
    OFFLINE = 'Offline'
    EXPENSES = 'Expenses'

    # subscriber side
    PAYABLE = 'Payable'       # always >= 0
    LIABILITY = 'Liability'   # always >= 0
    REFUNDED = 'Refunded'     # always <= 0

    # ``Transaction`` that can be referenced as an invoiced item
    # when we can attempt to charge a balance due.
    SETTLED = 'settled'


    objects = TransactionManager()

    # Implementation Note:
    # An exact created_at is too important to let auto_now_add mess with it.
    created_at = models.DateTimeField(
        help_text=_("Date/time of creation (in ISO format)"))

    orig_account = models.CharField(max_length=255, default="unknown",
        help_text=_("Source account from which funds are withdrawn"))
    orig_organization = models.ForeignKey(settings.ORGANIZATION_MODEL,
        on_delete=models.PROTECT,
        related_name="outgoing",
        help_text=_("Billing profile from which funds are withdrawn"))
    orig_amount = models.PositiveIntegerField(default=0,
        help_text=_("Amount withdrawn from source in orig_unit"))
    orig_unit = models.CharField(max_length=3, default=settings.DEFAULT_UNIT,
        help_text=_("Three-letter ISO 4217 code for source currency unit"\
            " (ex: usd)"))
    dest_account = models.CharField(max_length=255, default="unknown",
        help_text=_("Target account to which funds are deposited"))
    dest_organization = models.ForeignKey(settings.ORGANIZATION_MODEL,
        on_delete=models.PROTECT,
        related_name="incoming",
        help_text=_("Billing profile to which funds are deposited"))
    dest_amount = models.PositiveIntegerField(default=0,
        help_text=_("Amount deposited into target in dest_unit"))
    dest_unit = models.CharField(max_length=3, default=settings.DEFAULT_UNIT,
        help_text=_("Three-letter ISO 4217 code for target currency unit"\
            " (ex: usd)"))

    # Optional
    descr = models.TextField(default="N/A",
        help_text=_("Free-form text description for the Transaction"))
    event_id = models.SlugField(null=True,
        help_text=_("Event at the origin of this transaction"\
        " (ex. subscription, charge, etc.)"))

    def __str__(self):
        return str(self.id)

    @property
    def dest_price(self):
        return Price(self.dest_amount, self.dest_unit)

    @property
    def orig_price(self):
        return Price(self.orig_amount, self.orig_unit)

    @property
    def is_sub_event_id(self):
        """
        Returns `True` if the `Transaction` refers to a `Subscription` or
        `SubscriptionUse`.
        """
        return re.match(r'^sub_(\d+)/', self.event_id) is not None

    @property
    def is_sub_use_event_id(self):
        """
        Returns `True` if the `Transaction` refers to a `SubscriptionUse`.
        """
        return re.match(r'^sub_(\d+)/(\d+)/', self.event_id) is not None

    @property
    def subscription(self):
        """
        Returns the `Subscription` object associated to the `Transaction`
        or `None` if it could not be deduced from the `event_id`.
        """
        #pylint:disable=attribute-defined-outside-init
        if not hasattr(self, '_subscription'):
            self._subscription = Subscription.objects.get_by_event_id(
                self.event_id)
        return self._subscription

    def is_debit(self, organization):
        '''
        Return True if this transaction is a debit (negative ledger entry).
        '''
        return ((self.orig_organization == organization       # customer
                 and self.dest_account == Transaction.FUNDS)
                or (self.orig_organization == organization    # provider
                 and self.orig_account == Transaction.FUNDS))

    def get_event(self):
        """
        Returns the associated 'event' (SubscriptionUse, Subscription,
        Charge, or Coupon) if available.
        """
        if not self.event_id:
            return None
        usage = SubscriptionUse.objects.get_by_event_id(self.event_id)
        if usage:
            return usage
        subscription = Subscription.objects.get_by_event_id(self.event_id)
        if subscription:
            return subscription
        charge = Charge.objects.get_by_event_id(self.event_id)
        if charge:
            return charge
        coupon = Coupon.objects.get_by_event_id(self.event_id)
        if coupon:
            return coupon
        return None


@python_2_unicode_compatible
class BalanceLine(models.Model):
    """
    Defines a line in a balance sheet. All ``Transaction`` account matching
    ``selector`` will be aggregated over a period of time.

    When ``is_positive`` is ``True``, the absolute value will be reported.
    """
    report = models.SlugField()
    title = models.CharField(max_length=255,
        help_text=_("Title for the row"))
    selector = models.CharField(max_length=255, blank=True,
        help_text=_("Filter on transaction accounts"))
    is_positive = models.BooleanField(default=False)
    rank = models.IntegerField(
        help_text=_("Absolute position of the row in the list of rows"\
        " for the table"))
    moved = models.BooleanField(default=False)

    class Meta:
        unique_together = ('report', 'rank', 'moved')

    def __str__(self):
        return '%s/%d' % (self.report, int(self.rank))


def _clean_field(model, field_name, value, prefix='profile_'):
    #pylint:disable=protected-access
    field = model._meta.get_field(field_name)
    max_length = field.max_length
    if len(value) > max_length:
        orig = value
        value = value[:max_length]
        LOGGER.info("shorten %s '%s' to '%s' because it is longer than"\
            " %d characters", field_name, orig, value, max_length)
    try:
        field.run_validators(value)
    except DjangoValidationError:
        orig = value
        value = generate_random_slug(max_length, prefix=prefix)
        LOGGER.info("'%s' is an invalid %s so use '%s' instead.",
            orig, field_name, value)
    return value


def get_broker():
    """
    Returns the site-wide provider from a request.
    """
    LOGGER.debug("get_broker('%s')", settings.BROKER_CALLABLE)
    if isinstance(settings.BROKER_CALLABLE, six.string_types):
        try:
            settings.BROKER_CALLABLE = import_string(settings.BROKER_CALLABLE)
        except (ImportError, ModuleNotFoundError):
            pass
    if callable(settings.BROKER_CALLABLE):
        return settings.BROKER_CALLABLE()

    return get_organization_model().objects.get(slug=settings.BROKER_CALLABLE)


def is_broker(organization):
    """
    Returns ``True`` if the organization is the hosting platform
    for the service.
    """
    # We do a string compare here because both ``Organization`` might come
    # from a different db. That is if the organization parameter is not
    # a unicode string itself.
    if isinstance(organization, get_organization_model()):
        organization_slug = organization.slug
    else:
        organization_slug = str(organization)

    if settings.IS_BROKER_CALLABLE:
        if isinstance(settings.IS_BROKER_CALLABLE, six.string_types):
            try:
                settings.IS_BROKER_CALLABLE = import_string(
                    settings.IS_BROKER_CALLABLE)
            except (ImportError, ModuleNotFoundError):
                pass
        if callable(settings.IS_BROKER_CALLABLE):
            return settings.IS_BROKER_CALLABLE(organization_slug)

    return get_broker().slug == organization_slug


def is_sqlite3(db_key=None):
    if db_key is None:
        db_key = DEFAULT_DB_ALIAS
    return connections.databases[db_key]['ENGINE'].endswith('sqlite3')


def get_charge_event_id(charge, charge_item=None):
    """
    Returns a formatted id for a charge (or a charge_item
    on that charge) that can be used as `event_id` in a `Transaction`.
    """
    substr = "cha_%d/" % charge.id
    if charge_item:
        substr += "%d/" % charge_item.id
    return substr


def get_sub_event_id(subscription, use_charge=None):
    """
    Returns a formatted id for a subscription (or a use_charge
    on that subscription) that can be used as `event_id` in a `Transaction`.

    When we are building a cart order, subscriptions might not yet be present
    in the database (i.e. `subscription.pk is None`). In that case we use
    a generic 'sub_0/' prefix that can be later overriden when the subscription
    has been committed to the database.
    """
    if subscription.pk:
        substr = "sub_%d/" % subscription.pk
    else:
        substr = "sub_0/"
    if use_charge:
        substr += "%d/" % use_charge.pk
    return substr


def get_period_usage(subscription, use_charge, starts_at, ends_at):
    return sum_dest_amount(Transaction.objects.filter(
        orig_account=Transaction.RECEIVABLE,
        dest_account=Transaction.PAYABLE, created_at__lt=ends_at,
        created_at__gte=starts_at,
        event_id=get_sub_event_id(subscription, use_charge)))


def record_use_charge(subscription, use_charge, quantity=1, created_at=None):
    """
    Adds a use charge to the balance due by the subscriber
    """
    results = []
    invoiced_item = None
    invoiced_quantity = 0
    if not quantity:
        quantity = 1

    with transaction.atomic():
        usage, unused_created = SubscriptionUse.objects.get_or_create(
            subscription=subscription, use=use_charge, defaults={
                'expiring_quota': use_charge.quota
        })
        LOGGER.debug("[record_use_charge] %d units at %s "\
            "- (expiring_quota=%d, rollover_quota=%d)",
            quantity, created_at, usage.expiring_quota, usage.rollover_quota)
        if usage.expiring_quota >= quantity:
            # We are still below period quota
            usage.expiring_quota -= quantity
        else:
            invoiced_quantity = quantity - usage.expiring_quota
            usage.expiring_quota = 0
            LOGGER.debug("[record_use_charge] %d units at %s "\
                "- rollover_quota(%d) >= invoiced_quantity(%d)",
                quantity, created_at, usage.rollover_quota, invoiced_quantity)
            if usage.rollover_quota >= invoiced_quantity:
                # We are still below reserved usage paid in advance
                usage.rollover_quota -= invoiced_quantity
                invoiced_quantity = 0
            else:
                invoiced_quantity = invoiced_quantity - usage.rollover_quota
                usage.rollover_quota = 0
                invoiced_item = Transaction.objects.new_use_charge(
                    subscription, use_charge, invoiced_quantity,
                    created_at=created_at)

        usage.used_quantity += quantity
        usage.save()

        if invoiced_item:
            invoiced_item.save()
            results = [invoiced_item]
            signals.quota_reached.send(sender=__name__, usage=invoiced_quantity,
                use_charge=use_charge, subscription=subscription)

    period_balances = get_period_usage(subscription, use_charge,
        subscription.created_at, subscription.ends_at)
    for row in period_balances:
        amount = row['amount']
        if use_charge.maximum_limit and amount >= use_charge.maximum_limit:
            signals.use_charge_limit_crossed.send(sender=__name__,
                usage=amount, use_charge=use_charge, subscription=subscription)

    return results


def sum_balance_amount(dest_balances, orig_balances):
    """
    `dest_balances` and `orig_balances` are mostly the results
    of `sum_dest_amount` and `sum_orig_amount` respectively.
    """
    balances_by_unit = {}
    created_at = None
    for row in dest_balances:
        balances_by_unit.update({row['unit']: row['amount']})
        if created_at is None:
            created_at = row['created_at']
        else:
            created_at = max(row['created_at'], created_at)
    for row in orig_balances:
        balances_by_unit.update({row['unit']:
            balances_by_unit.get(row['unit'], 0) - row['amount']})
        if created_at is None:
            created_at = row['created_at']
        else:
            created_at = max(row['created_at'], created_at)
    balances = []
    for unit, balance in six.iteritems(balances_by_unit):
        if balance != 0:
            balances += [{
                'amount': balance,
                'unit': unit,
                'created_at': created_at # XXX OK to use max of all?
            }]
    if len(balances) > 1:
        raise ValueError(_("balances with multiple currency units (%s)") %
            str(balances))
    if balances:
        return balances[0]
    return {'amount': 0, 'unit': settings.DEFAULT_UNIT,
        'created_at': datetime_or_now()}


def sum_dest_amount(transactions):
    """
    Return the sum of the amount in the *transactions* set.
    """
    query_result = []
    if isinstance(transactions, QuerySet):
        if transactions.exists():
            query_result = transactions._clone()#pylint:disable=protected-access
            query_result.query.clear_ordering(True)
            query_result = query_result.values('dest_unit').annotate(
                Sum('dest_amount'), Max('created_at')).distinct()
    else:
        group_by = {}
        most_recent = None
        for item in transactions:
            if not most_recent or item.created_at < most_recent:
                most_recent = item.created_at
            if not item.dest_unit in group_by:
                group_by[item.dest_unit] = 0
            group_by[item.dest_unit] += item.dest_amount
        for unit, amount in six.iteritems(group_by):
            query_result += [{'dest_unit': unit, 'dest_amount__sum': amount,
                'created_at__max': most_recent}]
    results = []
    for res in query_result:
        results += [{
            'amount': res['dest_amount__sum'],
            'unit': res['dest_unit'],
            'created_at': res['created_at__max']}]
    if not results:
        results = [{'amount': 0, 'unit': settings.DEFAULT_UNIT,
            'created_at': datetime_or_now()}]
    return results


def sum_orig_amount(transactions):
    """
    Return the sum of the amount in the *transactions* set.
    """
    query_result = []
    if isinstance(transactions, QuerySet):
        if transactions.exists():
            query_result = transactions._clone()#pylint:disable=protected-access
            query_result.query.clear_ordering(True)
            query_result = query_result.values('orig_unit').annotate(
                Sum('orig_amount'), Max('created_at')).distinct()
    else:
        group_by = {}
        most_recent = None
        for item in transactions:
            if not most_recent or item.created_at < most_recent:
                most_recent = item.created_at
            if not item.orig_unit in group_by:
                group_by[item.orig_unit] = 0
            group_by[item.orig_unit] += item.orig_amount
        for unit, amount in six.iteritems(group_by):
            query_result += [{'orig_unit': unit, 'orig_amount__sum': amount,
                'created_at__max': most_recent}]
    results = []
    for res in query_result:
        results += [{
            'amount': res['orig_amount__sum'],
            'unit': res['orig_unit'],
            'created_at': res['created_at__max']}]
    if not results:
        results = [{'amount': 0, 'unit': settings.DEFAULT_UNIT,
            'created_at': datetime_or_now()}]
    return results
