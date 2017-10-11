#pylint: disable=bare-except, invalid-name, too-many-statements, too-many-nested-blocks, unused-argument, line-too-long, consider-using-enumerate, too-many-arguments, too-many-locals, too-many-branches
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
import pandas

import numpy as np
from django.conf import settings
from django.utils import dateformat, timezone
from django_remote_submission.models import Server, Job, Log, Interpreter
from django_remote_submission.tasks import submit_job_to_server, LogPolicy
from django.core.urlresolvers import reverse
from django.http import Http404

import plotly.offline as py
import plotly.graph_objs as go

from .parsing import refl1d
from . import job_handling
from .data_server import data_handler
from . import icat_server_communication as icat
from .models import FitProblem, FitterOptions, Constraint, ReflectivityLayer, UserData, SimultaneousModel, SimultaneousConstraint, SimultaneousFit
from .forms import ReflectivityFittingForm, LayerForm
import users.view_util

def extract_ascii_from_div(html_data):
    """
        Extract data from a plot <div>.
        Only returns the first one it finds.

        :param str html_data: <div> string
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

def check_permissions(request, run_id, instrument):
    """
        Verify that the user has the permissions to access the data

        :param str run_id: run identifier (usually a number)
        :param str instrument: instrument name, or user name
    """
    # When the user is accessing their own data, the instrument is set to the username
    if instrument == str(request.user):
        return True, {}

    # Get the IPTS from ICAT
    try:
        run_info = icat.get_run_info(instrument, run_id)
        if 'proposal' in run_info:
            return users.view_util.is_experiment_member(request, instrument, run_info['proposal']), run_info
        else:
            return request.user.is_staff, {}
    except:
        # The data probably doesn't exist
        return False, None
    return False, run_info

def get_fit_problem(request, instrument, data_id):
    """
        Get the latest FitProblem object for an instrument/data pair

        :param str data_id: run identifier (usually a number)
        :param str instrument: instrument name, or user name
    """
    data_path = "%s/%s" % (instrument, data_id)
    fit_problem_list = FitProblem.objects.filter(user=request.user,
                                                 reflectivity_model__data_path=data_path)
    if len(fit_problem_list) > 0:
        fit_problem = fit_problem_list.latest('timestamp')
        if len(fit_problem_list) > 1:
            logging.error("DB corruption: >1 FitProblems for %s/%s", instrument, data_id)
            for fitp in fit_problem_list:
                logging.error("  FitProblem [%s] [ReflModel %s] %s",
                              fitp.id, fitp.reflectivity_model.id, fitp.timestamp)

        return data_path, fit_problem
    return data_path, None

def get_fit_data(request, instrument, data_id):
    """
        Get the latest ascii data from

        :param str data_id: run identifier (usually a number)
        :param str instrument: instrument name, or user name
    """
    ascii_data = None
    _, fit_problem = get_fit_problem(request, instrument, data_id)
    if fit_problem is not None:
        job_logs = Log.objects.filter(job=fit_problem.remote_job)
        if len(job_logs) > 0:
            latest = job_logs.latest('time')
            ascii_data = refl1d.extract_data_from_log(latest.content)
    return ascii_data

def get_model_as_csv(request, instrument, data_id):
    """
        Return an ASCII block with model information to be loaded
        in third party applications.

        :param str data_id: run identifier (usually a number)
        :param str instrument: instrument name, or user name
    """
    ascii_data = None
    _, fit_problem = get_fit_problem(request, instrument, data_id)
    if fit_problem is not None:
        model_dict, layer_dicts = fit_problem.model_to_dicts()
        ascii_data = "# Reflectivity model\n"
        ascii_data += "# Created on %s\n" % fit_problem.timestamp
        ascii_data += "# Created by the ORNL Reflectivity Fitting Interface [DOI: 10.5281/zenodo.260178]\n"
        ascii_data += "# Data File: %s\n\n" % fit_problem.reflectivity_model.data_path
        ascii_data += "# SCALE\n"
        ascii_data += "scale = %g\n" % model_dict['scale']
        ascii_data += "background = %g\n\n" % model_dict['background']
        ascii_data += "# %8s %24s %12s %12s %12s %12s\n" % ('LAYER', 'NAME', 'THICK', 'SLD', 'iSLD', 'ROUGH')
        ascii_data += "  %8s %24s %12s %12s %12s\n" % ('FRONT', model_dict['front_name'],
                                                       0, model_dict['front_sld'], 0)
        for layer in layer_dicts:
            ascii_data += "  %8s %24s %12s %12s %12s %12s\n" % (layer['layer_number'], layer['name'],
                                                           layer['thickness'], layer['sld'],
                                                           layer['i_sld'], layer['roughness'])

        ascii_data += "  %8s %24s %12s %12s %12s\n" % ('BACK', model_dict['back_name'],
                                                       0, model_dict['back_sld'],
                                                       model_dict['back_roughness'])

    return ascii_data

def get_results(request, fit_problem):
    """
        Get the model parameters for a given fit problem

        :param FitProblem fit_problem: FitProblem object
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

