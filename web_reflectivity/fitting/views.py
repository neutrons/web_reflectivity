#pylint: disable=bare-except, invalid-name, unused-argument, too-many-branches, too-many-nested-blocks, line-too-long
"""
    Definition of views
"""
import sys
import logging
import json
from django.shortcuts import render, redirect, get_object_or_404, Http404
from django.forms.formsets import formset_factory
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.generic.base import View
from django.utils.decorators import method_decorator

from .forms import ReflectivityFittingForm, LayerForm, UploadFileForm
from django_remote_submission.models import Job
from . import view_util

import users.view_util

@login_required
def landing_page(request):
    """
        Landing page for the app. Redirects to the last fit.
    """
    data_path = request.session.get('latest_data_path', None)
    toks = data_path.split('/')
    if len(toks) == 2:
        instrument = toks[0]
        data_id = toks[1]
        return redirect(reverse('fitting:fit', args=(instrument, data_id)))
    raise Http404()

@login_required
def private(request):
    """
        Return the page telling the user that the data is private.
    """
    return render(request, 'fitting/private.html', {'instrument': settings.DEFAULT_INSTRUMENT,
                                                    'helpline': settings.HELPLINE})

@login_required
def is_completed(request, job_id):
    """
        AJAX call to know whether a job is complete.
        @param job_id: pk of the Job object
    """
    job_object = get_object_or_404(Job, pk=job_id)
    return_value = {'status': job_object.status,
                    'completed': job_object.status in [job_object.STATUS.success,
                                                       job_object.STATUS.failure]}
    response = HttpResponse(json.dumps(return_value), content_type="application/json")
    return response

@method_decorator(login_required, name='dispatch')
class FileView(View):
    """
        Process a file request
    """
    form_class = UploadFileForm
    template_name = 'fitting/files.html'

    def get(self, request, *args, **kwargs):
        """ Process a GET request """
        errors = []
        breadcrumbs = "<a href='/'>home</a> &rsaquo; data files"

        data = view_util.get_user_files(request)
        if data is None:
            errors.append("No user files found")
        form = self.form_class()
        template_values = {'breadcrumbs': breadcrumbs,
                           'file_list': data,
                           'form': form,
                           'user_alert': errors}
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, self.template_name, template_values)

    def post(self, request, *args, **kwargs):
        """ Process a POST request """
        form = self.form_class(request.POST, request.FILES)
        errors = []
        if form.is_valid():
            file_name = request.FILES['file'].name
            raw_content = request.FILES['file'].read()
            success, error_msg = view_util.parse_ascii_file(request, file_name, raw_content)
            if success is True:
                return redirect(reverse('fitting:show_files'))
            else:
                errors.append(error_msg)
        return render(request, self.template_name, {'form': form,
                                                    'user_alert': errors})


@method_decorator(login_required, name='dispatch')
class FitView(View):
    """
        View for data fitting
    """
    breadcrumbs = "<a href='/'>home</a> &rsaquo; reflectivity"

    def get(self, request, instrument, data_id, *args, **kwargs):
        """ Process GET """
        if not view_util.check_permissions(request, data_id, instrument):
            return redirect(reverse('fitting:private'))

        # Check whether we need an extra layer
        default_extra = 0
        try:
            extra = int(request.GET.get('extra', default_extra))
        except:
            extra = default_extra

        # Check whether we want to plot RQ^4 vs Q
        if 'rq4' in request.GET:
            rq4 = not request.GET.get('rq4', True) == '0'
            request.session['rq4'] = rq4
        else:
            rq4 = request.session.get('rq4', False)

        error_message = []
        data_path, fit_problem = view_util.get_fit_problem(request, instrument, data_id)

        initial_values, initial_layers, chi2, log_object, errors, can_update = view_util.get_results(request, data_path, fit_problem)
        error_message.extend(errors)
        data_form = ReflectivityFittingForm(initial=initial_values)

        if initial_layers == {}:
            extra = 1
        LayerFormSet = formset_factory(LayerForm, extra=extra)
        layers_form = LayerFormSet(initial=initial_layers)

        html_data = view_util.get_plot_data_from_server(instrument, data_id)
        if html_data is None:
            error_message.append("Could not find data for %s/%s" % (instrument, data_id))
        html_data = view_util.assemble_plot(html_data, log_object, rq4=rq4)

        job_id = request.session.get('job_id', None)
        template_values = {'breadcrumbs': "%s  &rsaquo; %s &rsaquo; %s" % (self.breadcrumbs, instrument, data_id),
                           'data_form': data_form,
                           'html_data': html_data,
                           'user_alert': error_message,
                           'chi2': chi2,
                           'rq4': rq4,
                           'instrument': instrument,
                           'data_id': data_id,
                           'job_id': job_id if can_update else None,
                           'layers_form': layers_form}
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, 'fitting/modeling.html', template_values)

    def post(self, request, instrument, data_id, *args, **kwargs):
        """ Process POST """
        if not view_util.check_permissions(request, data_id, instrument):
            return redirect(reverse('fitting:private'))

        error_message = []
        # Check whether we need to redirect because the user changes the data path
        data_path = request.POST.get('data_path', '')
        toks = data_path.split('/')
        if len(toks) == 1 and len(toks[0]) > 0:
            data_id = toks[0]
        elif len(toks) == 2 and len(toks[0]) > 0 and len(toks[1]) > 0:
            instrument = toks[0]
            data_id = toks[1]

        request.session['latest_data_path'] = data_path
        html_data = view_util.get_plot_data_from_server(instrument, data_id)
        if html_data is None:
            return redirect(reverse('fitting:fit', args=(instrument, data_id)))

        try:
            data_form = ReflectivityFittingForm(request.POST)
            LayerFormSet = formset_factory(LayerForm, extra=0, can_order=True)
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
                    return redirect(reverse('fitting:fit', args=(instrument, data_id)))
            else:
                error_message.append("Invalid parameters were found!")
        except:
            logging.error("Could not fit data: %s", sys.exc_value)
            error_message.append("Could not fit data")

        html_data = view_util.assemble_plot(html_data, None)
        template_values = {'breadcrumbs':  "%s  &rsaquo; %s &rsaquo; %s" % (self.breadcrumbs, instrument, data_id),
                           'data_form': data_form,
                           'html_data': html_data,
                           'user_alert': error_message,
                           'layers_form': layers_form}
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, 'fitting/modeling.html', template_values)
