#pylint: disable=bare-except, invalid-name
"""
    Definition of views
"""
import sys
import logging
from django.shortcuts import render, redirect
from django.forms.formsets import formset_factory
from django.core.urlresolvers import reverse
from django.conf import settings

from .forms import ReflectivityFittingForm, LayerForm
from . import view_util
from . import job_handling

def modeling(request):

    # Get data from user input
    # If post, then update the data for this user
    # You can either load a file or point to livedata.sns.gov using a URL

    # If we upload data, keep a sha so we can verify that it hasn't changed

    default_extra = 0
    try:
        extra = int(request.GET.get('extra', default_extra))
    except:
        extra = default_extra

    html_data = ''
    if request.method == 'POST':
        data_path = request.POST.get('data_path', '')
        try:
            html_data = view_util.get_plot_data_from_server(settings.DEFAULT_INSTRUMENT, data_path)
        except:
            logging.error("Could not get data from live data server: %s", sys.exc_value)
        data_form = ReflectivityFittingForm(request.POST)
        LayerFormSet = formset_factory(LayerForm, extra=extra)
        layers_form = LayerFormSet(request.POST)
        # Check for invalid form
        if data_form.is_valid() and layers_form.is_valid():
            task = request.POST.get('button_choice', 'fit')
            # Check for form submission option
            if task == "evaluate":
                # Process the form and evaluate the model (no fit)
                view_util.evaluate_model(data_form, layers_form, html_data)
            elif task == "fit":
                m=job_handling.create_model_file(data_form, layers_form)
                logging.error(m)
                # Process the form and fit data
                view_util.perform_fit()
            # Set the session data. This is the only thing we need
            # when requesting task = "set_data".
            view_util.update_session(request, data_form, layers_form)
            return redirect(reverse('fitting:modeling'))
    else:
        initial_values = request.session.get('data_form_values', {})
        data_path = initial_values.get('data_path', '')
        data_form = ReflectivityFittingForm(initial=initial_values)

        initial_layers = request.session.get('layers_form_values', {})
        if initial_layers == {}:
            extra = 1
        LayerFormSet = formset_factory(LayerForm, extra=extra)
        layers_form = LayerFormSet(initial=initial_layers)

    if len(html_data) == 0:
        try:
            html_data = view_util.get_plot_data_from_server(settings.DEFAULT_INSTRUMENT, data_path)
        except:
            logging.error("Could not get data from live data server: %s", sys.exc_value)

    template_values = {'data_form': data_form,
                       'html_data': html_data,
                       'layers_form': layers_form}
    return render(request, 'fitting/modeling.html', template_values)