def get_plot_from_html(html_data, rq4=False):
    """
        Process html data and return plot data

        :param str html_data: stored json for plotted data
        :param bool rq4: if True, the plot will be in R*Q^4
    """
    current_str = io.StringIO(extract_ascii_from_div(html_data))
    current_data = pandas.read_csv(current_str, delim_whitespace=True, comment='#', names=['q','r','dr','dq'])
    if rq4 is True:
        r_values = current_data['r'] * current_data['q']**4
        dr_values = current_data['dr'] * current_data['q']**4
    else:
        r_values = current_data['r']
        dr_values = current_data['dr']
    return [current_data['q'], r_values, dr_values]

def get_plot_from_job_report(log_object, rq4=False):
    """
        Obtain job log and extract plot data

        :param Log log_object: Log object for a given remote job
        :param bool rq4: if True, the plot will be in R*Q^4
    """
    refl_plot = None
    sld_plot = None
    if log_object is not None:
        # Extract reflectivity
        data_log = refl1d.extract_data_from_log(log_object.content)
        if data_log is not None:
            data_str = io.StringIO(data_log)
            raw_data = pandas.read_csv(data_str, delim_whitespace=True, comment='#', names=['q','dq','r','dr','theory','fresnel'])
            if rq4 is True:
                fit_values = raw_data['theory'] * raw_data['q']**4
            else:
                fit_values = raw_data['theory']
            refl_plot = [raw_data['q'], fit_values]
        # Extract SLD
        data_log = refl1d.extract_sld_from_log(log_object.content)
        if data_log is not None:
            data_str = io.StringIO(data_log)
            raw_data = pandas.read_csv(data_str, delim_whitespace=True, comment='#', names=['z','rho','irho'])
            sld_plot = [raw_data['z'], raw_data['rho']]
    return refl_plot, sld_plot

def assemble_plots(request, instrument, data_id, fit_problem, rq4=False):
    """
        Find all that needs to be plotted for this fit problem.

        :param str instrument: instrument name, or user name
        :param str data_id: run identifier (usually a number)
        :param FitProblem fit_problem: FitProblem object
        :param bool rq4: if True, the plot will be in R*Q^4
    """
    data_list = []
    data_names = []
    sld_list = []
    sld_names = []
    r_plot = ""
    # Find the data
    html_data = data_handler.get_plot_data_from_server(instrument, data_id)
    # If we can't retrieve data from the plot server, then the data doesn't exist and
    # we should return a 404.
    if html_data is None:
        raise Http404

    data_list.append(get_plot_from_html(html_data, rq4))
    data_names.append("Data")

    # Extract data from log object
    _, log_object, _, _ = get_results(request, fit_problem)
    fit_plot, sld_plot = get_plot_from_job_report(log_object, rq4)
    if fit_plot is not None:
        data_list.append(fit_plot)
        data_names.append("Fit")
    if sld_plot is not None:
        sld_list.append(sld_plot)
        sld_names.append("SLD")

    # Extra data
    extra_data = find_overlay_data(fit_problem)
    for extra_name, extra_html in extra_data:
        # Add the data itself
        data_list.append(get_plot_from_html(extra_html, rq4))
        data_names.append(extra_name)
        # Add fit result if it exists
        instrument_, data_id_ = parse_data_path(extra_name)
        _, extra_fit = get_fit_problem(request, instrument_, data_id_)
        _, log_extra, _, _ = get_results(request, extra_fit)
        fit_plot, sld_plot = get_plot_from_job_report(log_extra, rq4)
        if fit_plot is not None:
            data_list.append(fit_plot)
            data_names.append(extra_name)
        if sld_plot is not None:
            sld_list.append(sld_plot)
            sld_names.append(extra_name)

    y_title=u"Reflectivity"
    if rq4 is True:
        y_title += u" x Q<sup>4</sup> (1/\u212b<sup>4</sup>)"

    if len(data_list) > 0:
        r_plot = plot1d(data_list, data_names=data_names, x_title=u"Q (1/\u212b)", y_title=y_title)

    if len(sld_list) > 0:
        sld_plot = plot1d(sld_list, x_log=False, y_log=False,
                          data_names=sld_names, x_title=u"Z (\u212b)",
                          y_title='SLD (10<sup>-6</sup>/\u212b<sup>2</sup>)')
        r_plot = "<div>%s</div><div>%s</div>" % (r_plot, sld_plot)

    return r_plot

