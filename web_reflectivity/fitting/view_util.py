#pylint: disable=bare-except, invalid-name, too-many-nested-blocks, unused-argument, line-too-long, consider-using-enumerate
"""
    Utilities for modeling application
"""
import sys
import logging
import hashlib
import httplib
import string
from django.conf import settings

def generate_key(instrument, run_id):
    """
        Generate a secret key for a run on a given instrument
        @param instrument: instrument name
        @param run_id: run number
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
        @param input_url: url to modify
        @param instrument: instrument name
        @param run_id: run number
    """
    client_key = generate_key(instrument, run_id)
    if client_key is None:
        return input_url
    # Determine whether this is the first query string argument of the url
    delimiter = '&' if '/?' in input_url else '?'
    return "%s%skey=%s" % (input_url, delimiter, client_key)


def get_plot_data_from_server(instrument, run_id, data_type='html'):
    """
        Get json data from the live data server
        @param instrument: instrument name
        @param run_id: run number
        @param data_type: data type, either 'json' or 'html'
    """
    json_data = None
    try:
        url_template = string.Template(settings.LIVE_DATA_SERVER)
        live_data_url = url_template.substitute(instrument=instrument, run_number=run_id)
        live_data_url += "/%s/" % data_type
        live_data_url = append_key(live_data_url, instrument, run_id)
        conn = httplib.HTTPSConnection(settings.LIVE_DATA_SERVER_DOMAIN, timeout=1.5)
        conn.request('GET', live_data_url)
        data_request = conn.getresponse()
        if data_request.status == 200:
            json_data = data_request.read()
        else:
            logging.error("Return code %s for %s:", data_request.status, live_data_url)
    except:
        logging.error("Could not pull data from live data server:\n%s", sys.exc_value)
    return json_data

def update_session(request, data_form, layers_form):
    """
    """
    if not data_form.is_valid() or not layers_form.is_valid():
        logging.error("update_session: Forms are invalid: cannot update session information")
        return
    request.session['data_form_values'] = data_form.cleaned_data
    layers = []

    for item in layers_form.cleaned_data:
        if 'remove' in item and item['remove'] is False:
            layers.append(item)

    if 'layer_number' in layers[0]:
        sorted_layers = sorted(layers, key=lambda l: l['layer_number'])
    else:
        sorted_layers = layers

    for i in range(len(sorted_layers)):
        sorted_layers[i]['layer_number'] = i+1

    request.session['layers_form_values'] = sorted_layers


def perform_fit():
    return None

def evaluate_model():
    return None