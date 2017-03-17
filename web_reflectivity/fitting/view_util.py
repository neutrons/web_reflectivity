#pylint: disable=bare-except, invalid-name, too-many-nested-blocks, unused-argument, line-too-long, consider-using-enumerate, too-many-arguments, too-many-locals, too-many-branches
"""
    Utilities for modeling application
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import sys
import os
import re
import io
import traceback
import json
import logging
import hashlib
import httplib
import pandas
import requests
import string
from django.conf import settings
from django_remote_submission.models import Server, Job, Log, Interpreter
from django_remote_submission.tasks import submit_job_to_server, LogPolicy
from django.core.urlresolvers import reverse

import plotly.offline as py
import plotly.graph_objs as go

from . import refl1d
from . import job_handling
from . import icat_server_communication as icat
from .models import FitProblem, FitterOptions, Constraint

import users.view_util

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
        #TODO: clean this up
        Update the session information with the latest fit
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

def check_permissions(request, run_id, instrument):
    """
        Verify that the user has the permissions to access the data
    """
    # When the user is accessing their own data, the instrument is set to the username
    if instrument == str(request.user):
        return True, {}

    # Get the IPTS from ICAT
    run_info = icat.get_run_info(instrument, run_id)
    if 'proposal' in run_info:
        return users.view_util.is_experiment_member(request, instrument, run_info['proposal']), run_info
    else:
        return request.user.is_staff, {}
    return False, run_info

def get_fit_problem(request, instrument, data_id):
    """
        Get the latest FitProblem object for an instrument/data pair
    """
    data_path = "%s/%s" % (instrument, data_id)
    fit_problem_list = FitProblem.objects.filter(user=request.user,
                                                 reflectivity_model__data_path=data_path)
    if len(fit_problem_list) > 0:
        fit_problem = fit_problem_list.latest('timestamp')

        # Cleanup
        #TODO: make sure we can remove the following block of code
        #job_id = request.session.get('job_id', None)
        #for item in fit_problem_list:
        #    if not item == fit_problem and not item.id == job_id:
        #        logging.debug("Cleaning old FitProblem %s [curr: %s]", item.id, fit_problem.id)
        #        delete_problem(item)

        return data_path, fit_problem
    return data_path, None

def get_fit_data(request, instrument, data_id):
    """
        Get the latest ascii data from
    """
    ascii_data = None
    _, fit_problem = get_fit_problem(request, instrument, data_id)
    if fit_problem is not None:
        job_logs = Log.objects.filter(job=fit_problem.remote_job)
        if len(job_logs) > 0:
            latest = job_logs.latest('time')
            ascii_data = refl1d.extract_data_from_log(latest.content)
    return ascii_data

def delete_problem(fit_problem):
    """
        Remove a FitProblem and all its related entries from the database
        @param fit_problem: FitProblem ojbect
    """
    # Only delete jobs that are not active
    try:
        if fit_problem.remote_job.status not in [fit_problem.remote_job.STATUS.success,
                                                 fit_problem.remote_job.STATUS.failure]:
            return

        # Delete the reflectivity model objects
        for item in fit_problem.layers.all():
            #fit_problem.layers.remove(item)
            item.delete()

        fit_problem.reflectivity_model.delete()

        # Delete the job
        fit_problem.remote_job.delete()
    except:
        logging.error("Could not retrieve object: %s", sys.exc_value)
        return

def get_results(request, fit_problem):
    """
        Get the model parameters for a given fit problem
    """
    errors = []
    chi2 = None
    latest = None
    can_update = False
    if fit_problem is not None:
        if fit_problem.remote_job is not None:
            try:
                #TODO: what if the latest job was not successful? How do we report errors?
                can_update = fit_problem.remote_job.status not in [fit_problem.remote_job.STATUS.success,
                                                                   fit_problem.remote_job.STATUS.failure]
                errors.append("Job status: %s" % fit_problem.remote_job.status)
                job_logs = Log.objects.filter(job=fit_problem.remote_job)
                if len(job_logs) > 0:
                    latest = job_logs.latest('time')
                    for job in job_logs:
                        if not job == latest:
                            logging.error("Logs for job %s needs cleaning up", job.id)
                            #job.delete()

                    chi2 = refl1d.update_model(latest.content, fit_problem)
                    for item in Constraint.objects.filter(fit_problem=fit_problem):
                        item.apply_constraint(fit_problem)
                    if chi2 is None:
                        errors.append("The fit results appear to be incomplete.")
                        can_update = False
                else:
                    errors.append("No results found")
            except:
                logging.error("Problem retrieving results: %s", sys.exc_value)
                errors.append("Problem retrieving results")
        else:
            errors.append("No result for this model")
    else:
        errors.append("No model found for this data set")

    return chi2, latest, errors, can_update

def assemble_plot(html_data, log_object, rq4=False):
    """
        @param log_object: remote job Log object
    """
    data_list = []
    data_names = []
    # Check that the latest fit really corresponds to the latest data
    current_str = io.StringIO(extract_ascii_from_div(html_data))
    current_data = pandas.read_csv(current_str, delim_whitespace=True, comment='#', names=['q','r','dr','dq'])
    if rq4 is True:
        r_values = current_data['r'] * current_data['q']**4
        dr_values = current_data['dr'] * current_data['q']**4
    else:
        r_values = current_data['r']
        dr_values = current_data['dr']
    data_list.append([current_data['q'], r_values, dr_values])
    data_names.append("Data")

    # Extract data from log object
    if log_object is not None:
        data_log = refl1d.extract_data_from_log(log_object.content)
        if data_log is not None:
            data_str = io.StringIO(data_log)
            raw_data = pandas.read_csv(data_str, delim_whitespace=True, comment='#', names=['q','dq','r','dr','theory','fresnel'])
            if rq4 is True:
                fit_values = raw_data['theory'] * raw_data['q']**4
            else:
                fit_values = raw_data['theory']
            data_list.append([raw_data['q'], fit_values])
            data_names.append("Fit")

    y_title=u"Reflectivity"
    if rq4 is True:
        y_title += u" x Q<sup>4</sup> (1/\u212b<sup>4</sup>)"
    return plot1d(data_list, data_names=data_names, x_title=u"Q (1/\u212b)", y_title=y_title)

def is_fittable(data_form, layers_form):
    """
        Return True if a fit problem (comprised of all its forms)
        is fittable or not. To be fittable, refl1d requires at least
        one free parameter.
    """
    has_free = data_form.has_free_parameter()
    for layer in layers_form:
        has_free = has_free or layer.has_free_parameter()
    return has_free

def evaluate_model(data_form, layers_form, html_data, fit=True, user=None):
    """
        Protected version of the call to refl1d
    """
    try:
        return _evaluate_model(data_form, layers_form, html_data, fit=fit, user=user)
    except:
        traceback.print_exc()
        logging.error("Problem evaluating model: %s", sys.exc_value)
        return {'error': "Problem evaluating model: %s" % sys.exc_value}

def _evaluate_model(data_form, layers_form, html_data, fit=True, user=None):
    """
        Refl1d fitting job
    """
    # Save the model first
    fit_problem = save_fit_problem(data_form, layers_form, None, user)
    constraint_list = Constraint.objects.filter(fit_problem=fit_problem)

    try:
        base_name = os.path.split(data_form.cleaned_data['data_path'])[1]
    except:
        base_name = data_form.cleaned_data['data_path']

    ascii_data = extract_ascii_from_div(html_data)
    work_dir = os.path.join(settings.REFL1D_JOB_DIR, user.username)
    output_dir = os.path.join(settings.REFL1D_JOB_DIR, user.username, 'reflectivity_fits', base_name)
    # Get fitter options
    options = {}
    if user is not None:
        obj, _ = FitterOptions.objects.get_or_create(user=user)
        options = obj.get_dict()

    script = job_handling.create_model_file(data_form, layers_form,
                                            data_file=os.path.join(work_dir, '__data.txt'), ascii_data=ascii_data,
                                            output_dir=output_dir, fit=fit, options=options, constraints=constraint_list)

    server = Server.objects.get_or_create(title='Analysis', hostname=settings.JOB_HANDLING_HOST, port=settings.JOB_HANDLING_POST)[0]

    python2_interpreter = Interpreter.objects.get_or_create(name='python2',
                                                            path=settings.JOB_HANDLING_INTERPRETER)[0]
    server.interpreters.set([python2_interpreter,])

    job = Job(title=data_form.cleaned_data['data_path'], #'Reflectivity fit %s' % time.time(),
                                    program=script,
                                    remote_directory=work_dir,
                                    remote_filename='fit_job.py',
                                    owner=user,
                                    interpreter=python2_interpreter,
                                    server=server)
    job.save()
    submit_job_to_server.delay(
        job_pk=job.pk,
        password='',
        username=user.username,
        log_policy=LogPolicy.LOG_TOTAL,
        store_results=''
    )

    # Update the remote job info
    fit_problem.remote_job = job
    fit_problem.save()
    return {'job_id': job.pk}

def save_fit_problem(data_form, layers_form, job_object, user):
    """
        Save the state of the model forms
    """
    # Save the ReflectivityModel object
    ref_model = data_form.save()
    fit_problem_list = FitProblem.objects.filter(user=user,
                                                 reflectivity_model__data_path=data_form.cleaned_data['data_path'])
    if len(fit_problem_list) > 0:
        fit_problem = fit_problem_list.latest('timestamp')
        # Replace foreign keys
        old_job = fit_problem.remote_job
        fit_problem.remote_job = job_object
        fit_problem.reflectivity_model = ref_model
        # Clean up previous data that is now obsolete
        if old_job is not None:
            old_job.delete()
    else:
        fit_problem = FitProblem(user=user, reflectivity_model=ref_model,
                                 remote_job=job_object)
    fit_problem.save()
    fit_problem.layers.clear()

    # Save the layer parameters
    for layer in layers_form:
        if 'remove' in layer.cleaned_data and layer.cleaned_data['remove'] is False:
            l_object = layer.save()
            fit_problem.layers.add(l_object)

    # Reorder the layers
    i = 0
    for layer in fit_problem.layers.all().order_by('layer_number'):
        i += 1
        layer.layer_number = i
        layer.save()

    fit_problem.save()
    return fit_problem

def plot1d(data_list, data_names=None, x_title='', y_title='',
           x_log=True, y_log=True, show_dx=False):
    """
        #TODO: no connecting line for data
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
                                       mode='markers', error_x=err_x, error_y=err_y))


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