def find_overlay_data(fit_problem):
    """
        Find extra data to be over-plotted for a given fit problem.

        :param FitProblem fit_problem: FitProblem object
    """
    simult_data = []
    for item in SimultaneousModel.objects.filter(fit_problem=fit_problem):
        instrument_, data_id_ = parse_data_path(item.dependent_data)
        html_data = data_handler.get_plot_data_from_server(instrument_, data_id_)
        if html_data is not None:
            simult_data.append([item.dependent_data, html_data])
    return simult_data

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

def evaluate_model(data_form, layers_form, html_data, fit=True, user=None, run_info=None):
    """
        Protected version of the call to refl1d
    """
    try:
        return _evaluate_model(data_form, layers_form, html_data, fit=fit, user=user, run_info=run_info)
    except:
        traceback.print_exc()
        logging.error("Problem evaluating model: %s", sys.exc_value)
        return {'error': "Problem evaluating model: %s" % sys.exc_value}

def _evaluate_model(data_form, layers_form, html_data, fit=True, user=None, run_info=None):
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

    fit_dir = 'reflectivity_fits'
    if run_info is not None and 'proposal' in run_info:
        fit_dir = os.path.join(fit_dir, run_info['proposal'])

    ascii_data = extract_ascii_from_div(html_data)
    work_dir = os.path.join(settings.REFL1D_JOB_DIR, user.username)
    output_dir = os.path.join(work_dir, fit_dir, base_name)
    # Get fitter options
    options = {}
    if user is not None:
        obj, _ = FitterOptions.objects.get_or_create(user=user)
        options = obj.get_dict()

    template = 'reflectivity_model.py.template'
    #TODO: bypass fitting but retrieve all the info we need.
    #if not fit:
    #    template = 'reflectivity_theory_model.py.template'
    script = job_handling.create_model_file(data_form, layers_form, template=template,
                                            data_file=os.path.join(work_dir, '__data.txt'), ascii_data=ascii_data,
                                            output_dir=output_dir, fit=fit, options=options, constraints=constraint_list)

    server = Server.objects.get_or_create(title='Analysis', hostname=settings.JOB_HANDLING_HOST, port=settings.JOB_HANDLING_PORT)[0]

    python_path = settings.JOB_HANDLING_INTERPRETER
    if settings.JOB_HANDLING_HOST == 'localhost':
        python_path = sys.executable
    python2_interpreter = Interpreter.objects.get_or_create(name='python2', path=python_path)[0]
    server.interpreters.set([python2_interpreter,])

    job = Job.objects.get_or_create(title=data_form.cleaned_data['data_path'], #'Reflectivity fit %s' % time.time(),
                                    program=script,
                                    remote_directory=work_dir,
                                    remote_filename='fit_job.py',
                                    owner=user,
                                    interpreter=python2_interpreter,
                                    server=server)[0]
    submit_job_to_server.delay(
        job_pk=job.pk,
        password='',
        username=user.username,
        log_policy=LogPolicy.LOG_TOTAL,
        store_results='',
        remote = not settings.JOB_HANDLING_HOST == 'localhost'
    )

    # Update the remote job info
    fit_problem.remote_job = job
    fit_problem.save()
    return {'job_id': job.pk}

