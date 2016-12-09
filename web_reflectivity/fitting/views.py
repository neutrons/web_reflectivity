#pylint: disable=bare-except, invalid-name
"""
    Definition of views
"""
import sys
import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.forms.formsets import formset_factory
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from .forms import ReflectivityFittingForm, LayerForm
from django_remote_submission.models import Job
from . import view_util

import users.view_util


@login_required
def modeling(request):

    # Get data from user input
    # If post, then update the data for this user
    # You can either load a file or point to livedata.sns.gov using a URL

    # If we upload data, keep a sha so we can verify that it hasn't changed
    breadcrumbs = "<a href='/'>home</a> &rsaquo; reflectivity"
    default_extra = 0
    try:
        extra = int(request.GET.get('extra', default_extra))
    except:
        extra = default_extra

    html_data = ''
    log_object = None
    chi2 = None
    job_id = request.session.get('job_id', None)

    error_message = []
    if request.method == 'POST':
        data_path = request.POST.get('data_path', '')
        if not view_util.check_permissions(request, data_path, settings.DEFAULT_INSTRUMENT):
            return redirect(reverse('fitting:private'))

        request.session['latest_data_path'] = data_path
        try:
            html_data = view_util.get_plot_data_from_server(settings.DEFAULT_INSTRUMENT, data_path)
            data_form = ReflectivityFittingForm(request.POST)
            LayerFormSet = formset_factory(LayerForm, extra=extra, can_order=True)
            layers_form = LayerFormSet(request.POST)
            # Check for invalid form
            if data_form.is_valid() and layers_form.is_valid():
                task = request.POST.get('button_choice', 'fit')
                # Check for form submission option
                output = {}
                if task in ["evaluate", "fit"]:
                    if view_util.is_fittable(data_form, layers_form):
                        output = view_util.evaluate_model(data_form, layers_form, html_data, fit=task == "fit", user=request.user)
                        if 'job_id' in output:
                            job_id = output['job_id']
                            request.session['job_id'] = job_id
                    else:
                        error_message.append("Your model needs at least one free parameter.")
                if 'error' in output:
                    error_message.append(output['error'])

                # Set the session data. This is the only thing we need
                # when requesting task = "set_data".
                view_util.update_session(request, data_form, layers_form)
                if len(error_message) == 0:
                    return redirect(reverse('fitting:modeling'))
        except:
            logging.error("Could not get data from live data server: %s", sys.exc_value)
            html_data = "<b>Could not get data from live data server</b>"
    else:
        data_path, fit_problem = view_util.get_latest_fit(request)
        if not view_util.check_permissions(request, data_path, settings.DEFAULT_INSTRUMENT):
            return redirect(reverse('fitting:private'))
        initial_values, initial_layers, chi2, log_object, errors, can_update = view_util.get_results(request, fit_problem)
        error_message.extend(errors)
        data_form = ReflectivityFittingForm(initial=initial_values)

        if initial_layers == {}:
            extra = 1
        LayerFormSet = formset_factory(LayerForm, extra=extra)
        layers_form = LayerFormSet(initial=initial_layers)

    # Get plot data if we don't have it already (through POST)
    # If we have fit results, overplot it.
    if len(html_data) == 0:
        try:
            html_data = view_util.get_plot_data_from_server(settings.DEFAULT_INSTRUMENT, data_path)
        except:
            logging.error("Could not get data from live data server: %s", sys.exc_value)

    html_data = view_util.assemble_plot(html_data, log_object)

    template_values = {'breadcrumbs': breadcrumbs,
                       'data_form': data_form,
                       'html_data': html_data,
                       'user_alert': error_message,
                       'chi2': chi2,
                       'job_id': job_id if can_update else None,
                       'layers_form': layers_form}
    template_values = users.view_util.fill_template_values(request, **template_values)
    return render(request, 'fitting/modeling.html', template_values)

@login_required
def private(request):
    return render(request, 'fitting/private.html', {'instrument': settings.DEFAULT_INSTRUMENT,
                                                    'helpline': settings.HELPLINE})

@login_required
def is_completed(request, job_id):
    """
    """
    job_object = get_object_or_404(Job, pk=job_id)
    return_value = {'status': job_object.status,
                    'completed': job_object.status in [job_object.STATUS.success,
                                                       job_object.STATUS.failure]}
    response = HttpResponse(json.dumps(return_value), content_type="application/json")
    return response