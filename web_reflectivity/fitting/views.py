#pylint: disable=bare-except, invalid-name, unused-argument, too-many-branches, too-many-nested-blocks, line-too-long, too-many-locals, too-many-ancestors
"""
    Definition of views
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import sys
import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.forms.formsets import formset_factory
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotFound
from django.views.generic.base import View
from django.views.generic.list import ListView
from django.views.generic.edit import UpdateView
from django.utils import dateformat, timezone
from django.utils.decorators import method_decorator

from django_remote_submission.models import Job
from .forms import ReflectivityFittingForm, LayerForm, UploadFileForm, ConstraintForm, layer_modelformset
from .models import FitProblem, FitterOptions, Constraint, ReflectivityLayer
from . import view_util
import users.view_util

@method_decorator(login_required, name='dispatch')
class FitterOptionsUpdate(UpdateView):
    """
        View to update the refl1d options
    """
    model = FitterOptions
    fields = ['steps', 'burn']
    template_name_suffix = '_update_form'

    def get(self, request, **kwargs):
        self.object, _ = FitterOptions.objects.get_or_create(user=self.request.user)
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        context = self.get_context_data(object=self.object, form=form)
        return self.render_to_response(context)

    def get_object(self, queryset=None):
        return FitterOptions.objects.get(user=self.request.user)

@login_required
def remove_constraint(request, instrument, data_id, const_id):
    """
        Remove a constraint
        @param request: request object
        @param instrument: instrument name
        @param data_id: data set identifier
        @param const_id: pk of the constraint object to delete
    """
    const_obj = get_object_or_404(Constraint, id=const_id)
    const_obj.delete()
    return redirect(reverse('fitting:constraints', args=(instrument, data_id)))

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

    def _get_template_values(self, request): #pylint: disable=no-self-use
        """ Return template dict """
        errors = []
        breadcrumbs = "<a href='/'>home</a> &rsaquo; data files"

        data = view_util.get_user_files(request)
        if data is None:
            errors.append("No user file found")
        template_values = {'breadcrumbs': breadcrumbs,
                           'file_list': data,
                           'user_alert': errors}
        return template_values

    def get(self, request, *args, **kwargs):
        """ Process a GET request """
        template_values = self._get_template_values(request)
        form = self.form_class()
        template_values['form'] = form
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, self.template_name, template_values)

    def post(self, request, *args, **kwargs):
        """ Process a POST request """
        template_values = self._get_template_values(request)
        form = self.form_class(request.POST, request.FILES)
        errors = []
        if form.is_valid():
            file_name = request.FILES['file'].name
            if request.FILES['file'].size < 1024 * 1024:
                raw_content = request.FILES['file'].read()
                success, error_msg = view_util.parse_ascii_file(request, file_name, raw_content)
                if success is True:
                    return redirect(reverse('fitting:show_files'))
                else:
                    errors.append(error_msg)
            else:
                errors.append("The uploaded file is too big.")
        template_values['form'] = form
        template_values['user_alert'] = errors
        return render(request, self.template_name, template_values)

@login_required
def download_reduced_data(request, instrument, data_id):
    """
        Download reduced data from live data server
        @param request: http request object
        @param instrument: instrument name
        @param run_id: run number
    """
    html_data = view_util.get_plot_data_from_server(instrument, data_id)
    ascii_data = view_util.extract_ascii_from_div(html_data)
    if ascii_data is None:
        error_msg = "Could not find data for %s/%s"  % (instrument, data_id)
        return HttpResponseNotFound(error_msg)
    ascii_data = "# %s Run %s\n# X Y dY dX\n%s" % (instrument.upper(), data_id, ascii_data)
    response = HttpResponse(ascii_data, content_type="text/plain")
    response['Content-Disposition'] = 'attachment; filename=%s_%s.txt' % (instrument.upper(), data_id)
    return response

@login_required
def download_fit_data(request, instrument, data_id, include_model=False):
    """
        Download reduced data and fit data from latest fit
        @param request: http request object
        @param instrument: instrument name
        @param run_id: run number
    """
    #TODO: Downloading data with the extra fit column is not really useful if you can loading in
    # another fit application. Eventually let the user choose whether they want the fit data.
    if not include_model:
        return download_reduced_data(request, instrument, data_id)

    ascii_data = view_util.get_fit_data(request, instrument, data_id)
    if ascii_data is None:
        return download_reduced_data(request, instrument, data_id)

    response = HttpResponse(ascii_data, content_type="text/plain")
    response['Content-Disposition'] = 'attachment; filename=%s_%s.txt' % (instrument.upper(), data_id)
    return response

@login_required
def download_model(request, instrument, data_id):
    """
        Download reduced data and fit data from latest fit
        @param request: http request object
        @param instrument: instrument name
        @param run_id: run number
    """
    ascii_data = view_util.get_model_as_csv(request, instrument, data_id)
    if ascii_data is None:
        ascii_data = "There is no model for this data: construct your model and click Evaluate first."
    response = HttpResponse(ascii_data, content_type="text/plain")
    response['Content-Disposition'] = 'attachment; filename=%s_%s_model.txt' % (instrument.upper(), data_id)
    return response

@login_required
def reverse_model(request, instrument, data_id):
    """
        Download reduced data and fit data from latest fit
        @param request: http request object
        @param instrument: instrument name
        @param run_id: run number
    """
    _, fit_problem = view_util.get_fit_problem(request, instrument, data_id)
    if fit_problem is not None:
        view_util.reverse_model(fit_problem)
    return redirect(reverse('fitting:fit', args=(instrument, data_id)))

@method_decorator(login_required, name='dispatch')
class FitListView(ListView):
    """
        List of fits
    """
    model = FitProblem
    template_name = 'fitting/fit_list.html'
    context_object_name = 'fit_list'

    def get_queryset(self):
        return FitProblem.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super(FitListView, self).get_context_data(**kwargs)
        errors = []
        if len(context) == 0:
            errors.append("No fit found")
        fit_list = []
        for item in context['fit_list']:
            localtime = timezone.localtime(item.timestamp)
            df = dateformat.DateFormat(localtime)
            fit_list.append({'id': item.id, 'layers': item.show_layers(), 'data': item.reflectivity_model.data_path,
                             'url': "<a href='%s%s' target='_blank'>click to fit</a>" % (reverse('fitting:modeling'),
                                                                                         item.reflectivity_model.data_path),
                             'timestamp': item.timestamp.isoformat(),
                             'created_on': df.format(settings.DATETIME_FORMAT)})
        context['json_list'] = json.dumps(fit_list)
        context['user_alert'] = errors
        context['breadcrumbs'] = "<a href='/'>home</a> &rsaquo; recent fits"
        return context

@method_decorator(login_required, name='dispatch')
class FitView(View):
    """
        View for data fitting
    """
    breadcrumbs = "<a href='/'>home</a> &rsaquo; reflectivity"

    def _fill_template_values(self, request, instrument, data_id, **template_args): #pylint: disable=no-self-use
        """ Get common template values """
        # Check whether we want to plot RQ^4 vs Q
        if 'rq4' in request.GET:
            rq4 = not request.GET.get('rq4', True) == '0'
            request.session['rq4'] = rq4
        else:
            rq4 = request.session.get('rq4', False)

        template_args['breadcrumbs'] = "%s  &rsaquo; %s &rsaquo; %s" % (self.breadcrumbs, instrument, data_id)
        template_args['instrument'] = instrument
        template_args['data_id'] = data_id
        template_args['rq4'] = rq4
        return template_args

    def get(self, request, instrument, data_id, *args, **kwargs):
        """
            Process GET
            @param request: request object
            @param instrument: instrument name
            @param data_id: data set identifier
        """
        is_allowed, run_info = view_util.check_permissions(request, data_id, instrument)
        if is_allowed is False:
            return redirect(reverse('fitting:private'))

        template_values = self._fill_template_values(request, instrument, data_id)

        # Check whether we need an extra layer
        default_extra = 0
        try:
            extra = int(request.GET.get('extra', default_extra))
        except:
            extra = default_extra

        error_message = []
        data_path, fit_problem = view_util.get_fit_problem(request, instrument, data_id)

        chi2, log_object, errors, can_update = view_util.get_results(request, fit_problem)
        error_message.extend(errors)
        if fit_problem is not None:
            data_form = ReflectivityFittingForm(instance=fit_problem.reflectivity_model)
        else:
            extra = 1
            data_form = ReflectivityFittingForm(initial={'data_path': data_path})

        LayerFormSet = layer_modelformset(extra=extra)
        layers_form = LayerFormSet(queryset = fit_problem.layers.all().order_by('layer_number') if fit_problem is not None else ReflectivityLayer.objects.none())

        html_data = view_util.get_plot_data_from_server(instrument, data_id)
        if html_data is None:
            error_message.append("Could not find data for %s/%s" % (instrument, data_id))
        html_data = view_util.assemble_plot(html_data, log_object, rq4=template_values['rq4'])

        number_of_constraints = Constraint.objects.filter(fit_problem=fit_problem).count()

        job_id = request.session.get('job_id', None)
        template_values.update({'data_form': data_form,
                                'html_data': html_data,
                                'user_alert': error_message,
                                'chi2': chi2,
                                'extra': extra,
                                'number_of_constraints': number_of_constraints,
                                'job_id': job_id if can_update else None,
                                'layers_form': layers_form})
        template_values['run_title'] = run_info.get('title', '')
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, 'fitting/modeling.html', template_values)

    def post(self, request, instrument, data_id, *args, **kwargs):
        """
            Process POST
            @param request: request object
            @param instrument: instrument name
            @param data_id: data set identifier
        """
        error_message = []
        # Check whether we need to redirect because the user changes the data path
        data_path = request.POST.get('data_path', '')
        instrument_, data_id_ = view_util.parse_data_path(data_path)
        if instrument_ is not None:
            instrument = instrument_
        if data_id_ is not None:
            data_id = data_id_

        is_allowed, run_info = view_util.check_permissions(request, data_id, instrument)
        if is_allowed is False: 
            return redirect(reverse('fitting:private'))

        template_values = self._fill_template_values(request, instrument, data_id)

        request.session['latest_data_path'] = data_path
        html_data = view_util.get_plot_data_from_server(instrument, data_id)
        if html_data is None:
            return redirect(reverse('fitting:fit', args=(instrument, data_id)))

        try:
            # See if we have a fit problem already
            fit_problem_list = FitProblem.objects.filter(user=request.user,
                                                         reflectivity_model__data_path=data_path)
            if len(fit_problem_list) > 0:
                reflectivity_model = fit_problem_list.latest('timestamp').reflectivity_model
            else:
                reflectivity_model = None

            data_form = ReflectivityFittingForm(request.POST, instance=reflectivity_model)
            LayerFormSet = layer_modelformset(extra=0)
            layers_form = LayerFormSet(request.POST)
            # Check for invalid form
            if data_form.is_valid() and layers_form.is_valid():
                task = request.POST.get('button_choice', 'fit')
                # Check for form submission option
                output = {}
                if task in ["evaluate", "fit"]:
                    if task == "evaluate" or view_util.is_fittable(data_form, layers_form):
                        output = view_util.evaluate_model(data_form, layers_form, html_data, fit=task == "fit", user=request.user, run_info=run_info)
                        if 'job_id' in output:
                            job_id = output['job_id']
                            request.session['job_id'] = job_id
                    else:
                        error_message.append("Your model needs at least one free parameter.")
                else:
                    view_util.save_fit_problem(data_form, layers_form, None, request.user)
                if 'error' in output:
                    error_message.append(output['error'])

                # Set the session data. This is the only thing we need
                # when requesting task = "set_data".
                #view_util.update_session(request, data_form, layers_form)
                if len(error_message) == 0:
                    return redirect(reverse('fitting:fit', args=(instrument, data_id)))
            else:
                error_message.append("Invalid parameters were found!")
        except:
            logging.error("Could not fit data: %s", sys.exc_value)
            error_message.append("Could not fit data")

        html_data = view_util.assemble_plot(html_data, None)
        template_values.update({'data_form': data_form,
                                'html_data': html_data,
                                'user_alert': error_message,
                                'instrument': instrument,
                                'data_id': data_id,
                                'layers_form': layers_form})
        template_values['run_title'] = run_info.get('title', '')
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, 'fitting/modeling.html', template_values)


@method_decorator(login_required, name='dispatch')
class ConstraintView(View):
    """
        View for data fitting
    """
    breadcrumbs = "<a href='/'>home</a> &rsaquo; constraint"

    @classmethod
    def _get_variable_choices(cls, fit_problem):
        variable_names = []
        params = fit_problem.model_to_dicts()
        for item in params:
            if isinstance(item, list):
                for layer in item:
                    if 'name' in layer:
                        v_name = "%s_%s" % (layer['name'], 'thickness')
                        variable_names.append((v_name, v_name))
                        v_name = "%s_%s" % (layer['name'], 'sld')
                        variable_names.append((v_name, v_name))
                        v_name = "%s_%s" % (layer['name'], 'roughness')
                        variable_names.append((v_name, v_name))
        return variable_names

    def _fill_template_values(self, request, instrument, data_id, const_id, **template_args): #pylint: disable=no-self-use
        """ Return template dict """
        data_path, fit_problem = view_util.get_fit_problem(request, instrument, data_id)
        if fit_problem is not None:
            initial_values, initial_layers = fit_problem.model_to_dicts()
        else:
            initial_layers = []
            initial_values = {'data_path': data_path}
        data_form = ReflectivityFittingForm(initial=initial_values)

        LayerFormSet = formset_factory(LayerForm, extra=0)
        layers_form = LayerFormSet(initial=initial_layers)

        # Find existing constraints
        constraint_list = Constraint.objects.filter(fit_problem=fit_problem)
        # Sanity check
        parameter_names = []
        error_message = []
        for item in constraint_list:
            p_name = "%s_%s" % (item.layer.name, item.parameter)
            if p_name in parameter_names:
                error_message.append("Parameter <b>%s</b> found more than once in the constraint list" % p_name)
            else:
                parameter_names.append(p_name)

        template_args['breadcrumbs'] = "%s  &rsaquo; %s &rsaquo; %s" % (self.breadcrumbs, instrument, data_id)
        template_args['instrument'] = instrument
        template_args['data_id'] = data_id
        template_args['layers_form'] = layers_form
        template_args['data_form'] = data_form
        template_args['constraint_list'] = constraint_list
        template_args['user_alert'] = error_message
        template_args['fit_problem'] = fit_problem

        return template_args

    def get(self, request, instrument, data_id, const_id=None, *args, **kwargs):
        """ Process GET """
        template_values = self._fill_template_values(request, instrument, data_id, const_id)
        fit_problem = template_values['fit_problem']

        const_init = {'definition': 'return 1'}
        if const_id is not None:
            constraint = get_object_or_404(Constraint, pk=const_id)
            const_init['definition'] = constraint.definition
            const_init['layer'] = constraint.layer
            const_init['parameter'] = constraint.parameter
            const_init['variables'] = [ v.strip() for v in constraint.variables.split(',')]

        constraint_form = ConstraintForm(initial=const_init)
        if fit_problem is not None:
            variable_names = self._get_variable_choices(fit_problem)
            constraint_form.fields['variables'].choices = variable_names
            constraint_form.fields['layer'].queryset = fit_problem.layers.all()
        else:
            template_values['user_alert'] = ["No model is available for this data.",
                                             "<a href='%s'>Create</a> and evaluate a model before adding a constraint." % reverse('fitting:fit', args=(instrument, data_id))]

        template_values['constraint_form'] = constraint_form
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, 'fitting/constraints.html', template_values)

    def post(self, request, instrument, data_id, const_id=None, *args, **kwargs):
        """ Process POST """
        template_values = self._fill_template_values(request, instrument, data_id, const_id)
        fit_problem = template_values['fit_problem']

        constraint_form = ConstraintForm(request.POST)
        variable_names = self._get_variable_choices(fit_problem)
        constraint_form.fields['layer'].queryset = fit_problem.layers.all()
        constraint_form.fields['variables'].choices = variable_names

        alerts = []
        form_errors = ""
        if constraint_form.is_valid():
            is_valid, alerts = Constraint.validate_constraint(constraint_form.cleaned_data['definition'],
                                                              constraint_form.cleaned_data['variables'])
            if is_valid:
                if const_id is not None:
                    constraint = get_object_or_404(Constraint, pk=const_id)
                else:
                    constraint = Constraint(user=request.user, fit_problem=fit_problem)
                constraint.layer=constraint_form.cleaned_data['layer']
                constraint.definition=constraint_form.cleaned_data['definition']
                constraint.parameter=constraint_form.cleaned_data['parameter']
                constraint.variables=','.join(constraint_form.cleaned_data['variables'])
                constraint.save()
                return redirect(reverse('fitting:constraints', args=(instrument, data_id)))
        else:
            alerts =  ["There were errors in the form, likely due to an old model: refresh your page"]
            form_errors = constraint_form.errors

        template_values['error_list'] = form_errors
        template_values['user_alert'] = alerts
        template_values['constraint_form'] = constraint_form
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, 'fitting/constraints.html', template_values)