def _process_fit_problem(fit_problem, instrument, data_id, options, work_dir, output_dir):
    """ Utility method to get all the info from a fit problem """
    # First the parent data set
    initial_values, initial_layers = fit_problem.model_to_dicts()
    layers_form = []
    errors = []
    for layer in initial_layers:
        layer_form = LayerForm(layer)
        if layer_form.is_valid():
            layers_form.append(layer_form)
        else:
            errors.append("Layer %s was invalid" % layer['layer_number'])

    data_form = ReflectivityFittingForm(initial_values)
    constraint_list = Constraint.objects.filter(fit_problem=fit_problem)

    html_data = data_handler.get_plot_data_from_server(instrument, data_id)
    ascii_data = extract_ascii_from_div(html_data)

    script = ''
    if data_form.is_valid():
        data_file = os.path.join(work_dir, '__data%s.txt' % fit_problem.id)
        expt_name = 'expt%s' % fit_problem.id
        script = job_handling.create_model_file(data_form, layers_form,
                                                data_file=data_file, ascii_data=ascii_data,
                                                output_dir=output_dir, fit=True, options=options, constraints=constraint_list,
                                                template='simultaneous_model.py.template',
                                                sample_name='sample%s' % fit_problem.id, probe_name='probe%s' % fit_problem.id,
                                                expt_name=expt_name)
    else:
        errors.append("Reflectivity fitting object was invalid")
    return script, [data_file, ascii_data], expt_name, errors

def evaluate_simultaneous_fit(request, instrument, data_id, run_info):
    """
        Assemble all the information for co-refinement
    """
    error_list = []
    data_path, fit_problem = get_fit_problem(request, instrument, data_id)
    # Decide on an output directory
    try:
        base_name = os.path.split(data_path)[1]
    except:
        base_name = data_path
    if run_info is not None and 'proposal' in run_info:
        fit_dir = os.path.join('reflectivity_fits', run_info['proposal'], 'simultaneous')
    else:
        fit_dir = os.path.join('reflectivity_fits', 'simultaneous')

    work_dir = os.path.join(settings.REFL1D_JOB_DIR, request.user.username)
    output_dir = os.path.join(work_dir, fit_dir, base_name)
    # Get fitter options
    obj, _ = FitterOptions.objects.get_or_create(user=request.user)
    options = obj.get_dict()

    data_files = []
    expt_names = []
    data_ids = []
    # Process the parent data set
    script_models = "\n# run %s/%s #############################################################\n" % (instrument, data_id)
    script_part, data, expt_name, errors = _process_fit_problem(fit_problem, instrument, data_id, options, work_dir, output_dir)
    script_models += script_part
    data_files.append(data)
    expt_names.append(expt_name)
    error_list.extend(errors)
    data_ids.append(data_path)

    # Then the data sets appended to the parent data set
    #TODO: check is_active
    for item in SimultaneousModel.objects.filter(fit_problem=fit_problem):
        instrument_, data_id_ = parse_data_path(item.dependent_data)
        _, extra_fit = get_fit_problem(request, instrument_, data_id_)
        script_models += "\n# run %s/%s #############################################################\n" % (instrument_, data_id_)
        script_part, data, expt_name, errors = _process_fit_problem(extra_fit, instrument_, data_id_, options, work_dir, output_dir)
        script_models += script_part
        data_files.append(data)
        expt_names.append(expt_name)
        error_list.extend(errors)
        data_ids.append(item.dependent_data)

    # Now the constraints
    script_models += "\n# Constraints ##################################################################\n"
    for item in SimultaneousConstraint.objects.filter(fit_problem=fit_problem, user=request.user):
        script_models += item.get_constraint(sample_name='sample') + '\n'

    data_script = job_handling.assemble_data_setup(data_files)
    job_script = job_handling.assemble_job(script_models, data_script, expt_names, data_ids, options, work_dir, output_dir)

    # Submit job
    server = Server.objects.get_or_create(title='Analysis', hostname=settings.JOB_HANDLING_HOST, port=settings.JOB_HANDLING_PORT)[0]

    python_path = settings.JOB_HANDLING_INTERPRETER
    if settings.JOB_HANDLING_HOST == 'localhost':
        python_path = sys.executable
    python2_interpreter = Interpreter.objects.get_or_create(name='python2', path=python_path)[0]
    server.interpreters.set([python2_interpreter,])

    job = Job.objects.get_or_create(title=data_path,
                                    program=job_script,
                                    remote_directory=work_dir,
                                    remote_filename='fit_job.py',
                                    owner=request.user,
                                    interpreter=python2_interpreter,
                                    server=server)[0]
    submit_job_to_server.delay(
        job_pk=job.pk,
        password='',
        username=request.user.username,
        log_policy=LogPolicy.LOG_TOTAL,
        store_results='',
        remote = not settings.JOB_HANDLING_HOST == 'localhost'
    )

    # Update the remote job info
    simul_fit, _ = SimultaneousFit.objects.get_or_create(user=request.user, fit_problem=fit_problem)
    simul_fit.remote_job = job
    simul_fit.save()

    return dict(job_id=job.pk, error_list=error_list)

