#pylint: disable=bare-except, invalid-name, too-many-nested-blocks, unused-argument, line-too-long, consider-using-enumerate
"""
    Utilities for modeling application
"""
import sys
import os
import time
import re
import io
import traceback
import json
import logging
import hashlib
import httplib
import pandas
import string
from django.conf import settings
from django_remote_submission.models import Server, Job, Log
from django_remote_submission.tasks import submit_job_to_server, LogPolicy

import plotly.offline as py
import plotly.graph_objs as go

from . import refl1d
from . import job_handling
from .models import FitProblem

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
        Extract data from a plot <div>.
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
                    ascii_data += u"%g %g %g %g\n" % (x[i], y[i], dy[i], dx[i])
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

def get_latest_results(data_path, initial_values, initial_layers, user):
    """
        Look for the latest results for this data set.
    """
    # Look for the latest job owned by the user corresponding to this data.
    logging.error("Looking for %s", data_path)
    user_jobs = Job.objects.filter(owner=user, title=data_path)
    if len(user_jobs) == 0:
        logging.error("Nothing found for %s", data_path)
        return initial_values, initial_layers, None, None
    latest_job = user_jobs.latest('id')
    logging.error("  - found %s", latest_job.id)
    for job in user_jobs:
        if not job == latest_job:
            logging.error("remove job %s", job.id)
            #job.delete()

    # Find the latest log for that job
    #TODO: what if the latest job was not successful? How do we report errors?
    job_logs = Log.objects.filter(job=latest_job)
    if len(job_logs) == 0:
        logging.error("nothing found for %s", latest_job.id)
        return initial_values, initial_layers, None, None
    latest = job_logs.latest('time')
    for job in job_logs:
        if not job == latest:
            logging.error("Deleting log %s", job.id)
            #job.delete()

    initial_values, initial_layers, chi2 = refl1d.get_latest_results(latest.content, initial_values, initial_layers)
    return initial_values, initial_layers, chi2, latest

def assemble_plot(html_data, log_object):
    """
        @param log_object: remote job Log object
    """
    data_list = []
    data_names = []
    # Check that the latest fit really corresponds to the latest data
    current_str = io.StringIO(extract_ascii_from_div(html_data))
    current_data = pandas.read_csv(current_str, delim_whitespace=True, comment='#', names=['q','r','dr','dq'])
    data_list.append([current_data['q'], current_data['r'], current_data['dr']])
    data_names.append("Data")

    # Extract data from log object
    if log_object is not None:
        data_log = refl1d.extract_data_from_log(log_object.content)
        if data_log is not None:
            data_str = io.StringIO(data_log)
            raw_data = pandas.read_csv(data_str, delim_whitespace=True, comment='#', names=['q','dq','r','dr','theory','fresnel'])
            data_list.append([raw_data['q'], raw_data['theory']])
            data_names.append("Fit")

    return plot1d(data_list, data_names=data_names, x_title=u"Q (1/\u212b)", y_title="Reflectivity")

def is_fittable(data_form, layers_form):
    has_free = data_form.has_free_parameter()
    for layer in layers_form:
        has_free = has_free or layer.has_free_parameter()
    return has_free

def evaluate_model(data_form, layers_form, html_data, fit=True, user=None):
    try:
        return _evaluate_model(data_form, layers_form, html_data, fit=fit, user=user)
    except:
        traceback.print_exc()
        logging.error("Problem evaluating model: %s", sys.exc_value)
        return {'error': "Problem evaluating model: %s" % sys.exc_value}

def _evaluate_model(data_form, layers_form, html_data, fit=True, user=None):
    ascii_data = extract_ascii_from_div(html_data)
    work_dir = os.path.join(settings.REFL1D_JOB_DIR, user.username)
    output_dir = os.path.join(settings.REFL1D_JOB_DIR, user.username, 'fit')
    script = job_handling.create_model_file(data_form, layers_form,
                                            data_file=os.path.join(work_dir, '__data.txt'), ascii_data=ascii_data,
                                            output_dir=output_dir, fit=fit)

    server = Server.objects.get_or_create(title='Analysis', hostname=settings.JOB_HANDLING_HOST,  port=22)[0]

    job = Job.objects.get_or_create(title=data_form.cleaned_data['data_path'], #'Reflectivity fit %s' % time.time(),
                                    program=script,
                                    remote_directory=work_dir,
                                    remote_filename='fit_job.py',
                                    owner=user,
                                    server=server)[0]
    submit_job_to_server.delay(
        job_pk=job.pk,
        password='',
        username=user.username,
        log_policy=LogPolicy.LOG_TOTAL
    )

    # Save this fit job
    save_fit_problem(data_form, layers_form, job, user)
    return {'jod_id': job.pk}

def save_fit_problem(data_form, layers_form, job_object, user):
    # Save the ReflectivityModel object
    ref_model = data_form.save()
    fit_problem = FitProblem(user=user, reflectivity_model=ref_model,
                             remote_job=job_object)
    fit_problem.save()

    # Save the layer parameters
    for layer in layers_form:
        logging.error("layer")
        l_object = layer.save()
        fit_problem.layers.add(l_object)
    fit_problem.save()
    return fit_problem

def plot1d(data_list, data_names=None, x_title='', y_title='',
           x_log=True, y_log=True, show_dx=False):
    """
        Produce a 1D plot
        @param data_list: list of traces [ [x1, y1], [x2, y2], ...]
        @param data_names: name for each trace, for the legend
    """
    # Create traces
    if not isinstance(data_list, list):
        raise RuntimeError("plot1d: data_list parameter is expected to be a list")

    # Catch the case where the list is in the format [x y]
    data = []
    show_legend = False
    if len(data_list) == 2 and not isinstance(data_list[0], list):
        label = ''
        if isinstance(data_names, list) and len(data_names) == 1:
            label = data_names[0]
            show_legend = True
        data = [go.Scatter(name=label, x=data_list[0], y=data_list[1])]
    else:
        for i in range(len(data_list)):
            label = ''
            if isinstance(data_names, list) and len(data_names) == len(data_list):
                label = data_names[i]
                show_legend = True
            err_x = {}
            err_y = {}
            if len(data_list[i]) >= 3:
                err_y = dict(type='data', array=data_list[i][2], visible=True)
            if len(data_list[i]) >= 4:
                err_x = dict(type='data', array=data_list[i][3], visible=True)
                if show_dx is False:
                    err_x['thickness'] = 0

            if len(err_y) == 0:
                data.append(go.Scatter(name=label, x=data_list[i][0], y=data_list[i][1],
                                       error_x=err_x, error_y=err_y,
                                       line=dict(color="rgb(102, 102, 102)",width=2)))
            else:
                data.append(go.Scatter(name=label, x=data_list[i][0], y=data_list[i][1],
                                       error_x=err_x, error_y=err_y))


    x_layout = dict(title=x_title, zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True,
                    showline=True, mirror="all", ticks="inside")
    if x_log:
        x_layout['type'] = 'log'
    y_layout = dict(title=y_title, zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True,
                    showline=True, mirror="all", ticks="inside")
    if y_log:
        y_layout['type'] = 'log'

    layout = go.Layout(
        showlegend=show_legend,
        autosize=True,
        width=700,
        height=400,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode='closest',
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout
    )

    fig = go.Figure(data=data, layout=layout)
    plot_div = py.plot(fig, output_type='div', include_plotlyjs=False, show_link=False)
    return plot_div
