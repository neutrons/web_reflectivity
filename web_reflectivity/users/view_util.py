#pylint: disable=bare-except, invalid-name
"""
    View utility functions for user management
"""
import sys
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.conf import settings

# import code for encoding urls and generating md5 hashes
import hashlib
import socket
import logging


def fill_template_values(request, **template_args):
    """
        Fill the template argument items needed to populate
        side bars and other satellite items on the pages.

        Only the arguments common to all pages will be filled.
    """
    template_args['user'] = request.user
    if request.user.is_authenticated():
        if hasattr(settings, 'GRAVATAR_URL'):
            guess_email = "%s@%s" % (request.user.username, settings.ALLOWED_HOSTS[0])
            gravatar_url = settings.GRAVATAR_URL+hashlib.md5(guess_email).hexdigest()+'?d=identicon'
            template_args['gravatar_url'] = gravatar_url
    else:
        request.user.username = 'Guest User'

    template_args['logout_url'] = reverse('users:perform_logout')
    redirect_url = reverse('users:perform_login')
    redirect_url  += '?next=%s' % request.path
    template_args['login_url'] = redirect_url

    # Determine whether the user is using a mobile device
    template_args['is_mobile'] = hasattr(request, 'mobile') and request.mobile

    return template_args

def is_instrument_staff(request, instrument_id):
    """
        Determine whether a user is part of an
        instrument team
        @param request: HTTP request object
        @param instrument_id: Instrument object
    """
    # Look for Django group
    try:
        instrument_name = str(instrument_id).upper()
        instr_group = Group.objects.get(name="%s%s" % (instrument_name,
                                                       settings.INSTRUMENT_TEAM_SUFFIX))
        if instr_group in request.user.groups.all():
            return True
    except Group.DoesNotExist:
        # The group doesn't exist, carry on
        pass
    # Look for LDAP group
    try:
        if request.user is not None and hasattr(request.user, "ldap_user"):
            groups = request.user.ldap_user.group_names
            if u'sns_%s_team' % str(instrument_id).lower() in groups \
            or u'snsadmin' in groups:
                return True
    except:
        # Couldn't find the user in the instrument LDAP group
        pass
    return request.user.is_staff

def is_experiment_member(request, instrument_id, experiment_id):
    """
        Determine whether a user is part of the given experiment.

        @param request: request object
        @param instrument_id: Instrument object
        @param experiment_id: IPTS object
    """
    if hasattr(settings, 'HIDE_RUN_DETAILS') and settings.HIDE_RUN_DETAILS is False:
        return True

    try:
        if request.user is not None and hasattr(request.user, "ldap_user"):
            groups = request.user.ldap_user.group_names
            return u'sns_%s_team' % str(instrument_id).lower() in groups \
            or u'sns-ihc' in groups \
            or u'snsadmin' in groups \
            or u'%s' % experiment_id.expt_name.upper() in groups \
            or is_instrument_staff(request, instrument_id)
    except:
        logging.error("Error determining whether user %s is part of %s", str(request.user), str(experiment_id))
    return request.user.is_staff