def save_fit_problem(data_form, layers_form, job_object, user):
    """
        Save the state of the model forms
    """
    # Save the ReflectivityModel object
    ref_model = data_form.save()
    fit_problem_list = FitProblem.objects.filter(user=user,
                                                 reflectivity_model__data_path=data_form.cleaned_data['data_path'])
    fit_created = False
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
        fit_created = True
    fit_problem.save()
    fit_problem.layers.clear()

    # Save the layer parameters
    for layer in layers_form:
        if 'remove' in layer.cleaned_data and layer.cleaned_data['remove'] is False:
            # The object ID is part of the form, so if we changed the dataset
            # while submitting (if we had to create a new FitProblem), then
            # we need to copy the layers, not update them.
            # We also need to copy over any existing constraint.
            if fit_created:
                c_list = Constraint.objects.filter(layer=layer.cleaned_data['id'])
                layer.cleaned_data['id'] = None
                l_object = ReflectivityLayer.objects.create(**(layer.cleaned_data))
                if len(c_list) > 0:
                    Constraint.objects.create(user=c_list[0].user,
                                              fit_problem=fit_problem,
                                              definition=c_list[0].definition,
                                              layer=l_object,
                                              parameter=c_list[0].parameter,
                                              variables=c_list[0].variables)
            else:
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

def apply_model(fit_problem, saved_model, instrument, data_id):
    """
        Apply a saved model to a fit problem
    """
    data_path = "%s/%s" % (instrument.lower().strip(), data_id.lower().strip())
    if fit_problem is not None:
        data_path = fit_problem.reflectivity_model.data_path

    # Make a copy of the ReflectivityModel object
    ref_model = saved_model.fit_problem.reflectivity_model
    ref_model.pk = None
    ref_model.data_path = data_path
    ref_model.save()

    if fit_problem is not None:
        old_model = fit_problem.reflectivity_model
        fit_problem.reflectivity_model = ref_model
        fit_problem.remote_job = None
        fit_problem.save()
        old_model.delete()
    else:
        fit_problem = FitProblem(user=saved_model.user, reflectivity_model=ref_model)
        fit_problem.save()

    # Copy over the layers
    fit_problem.layers.clear()
    for layer in saved_model.fit_problem.layers.all().order_by('layer_number'):
        layer.id = None
        layer.pk = None
        layer.save()
        fit_problem.layers.add(layer)

    fit_problem.save()
    return fit_problem

def model_hash(fit_problem):
    """
        Return a secret hash for a given fit problem
    """
    h = hashlib.sha1()
    h.update("%s%s%s" % (fit_problem.id, fit_problem.reflectivity_model.id, fit_problem.user))
    return h.hexdigest()

