#pylint: disable=bare-except
"""
    Abstraction of the data handler. For test purposes, we can store data locally.
    With a production system, we are likely to set the data to a remote server.
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import sys
import logging
import json
import httplib
import hashlib
import string
import requests
from django.conf import settings
from django.utils import dateparse, timezone

from ..models import UserData

def generate_key(instrument, run_id):
    """
        Generate a secret key for a run on a given instrument

        :param str instrument: instrument name
        :param int run_id: run number
    """
    if not hasattr(settings, "LIVE_PLOT_SECRET_KEY"):
        return None
    secret_key = settings.LIVE_PLOT_SECRET_KEY
    if len(secret_key) == 0:
        return None
    else:
        h = hashlib.sha1()
        h.update("%s%s%s" % (instrument.upper(), secret_key, run_id))
        return h.hexdigest()

def append_key(input_url, instrument, run_id):
    """
        Append a live data secret key to a url

        :param str input_url: url to modify
        :param str instrument: instrument name
        :param int run_id: run number
    """
    client_key = generate_key(instrument, run_id)
    if client_key is None:
        return input_url
    # Determine whether this is the first query string argument of the url
    delimiter = '&' if '/?' in input_url else '?'
    return "%s%skey=%s" % (input_url, delimiter, client_key)

def store_user_data(request, file_name, plot):
    """
        Store user data

        :param Request request: Django request object
        :param str file_name: name of the uploaded file
        :param str plot: user data, as a plotly json object
    """
    if 'datahandler' in settings.INSTALLED_APPS:
        return _local_store(request, file_name, plot)
    else:
        return _remote_store(request, file_name, plot)

def _local_store(request, file_name, plot):
    """
        Store user data locally

        :param Request request: Django request object
        :param str file_name: name of the uploaded file
        :param str plot: user data, as a plotly json object
    """
    from datahandler.models import Instrument, DataRun, PlotData

    # Get or create the instrument
    instrument_obj, _ = Instrument.objects.get_or_create(name=str(request.user).lower())

    run_list = DataRun.objects.filter(instrument=instrument_obj, run_id=file_name)
    if len(run_list) > 0:
        run_obj = run_list.latest('created_on')
    else:
        run_obj = DataRun()
        run_obj.instrument = instrument_obj
        run_obj.run_number = 0
        run_obj.run_id = file_name
        run_obj.save()
        # Since user data have no run number, force the run number to be the PK,
        # which is unique and will allow use to retrieve the data live normal
        # instrument data.
        run_obj.run_number = run_obj.id
        run_obj.save()

    # Look for a data file and treat it differently
    data_entries = PlotData.objects.filter(data_run=run_obj)
    if len(data_entries) > 0:
        plot_data = data_entries[0]
    else:
        # No entry was found, create one
        plot_data = PlotData()
        plot_data.data_run = run_obj

    plot_data.data = plot
    plot_data.timestamp = timezone.now()
    plot_data.save()

    user_data, created = UserData.objects.get_or_create(user=request.user, file_id=run_obj.id, defaults={'timestamp': timezone.now()})
    if created:
        user_data.file_name = file_name
        user_data.timestamp = plot_data.timestamp
        user_data.save()

    return True, ""

def _remote_store(request, file_name, plot):
    """
        Store user data in a remove data server

        :param Request request: Django request object
        :param str file_name: name of the uploaded file
        :param str plot: user data, as a plotly json object
    """
    # Upload plot to live data server
    url_template = string.Template(settings.LIVE_DATA_USER_UPLOAD_URL)
    live_data_url = url_template.substitute(user=str(request.user),
                                            domain=settings.LIVE_DATA_SERVER_DOMAIN,
                                            port=settings.LIVE_DATA_SERVER_PORT)
    monitor_user = {'username': settings.LIVE_DATA_API_USER, 'password': settings.LIVE_DATA_API_PWD,
                    'data_id': file_name}
    files = {'file': plot}
    http_request = requests.post(live_data_url, data=monitor_user, files=files, verify=True)

    if http_request.status_code == 200:
        get_user_files_from_server(request, filter_file_name=file_name)
        return True, ""
    else:
        logging.error("Return code %s for %s:", http_request.status_code, live_data_url)
        return False, "Could not send data to server"

def get_plot_data_from_server(instrument, run_id, data_type='html'):
    """
        Retrieve data

        :param str instrument: instrument or user name
        :param int run_id: run id, usually the run number
        :param str data_type: type of data, always HTML but kept here for API compatibility
    """
    if 'datahandler' in settings.INSTALLED_APPS:
        return _local_fetch(instrument, run_id, data_type)
    else:
        return _remote_fetch(instrument, run_id, data_type)

def _local_fetch(instrument, run_id, data_type='html'):
    """
        Retrieve data locally

        :param str instrument: instrument or user name
        :param int run_id: run id, usually the run number
        :param str data_type: type of data, always HTML but kept here for API compatibility
    """
    # Get or create the instrument
    from datahandler.models import Instrument, DataRun, PlotData

    # Get or create the instrument
    instrument_obj, _ = Instrument.objects.get_or_create(name=instrument)

    # Get or create the run item
    run_list = DataRun.objects.filter(instrument=instrument_obj, run_number=run_id)
    if len(run_list) > 0:
        run_obj = run_list[0]
        plot_data_list = PlotData.objects.filter(data_run=run_obj)
        if len(plot_data_list) > 0:
            return plot_data_list[0].data
    return None

def _remote_fetch(instrument, run_id, data_type='html'):
    """
        Get json data from the live data server

        :param str instrument: instrument name
        :param int run_id: run number
        :param str data_type: data type, either 'json' or 'html'
    """
    json_data = None
    try:
        url_template = string.Template(settings.LIVE_DATA_SERVER)
        live_data_url = url_template.substitute(instrument=instrument, run_number=run_id)
        live_data_url += "/%s/" % data_type
        live_data_url = append_key(live_data_url, instrument, run_id)
        conn = httplib.HTTPSConnection(settings.LIVE_DATA_SERVER_DOMAIN, timeout=5.5)
        conn.request('GET', live_data_url)
        data_request = conn.getresponse()
        if data_request.status == 200:
            json_data = data_request.read()
        else:
            logging.error("Return code %s for %s:", data_request.status, live_data_url)
    except:
        logging.error("Could not pull data from live data server:\n%s", sys.exc_value)
    return json_data

def get_user_files_from_server(request, filter_file_name=None):
    """
        Get a list of the user's data on the live data server and update the local database

        :param Request request: request object
        :param str filter_file_name: If this parameter is not None, we will only update the entry with that file name
    """
    # If we are running locally, we have all the data we need
    if 'datahandler' in settings.INSTALLED_APPS:
        return

    try:
        # Upload plot to live data server
        url_template = string.Template(settings.LIVE_DATA_USER_FILES_URL)
        live_data_url = url_template.substitute(user=str(request.user),
                                                domain=settings.LIVE_DATA_SERVER_DOMAIN,
                                                port=settings.LIVE_DATA_SERVER_PORT)
        monitor_user = {'username': settings.LIVE_DATA_API_USER, 'password': settings.LIVE_DATA_API_PWD}
        http_request = requests.post(live_data_url, data=monitor_user, files={}, verify=True)

        data_list = json.loads(http_request.content)
        for item in data_list:
            if filter_file_name and not item['run_id'] == filter_file_name:
                continue
            user_data, created = UserData.objects.get_or_create(user=request.user, file_id=item['run_number'], defaults={'timestamp': timezone.now()})
            if created:
                user_data.file_name = item['run_id']
                user_data.timestamp = dateparse.parse_datetime(item['timestamp'])
                user_data.save()
    except:
        logging.error("Could not retrieve user files: %s", sys.exc_value)
