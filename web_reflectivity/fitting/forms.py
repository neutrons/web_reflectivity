#pylint: disable=line-too-long
"""
    Forms for web reflectivity
"""
import logging

from django import forms
from django.forms import ModelForm

from .models import ReflectivityModel, ReflectivityLayer

class UploadFileForm(forms.Form):
    """
        Simple form to select a data file on the user's machine
    """
    file = forms.FileField()


class ConstraintForm(forms.Form):
    """
        Simple form to select a data file on the user's machine
    """
    PARAMETER_CHOICES = (("thickness", "thickness"),
                         ("sld", "sld"),
                         ("roughness", "roughness"),
                         )
    definition = forms.CharField(widget=forms.Textarea)
    layer = forms.ModelChoiceField(queryset=ReflectivityLayer.objects.all())
    parameter = forms.ChoiceField(choices=PARAMETER_CHOICES)
    variables = forms.MultipleChoiceField(choices=[])

# Create the model form class.
class ReflectivityFittingModelForm(ModelForm):
    """
        Form created from the ReflectivityModel class
    """
    class Meta: #pylint: disable=old-style-class, no-init, too-few-public-methods
        """ Define how we use the model to create a form """
        model = ReflectivityModel
        fields = ['data_path', 'q_min', 'q_max',
                  'scale', 'scale_is_fixed', 'scale_min', 'scale_max', 'scale_error',
                  'background', 'background_is_fixed', 'background_min', 'background_max', 'background_error',
                  'front_sld', 'front_sld_is_fixed', 'front_sld_min', 'front_sld_max', 'front_sld_error',
                  'back_sld', 'back_sld_is_fixed', 'back_sld_min', 'back_sld_max', 'back_sld_error',
                  'back_roughness', 'back_roughness_is_fixed', 'back_roughness_min', 'back_roughness_max', 'back_roughness_error',
                  'front_name', 'back_name',
                  ]
        widgets = {
            'data_path': forms.TextInput(attrs={'class' : 'font_resize'}),
        }


class ReflectivityFittingForm(ReflectivityFittingModelForm):
    """
        Model parameters, excluding layers
    """
    def has_free_parameter(self):
        """
            Check that we have a least one free parameter, otherwise
            the fitter will complain.
        """
        return not self.cleaned_data['scale_is_fixed'] or not self.cleaned_data['background_is_fixed'] or \
            not self.cleaned_data['front_sld_is_fixed'] or not self.cleaned_data['back_sld_is_fixed'] or \
            not self.cleaned_data['back_roughness_is_fixed']

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

    def get_predefined_intensity_range(self, delta=0.001, probe_name='probe'):
        """
            Since refl1d only fits, evaluating a model has to mean fitting in a
            tiny range.
        """
        current_scale = self.cleaned_data['scale']
        scale_min = current_scale * (1.0-delta)
        scale_max = current_scale * (1.0+delta)
        ranges = "%s.intensity.range(%s, %s)\n" % (probe_name, scale_min, scale_max)
        ranges += "%s.background=Parameter(value=%s,name='background')\n" % (probe_name,
                                                                             self.cleaned_data['background'])
        return ranges

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


# Create the layer form class.
class LayerModelForm(ModelForm):
    """
        Form created from the ReflectivityLayer class
    """
    class Meta: #pylint: disable=old-style-class, no-init, too-few-public-methods
        """ Define how we use the model to create a form """
        model = ReflectivityLayer
        fields = ['name', 'thickness', 'sld', 'roughness', 'remove', 'layer_number',
                  'thickness_is_fixed', 'thickness_min', 'thickness_max', 'thickness_error',
                  'sld_is_fixed', 'sld_min', 'sld_max', 'sld_error',
                  'roughness_is_fixed', 'roughness_min', 'roughness_max', 'roughness_error',
                  ]


class LayerForm(LayerModelForm):
    """
        Reflectivity model layer
    """
    def has_free_parameter(self):
        """
            Check that we have a least one free parameter, otherwise
            the fitter will complain.
        """
        return not self.cleaned_data['thickness_is_fixed'] or not self.cleaned_data['sld_is_fixed'] or \
            not self.cleaned_data['roughness_is_fixed']

    def info_complete(self):
        """ Return True of this layer should be used """
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
        """
            Get layer info in a format we can send to refl1d
        """
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