def copy_fit_problem(fit_problem, user):
    """
        Make a duplicate copy of a FitProblem object
    """
    # Make a copy of the ReflectivityModel object
    ref_model = fit_problem.reflectivity_model
    ref_model.pk = None
    ref_model.data_path = "saved"
    ref_model.save()

    # Create a new FitProblem object
    fit_problem_copy = FitProblem(user=user, reflectivity_model=ref_model)
    fit_problem_copy.save()

    # Copy over the layers
    for layer in fit_problem.layers.all().order_by('layer_number'):
        layer.id = None
        layer.pk = None
        layer.save()
        fit_problem_copy.layers.add(layer)

    fit_problem_copy.save()
    return fit_problem_copy

def plot1d(data_list, data_names=None, x_title='', y_title='',
           x_log=True, y_log=True, show_dx=False):
    """
        Produce a 1D plot
        :param data_list: list of traces [ [x1, y1], [x2, y2], ...]
        :param data_names: name for each trace, for the legend
    """
    # Skipping this nice blue pair for the nicer blue/gray 'rgb(166,206,227)', 'rgb(31,120,180)'
    colors = ['#1f77b4', 'rgb(102,102,102)', 'rgb(178,223,138)', 'rgb(51,160,44)', 'rgb(251,154,153)', 'rgb(227,26,28)', 'rgb(253,191,111)', 'rgb(255,127,0)', 'rgb(202,178,214)', 'rgb(106,61,154)', 'rgb(255,255,153)', 'rgb(177,89,40)']
    # Create traces
    if not isinstance(data_list, list):
        raise RuntimeError("plot1d: data_list parameter is expected to be a list")

    # Catch the case where the list is in the format [x y]
    data = []
    n_data = -2
    n_fit = -1
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
                n_data += 2
                err_y = dict(type='data', array=data_list[i][2], visible=True, color=colors[n_data%12])
            else:
                n_fit += 2
            if len(data_list[i]) >= 4:
                err_x = dict(type='data', array=data_list[i][3], visible=True, color=colors[n_data%12])
                if show_dx is False:
                    err_x['thickness'] = 0

            if len(err_y) == 0:
                data.append(go.Scatter(name=label, x=data_list[i][0], y=data_list[i][1],
                                       error_x=err_x, error_y=err_y,
                                       line=dict(color=colors[n_fit%12],width=2)))
            else:
                data.append(go.Scatter(name=label, x=data_list[i][0], y=data_list[i][1],
                                       mode='markers', marker=dict(color=colors[n_data%12]),
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
        width=850,
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
        :param Request request: http request object
        :param str file_name: name of the uploaded file
        :param str raw_content: content of the file
    """
    try:
        # If we don't have a fourth column, add 3% Q resolution
        current_str = io.StringIO(unicode(raw_content))
        current_data = pandas.read_csv(current_str, delim_whitespace=True, comment='#', names=['q','r','dr','dq'])
        data_set = [current_data['q'], current_data['r'], current_data['dr'], current_data['dq']]
        for i in range(len(current_data['dq'])):
            if np.isnan(current_data['dq'][i]):
                current_data['dq'][i] = current_data['q'][i] * 0.03

        # Package the data in a plot
        plot = plot1d([data_set], data_names=file_name, x_title=u"Q (1/\u212b)", y_title="Reflectivity")

        # Upload plot to live data server
        return data_handler.store_user_data(request, file_name, plot)
    except:
        logging.error("Could not parse file %s: %s", file_name, sys.exc_value)
        return False, "Could not parse data file %s" % file_name

def get_user_files(request):
    """
        Get list of uploaded files

        :param Request request: http request object
    """
    user_data = UserData.objects.filter(user=request.user)
    if len(user_data) == 0:
        logging.warning("Syncing files for user %s", request.user)
        data_handler.get_user_files_from_server(request)
        user_data = UserData.objects.filter(user=request.user)

    data_list = []
    for item in user_data:
        update_url = "<a href='%s'><span style='display:inline-block' class='ui-icon ui-icon-pencil'></span></a>" % reverse('fitting:data_info', args=(str(request.user), item.file_id))
        delete_url = "<a href='%s'><span style='display:inline-block' class='ui-icon ui-icon-trash'></span></a>" % reverse('fitting:data_delete', args=(item.id,))
        fit_url = "<a href='%s' target='_blank'>click to fit</a>" % reverse('fitting:fit', args=(str(request.user), item.file_id))

        localtime = timezone.localtime(item.timestamp)
        df = dateformat.DateFormat(localtime)

        data_item = dict(id=item.file_id,
                         run_number=item.file_id,
                         run_id="<span id='%s/%s' draggable='true' ondragstart='drag(event)'>%s</span>" % (request.user, item.file_id, item.file_name),
                         timestamp=item.timestamp.isoformat(),
                         created_on=df.format(settings.DATETIME_FORMAT),
                         url="%s | %s %s" % (fit_url, update_url, delete_url),
                         tags=item.tags)
        data_list.append(data_item)

    return json.dumps(data_list)

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

def reverse_model(fit_problem):
    """
        Reverse a layer model
    """
    front_name = fit_problem.reflectivity_model.front_name
    front_sld = fit_problem.reflectivity_model.front_sld
    front_sld_is_fixed = fit_problem.reflectivity_model.front_sld_is_fixed
    front_sld_min = fit_problem.reflectivity_model.front_sld_min
    front_sld_max = fit_problem.reflectivity_model.front_sld_max
    front_sld_error = fit_problem.reflectivity_model.front_sld_error

    fit_problem.reflectivity_model.front_name = fit_problem.reflectivity_model.back_name
    fit_problem.reflectivity_model.front_sld = fit_problem.reflectivity_model.back_sld
    fit_problem.reflectivity_model.front_sld_is_fixed = fit_problem.reflectivity_model.back_sld_is_fixed
    fit_problem.reflectivity_model.front_sld_min = fit_problem.reflectivity_model.back_sld_min
    fit_problem.reflectivity_model.front_sld_max = fit_problem.reflectivity_model.back_sld_max
    fit_problem.reflectivity_model.front_sld_error = fit_problem.reflectivity_model.back_sld_error

    fit_problem.reflectivity_model.back_name = front_name
    fit_problem.reflectivity_model.back_sld = front_sld
    fit_problem.reflectivity_model.back_sld_is_fixed = front_sld_is_fixed
    fit_problem.reflectivity_model.back_sld_min = front_sld_min
    fit_problem.reflectivity_model.back_sld_max = front_sld_max
    fit_problem.reflectivity_model.back_sld_error = front_sld_error

    layers = [l.id for l in fit_problem.layers.all().order_by('layer_number')]
    count = fit_problem.layers.all().count()

    if count > 0:
        _roughness = fit_problem.reflectivity_model.back_roughness
        _roughness_is_fixed = fit_problem.reflectivity_model.back_roughness_is_fixed
        _roughness_min = fit_problem.reflectivity_model.back_roughness_min
        _roughness_max = fit_problem.reflectivity_model.back_roughness_max
        _roughness_error = fit_problem.reflectivity_model.back_roughness_error

        layer = ReflectivityLayer.objects.get(id=layers[0])
        fit_problem.reflectivity_model.back_roughness = layer.roughness
        fit_problem.reflectivity_model.back_roughness_is_fixed = layer.roughness_is_fixed
        fit_problem.reflectivity_model.back_roughness_min = layer.roughness_min
        fit_problem.reflectivity_model.back_roughness_max = layer.roughness_max
        fit_problem.reflectivity_model.back_roughness_error = layer.roughness_error

    fit_problem.reflectivity_model.save()
    fit_problem.remote_job = None
    fit_problem.save()

    # Reorder the layers
    for i in range(count):
        layer = ReflectivityLayer.objects.get(id=layers[i])
        layer.layer_number = count - i
        if i == count-1:
            layer.roughness = _roughness
            layer.roughness_is_fixed = _roughness_is_fixed
            layer.roughness_min = _roughness_min
            layer.roughness_max = _roughness_max
            layer.roughness_error = _roughness_error
        else:
            prev_layer = ReflectivityLayer.objects.get(id=layers[i+1])
            layer.roughness = prev_layer.roughness
            layer.roughness_is_fixed = prev_layer.roughness_is_fixed
            layer.roughness_min = prev_layer.roughness_min
            layer.roughness_max = prev_layer.roughness_max
            layer.roughness_error = prev_layer.roughness_error
        layer.save()