def parse_ascii_file(request, file_name, raw_content):
    """
        Process an uploaded data file
        @param request: http request object
        @param file_name: name of the uploaded file
        @param raw_content: content of the file
    """
    try:
        current_str = io.StringIO(unicode(raw_content))
        current_data = pandas.read_csv(current_str, delim_whitespace=True, comment='#', names=['q','r','dr','dq'])
        data_set = [current_data['q'], current_data['r'], current_data['dr'], current_data['dq']]

        # Package the data in a plot
        plot = plot1d([data_set], data_names=file_name, x_title=u"Q (1/\u212b)", y_title="Reflectivity")

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
            return True, ""
        else:
            logging.error("Return code %s for %s:", http_request.status_code, live_data_url)
            return False, "Could not send data to server"
    except:
        logging.error("Could not parse file %s: %s", file_name, sys.exc_value)
        return False, "Could not parse data file %s" % file_name

def get_user_files(request):
    """
        Get a list of the user's data on the live data server
    """
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
            item['url'] = "<a href='%s' target='_blank'>click to fit</a>" % reverse('fitting:fit', args=(str(request.user), item['run_number']))
        return json.dumps(data_list)
    except:
        logging.error("Could not retrieve user files: %s", sys.exc_value)
        return None

def parse_data_path(data_path):
    """
        Parse a data path of the form <instrument>/<data>
    """
    instrument = None
    data_id = None
    toks = data_path.split('/')
    if len(toks) == 1 and len(toks[0]) > 0:
        data_id = toks[0]
    elif len(toks) == 2 and len(toks[0]) > 0 and len(toks[1]) > 0:
        instrument = toks[0]
        data_id = toks[1]
    return instrument, data_id

