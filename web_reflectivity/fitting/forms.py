#pylint: disable=line-too-long
"""
    Forms for auto-reduction configuration

    @author: M. Doucet, Oak Ridge National Laboratory
    @copyright: 2014 Oak Ridge National Laboratory
"""
from django import forms
from django.core.exceptions import ValidationError

import sys
import re
import logging
from django.templatetags.l10n import localize


class ValueErrorField(forms.Field):
    #widget = forms.NumberInput
    default_error_messages = {
        'invalid': 'Enter a whole number.',
    }
    re_decimal = re.compile(r'\.0*\s*$')
    plus_minus = '+-'

    def to_python(self, value):
        """
        Validates that float() can be called on the input. Returns the result
        of float(). Returns None for empty values.
        """
        # Look for +- string. If we find it, strip everything after it.
        value_as_string = str(value)
        pm_location = value_as_string.find(self.plus_minus)
        if pm_location > 0:
            value_as_string = value_as_string[:pm_location].strip()
        try:
            value = float(value_as_string)
        except:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return super(ValueErrorField, self).to_python(value)

    def validate(self, value):
        self.to_python(value)


class ReflectivityFittingForm(forms.Form):
    """
        Generic form for DGS reduction instruments
    """
    data_path = forms.CharField(required=False, initial='/plots/ref_l/144761/update/html/', widget=forms.TextInput(attrs={'class' : 'font_resize'}))
    scale = ValueErrorField(required=True, initial=1.0)
    scale_is_fixed = forms.BooleanField(required=False, initial=True)
    scale_min = forms.FloatField(required=False)
    scale_max = forms.FloatField(required=False)

    background = forms.FloatField(required=True, initial=0.0)
    background_is_fixed = forms.BooleanField(required=False, initial=True)
    background_min = forms.FloatField(required=False)
    background_max = forms.FloatField(required=False)

class LayerForm(forms.Form):
    """
        Simple form for a layer
    """
    name = forms.CharField(required=False, initial='new layer')
    thickness = forms.FloatField(required=True, initial=15.0)
    sld = forms.FloatField(required=True, initial=3.2)
    roughness = forms.FloatField(required=True, initial=1.0)
    remove = forms.BooleanField(required=False, initial=False)
    layer_number = forms.IntegerField(initial=1000)

    # Fitting information
    thickness_is_fixed = forms.BooleanField(required=False, initial=True)
    thickness_min = forms.FloatField(required=False)
    thickness_max = forms.FloatField(required=False)

    sld_is_fixed = forms.BooleanField(required=False, initial=True)
    sld_min = forms.FloatField(required=False)
    sld_max = forms.FloatField(required=False)

    roughness_is_fixed = forms.BooleanField(required=False, initial=True)
    roughness_min = forms.FloatField(required=False)
    roughness_max = forms.FloatField(required=False)

