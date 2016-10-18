#pylint: disable=bare-except, invalid-name, too-many-nested-blocks, unused-argument, line-too-long, consider-using-enumerate
"""
    Utilities for modeling application
"""
import sys
import os
import re
import json
import logging
import hashlib
import httplib
import string
from django.conf import settings
from . import job_handling

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

def extract_ascii_from_div(html_data):
    """
        Extract data from an plot <div>.
        Only returns the first one it finds.
        @param html_data: <div> string
    """
    try:
        result = re.search(r"newPlot\((.*)\)</script>", html_data)
        jsondata_str = "[%s]" % result.group(1)
        data_list = json.loads(jsondata_str)
        ascii_data = ""
        for d in data_list:
            if isinstance(d, list):
                for trace in d:
                    if 'type' in trace and trace['type'] == 'scatter':
                        x = trace['x']
                        y = trace['y']
                        dx = [0]*len(x)
                        dy = [0]*len(y)
                        if 'error_x' in trace and 'array' in trace['error_x']:
                            dx = trace['error_x']['array']
                        if 'error_y' in trace and 'array' in trace['error_y']:
                            dy = trace['error_y']['array']
                        break
                for i in range(len(x)):
                    ascii_data += "%g %g %g %g\n" % (x[i], y[i], dy[i], dx[i])
                return ascii_data
    except:
        # Unable to extract data from <div>
        logging.debug("Unable to extract data from <div>: %s", sys.exc_value)
    return None

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

    if len(layers) == 0:
        request.session['layers_form_values'] = []
    else:
        if 'layer_number' in layers[0]:
            sorted_layers = sorted(layers, key=lambda l: l['layer_number'])
        else:
            sorted_layers = layers

        for i in range(len(sorted_layers)):
            sorted_layers[i]['layer_number'] = i+1

        request.session['layers_form_values'] = sorted_layers

def perform_fit():
    return None

def evaluate_model(data_form, layers_form, html_data):
    ascii_data = extract_ascii_from_div(html_data)
    data_file = '/tmp/__data.txt'
    with open(data_file, 'w') as fd:
        fd.write(ascii_data)
    model_file = job_handling.create_model_file(data_form, layers_form, data_file)
    output_dir = '/tmp/fit'

    cmd = "/Library/Frameworks/Python.framework/Versions/2.7/bin/refl1d_gui.py --fit=dream --steps=100 --burn=15 --store=%s %s --batch --parallel &> %s/__fit.log" % (output_dir, model_file, output_dir)
    os.system(cmd)
    #report_fit(output_dir)

    return None