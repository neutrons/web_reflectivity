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

    front_name = forms.CharField(required=False, initial='air')
    front_sld = forms.FloatField(required=True, initial=0.0)
    front_sld_is_fixed = forms.BooleanField(required=False, initial=True)
    front_sld_min = forms.FloatField(required=False)
    front_sld_max = forms.FloatField(required=False)

    back_name = forms.CharField(required=False, initial='Si')
    back_sld = forms.FloatField(required=True, initial=2.07)
    back_sld_is_fixed = forms.BooleanField(required=False, initial=True)
    back_sld_min = forms.FloatField(required=False)
    back_sld_max = forms.FloatField(required=False)

    back_roughness = forms.FloatField(required=True, initial=5.0)
    back_roughness_is_fixed = forms.BooleanField(required=False, initial=True)
    back_roughness_min = forms.FloatField(required=False)
    back_roughness_max = forms.FloatField(required=False)

    def get_ranges(self, probe_name='probe'):
        """
            probe.intensity=Parameter(value=1.0,name="unity")
            probe.background.range(1e-8,1e-5)
        """
        ranges = ''
        if self.cleaned_data['scale_is_fixed'] is False:
            ranges += "%s.intensity.range(%s, %s)\n" % (probe_name, self.cleaned_data['scale_min'],
                                                        self.cleaned_data['scale_max'])
        else:
            ranges += "%s.intensity=Parameter(value=%s,name='normalization')\n" % (probe_name,
                                                                                   self.cleaned_data['scale'])

        if self.cleaned_data['background_is_fixed'] is False:
            ranges += "%s.background.range(%s, %s)\n" % (probe_name, self.cleaned_data['background_min'],
                                                         self.cleaned_data['background_max'])
        else:
            ranges += "%s.background=Parameter(value=%s,name='background')\n" % (probe_name,
                                                                                 self.cleaned_data['background'])

        return ranges

class LayerForm(forms.Form):
    """
        Simple form for a layer
    """
    name = forms.CharField(required=False, initial='new layer')
    thickness = forms.FloatField(required=True, initial=0.0)
    sld = forms.FloatField(required=True, initial=0.0)
    roughness = forms.FloatField(required=True, initial=0.0)
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

    def get_material(self):
        """
            C60 = SLD(name='C60',  rho=1.3, irho=0.0)
        """
        return "%s = SLD(name='%s', rho=%s, irho=0.0)" % (self.cleaned_data['name'],
                                                          self.cleaned_data['name'],
                                                          self.cleaned_data['sld'])

    def get_layer(self):
        if self.cleaned_data['thickness'] == 0 and self.cleaned_data['roughness'] == 0:
            return self.cleaned_data['name']
        return "%s(%s, %s)" % (self.cleaned_data['name'],
                               self.cleaned_data['thickness'],
                               self.cleaned_data['roughness'])

    def get_ranges(self, sample_name='sample'):
        """
            sample['C60'].interface.range(0, 20)
            sample['C60'].material.rho.range(0, 3)
            sample['C60'].thickness.range(1, 300)
        """
        ranges = ''
        if self.cleaned_data['thickness'] == 0 and self.cleaned_data['roughness'] == 0:
            return ranges
        if self.cleaned_data['thickness_is_fixed'] is False:
            ranges += "%s['%s'].thickness.range(%s, %s)\n" % (sample_name, self.cleaned_data['name'],
                                                              self.cleaned_data['thickness_min'],
                                                              self.cleaned_data['thickness_max'])

        if self.cleaned_data['sld_is_fixed'] is False:
            ranges += "%s['%s'].material.rho.range(%s, %s)\n" % (sample_name, self.cleaned_data['name'],
                                                              self.cleaned_data['sld_min'],
                                                              self.cleaned_data['sld_max'])

        if self.cleaned_data['roughness_is_fixed'] is False:
            ranges += "%s['%s'].interface.range(%s, %s)\n" % (sample_name, self.cleaned_data['name'],
                                                              self.cleaned_data['roughness_min'],
                                                              self.cleaned_data['roughness_max'])
        return ranges

            
            