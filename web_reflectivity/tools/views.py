#pylint: disable=bare-except, line-too-long, invalid-name, too-many-arguments, unused-argument
"""
    Tools for reflectivity
"""
import sys
import logging
from django.shortcuts import render
from django.views.generic.base import View
from .forms import ChargeRateForm
import users.view_util

class ChargeRateView(View):
    """
        Compute capacity and charge rates.
    """
    form_class = ChargeRateForm
    template_name = 'tools/charge_rate.html'
    breadcrumbs = "<a href='/'>home</a> &rsaquo; capacity"

    def get(self, request, *args, **kwargs):
        """ Process a GET request """
        template_values = dict(form=self.form_class(),
                               breadcrumbs=self.breadcrumbs)
        template_values = users.view_util.fill_template_values(request, **template_values)
        return render(request, self.template_name, template_values)

    def post(self, request, *args, **kwargs):
        """ Process a POST request """
        form = self.form_class(request.POST)

        template_values = dict(form=form, breadcrumbs=self.breadcrumbs)
        template_values = users.view_util.fill_template_values(request, **template_values)

        if form.is_valid():
            try:
                electrode_info = form.capacity()
                if electrode_info is None:
                    template_values['user_alert'] = ["Could not process request.", "Check your density value."]
                else:
                    template_values.update(electrode_info)
            except:
                logging.error(sys.exc_value)
                template_values['user_alert']= ["Could not process request.", "Check your density value.", sys.exc_value]
        else:
            template_values['user_alert']= ["The form contains invalid data"]

        return render(request, self.template_name, template_values)

