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
        Main reflectivity parameters
    """
    data_path = forms.CharField(required=False, initial='/plots/ref_l/144761/update/html/', widget=forms.TextInput(attrs={'class' : 'font_resize'}))
    scale = ValueErrorField(required=True, initial=1.0)
    scale_is_fixed = forms.BooleanField(required=False, initial=True)
    scale_min = forms.FloatField(required=False, initial=0.9)
    scale_max = forms.FloatField(required=False, initial=1.1)
    scale_error = forms.FloatField(required=False, initial=0.0)

    background = forms.FloatField(required=True, initial=0.0)
    background_is_fixed = forms.BooleanField(required=False, initial=True)
    background_min = forms.FloatField(required=False, initial=0)
    background_max = forms.FloatField(required=False, initial=1e-6)
    background_error = forms.FloatField(required=False, initial=0.0)

    front_name = forms.CharField(required=False, initial='air')
    front_sld = forms.FloatField(required=True, initial=0.0)
    front_sld_is_fixed = forms.BooleanField(required=False, initial=True)
    front_sld_min = forms.FloatField(required=False, initial=0)
    front_sld_max = forms.FloatField(required=False, initial=1)
    front_sld_error = forms.FloatField(required=False, initial=0.0)

    back_name = forms.CharField(required=False, initial='Si')
    back_sld = forms.FloatField(required=True, initial=2.07)
    back_sld_is_fixed = forms.BooleanField(required=False, initial=True)
    back_sld_min = forms.FloatField(required=False, initial=2.0)
    back_sld_max = forms.FloatField(required=False, initial=2.1)
    back_sld_error = forms.FloatField(required=False, initial=0.0)

    back_roughness = forms.FloatField(required=True, initial=5.0)
    back_roughness_is_fixed = forms.BooleanField(required=False, initial=True)
    back_roughness_min = forms.FloatField(required=False, initial=1)
    back_roughness_max = forms.FloatField(required=False, initial=5)
    back_roughness_error = forms.FloatField(required=False, initial=0.0)

    def get_materials(self):
        """
            C60 = SLD(name='C60',  rho=1.3, irho=0.0)
        """
        materials = "%s = SLD(name='%s', rho=%s, irho=0.0)\n" % (self.cleaned_data['front_name'],
                                                                 self.cleaned_data['front_name'],
                                                                 self.cleaned_data['front_sld'])
        materials += "%s = SLD(name='%s', rho=%s, irho=0.0)\n" % (self.cleaned_data['back_name'],
                                                                  self.cleaned_data['back_name'],
                                                                  self.cleaned_data['back_sld'])
        return materials

    def get_ranges(self, sample_name='sample', probe_name='probe'):
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

        if self.cleaned_data['front_sld_is_fixed'] is False:
            ranges += "%s['%s'].material.rho.range(%s, %s)\n" % (sample_name, self.cleaned_data['front_name'],
                                                                 self.cleaned_data['front_sld_min'],
                                                                 self.cleaned_data['front_sld_max'])

        if self.cleaned_data['back_sld_is_fixed'] is False:
            ranges += "%s['%s'].material.rho.range(%s, %s)\n" % (sample_name, self.cleaned_data['back_name'],
                                                                 self.cleaned_data['back_sld_min'],
                                                                 self.cleaned_data['back_sld_max'])

        if self.cleaned_data['back_roughness_is_fixed'] is False:
            ranges += "%s['%s'].interface.range(%s, %s)\n" % (sample_name, self.cleaned_data['back_name'],
                                                              self.cleaned_data['back_roughness_min'],
                                                              self.cleaned_data['back_roughness_max'])

        return ranges

    def get_sample_template(self):
        """
            Return a template for the sample description
        """
        back_layer = " %s(0, %s)" % (self.cleaned_data['back_name'], self.cleaned_data['back_roughness'])
        return "( " + back_layer + " | %s" + str(self.cleaned_data['front_name']) + " )"

class LayerForm(forms.Form):
    """
        Simple form for a layer
    """
    name = forms.CharField(required=False, initial='')
    thickness = forms.FloatField(required=True, initial=0.0)
    sld = forms.FloatField(required=True, initial=0.0)
    roughness = forms.FloatField(required=True, initial=0.0)
    remove = forms.BooleanField(required=False, initial=False)
    layer_number = forms.IntegerField(initial=1000)

    # Fitting information
    thickness_is_fixed = forms.BooleanField(required=False, initial=True)
    thickness_min = forms.FloatField(required=False, initial=10.0)
    thickness_max = forms.FloatField(required=False, initial=100.0)
    thickness_error = forms.FloatField(required=False, initial=0.0)

    sld_is_fixed = forms.BooleanField(required=False, initial=True)
    sld_min = forms.FloatField(required=False, initial=1.0)
    sld_max = forms.FloatField(required=False, initial=4.0)
    sld_error = forms.FloatField(required=False, initial=0.0)

    roughness_is_fixed = forms.BooleanField(required=False, initial=True)
    roughness_min = forms.FloatField(required=False, initial=1.0)
    roughness_max = forms.FloatField(required=False, initial=10.0)
    roughness_error = forms.FloatField(required=False, initial=0.0)

    def info_complete(self):
        return len(self.cleaned_data) > 0 and self.cleaned_data['remove'] is False

    def get_materials(self):
        """
            C60 = SLD(name='C60',  rho=1.3, irho=0.0)
        """
        if 'name' not in self.cleaned_data or 'sld' not in self.cleaned_data:
            logging.error("Incomplete layer information: %s", str(self.cleaned_data))
            return ''
        layer_name = self.cleaned_data['name']
        layer_name = layer_name.replace(' ', '_')
        return "%s = SLD(name='%s', rho=%s, irho=0.0)" % (layer_name,
                                                          layer_name,
                                                          self.cleaned_data['sld'])

    def get_layer(self):
        if self.cleaned_data['thickness'] == 0 and self.cleaned_data['roughness'] == 0:
            return self.cleaned_data['name']
        layer_name = self.cleaned_data['name']
        layer_name = layer_name.replace(' ', '_')
        return "%s(%s, %s)" % (layer_name,
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
        layer_name = self.cleaned_data['name']
        layer_name = layer_name.replace(' ', '_')
        if self.cleaned_data['thickness_is_fixed'] is False:
            ranges += "%s['%s'].thickness.range(%s, %s)\n" % (sample_name, layer_name,
                                                              self.cleaned_data['thickness_min'],
                                                              self.cleaned_data['thickness_max'])

        if self.cleaned_data['sld_is_fixed'] is False:
            ranges += "%s['%s'].material.rho.range(%s, %s)\n" % (sample_name, layer_name,
                                                              self.cleaned_data['sld_min'],
                                                              self.cleaned_data['sld_max'])

        if self.cleaned_data['roughness_is_fixed'] is False:
            ranges += "%s['%s'].interface.range(%s, %s)\n" % (sample_name, layer_name,
                                                              self.cleaned_data['roughness_min'],
                                                              self.cleaned_data['roughness_max'])
        return ranges

