#pylint: disable=bare-except, invalid-name, too-many-nested-blocks, too-many-locals, too-many-branches
"""
    Optional utilities to communicate with ONcat.
    ONcat is an online data catalog used internally at ORNL.

    @copyright: 2018 Oak Ridge National Laboratory
"""
import sys
import datetime
import logging

from django.conf import settings
try:
    import pyoncat
    HAVE_ONCAT = True
except:
    HAVE_ONCAT = False

from fitting.models import CatalogCache

def decode_time(timestamp):
    """
        Decode timestamp and return a datetime object
        :param timestamp: timestamp to decode
    """
    try:
        tz_location = timestamp.rfind('+')
        if tz_location < 0:
            tz_location = timestamp.rfind('-')
        if tz_location > 0:
            date_time_str = timestamp[:tz_location]
            # Get rid of fractions of a second
            sec_location = date_time_str.rfind('.')
            if sec_location > 0:
                date_time_str = date_time_str[:sec_location]
            return datetime.datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%S")
    except:
        logging.error("Could not parse timestamp '%s': %s", timestamp, sys.exc_value)
        return None

def get_run_info(instrument, run_number):
    """
        Legacy issue:
        Until the facility information is stored in the DB so that we can
        retrieve the facility from it, we'll have to use the application
        configuration.

        :param str instrument: instrument name
        :param str run_number: run number
        :param str facility: facility name (SNS or HFIR)
    """
    facility = 'SNS'
    if hasattr(settings, 'FACILITY_INFO'):
        facility = settings.FACILITY_INFO.get(instrument, 'SNS')
    return _get_run_info(instrument, run_number, facility)

def _get_run_info(instrument, run_number, facility='SNS'):
    """
        Get ONCat info for the specified run
        Notes: At the moment we do not catalog reduced data
        :param str instrument: instrument short name
        :param str run_number: run number
        :param str facility: facility name (SNS or HFIR)
    """
    run_info = {}
    cached_entry = [] #CatalogCache.objects.filter(data_path="%s/%s" % (instrument, run_number))
    if len(cached_entry) > 0:
        return dict(title=cached_entry[0].title, proposal=cached_entry[0].proposal)

    if not HAVE_ONCAT:
        return run_info

    try:
        oncat = pyoncat.ONCat(
            settings.CATALOG_URL,
            # Here we're using the machine-to-machine "Client Credentials" flow,
            # which requires a client ID and secret, but no *user* credentials.
            flow = pyoncat.CLIENT_CREDENTIALS_FLOW,
            client_id = settings.CATALOG_ID,
            client_secret = settings.CATALOG_SECRET,
        )
        oncat.login()

        datafiles = oncat.Datafile.list(
            facility = facility,
            instrument = instrument.upper(),
            projection = ['experiment', 'location', 'metadata.entry.title'],
            tags = ['type/raw'],
            ranges_q = 'indexed.run_number:%s' % str(run_number)
        )
        if datafiles:
            run_info['title'] = datafiles[0].metadata.get('entry', {}).get('title', None)
            run_info['proposal'] = datafiles[0].experiment
            run_info['location'] = datafiles[0].location
    except:
        logging.error("Communication with ONCat server failed: %s", sys.exc_value)

    return run_info
