"""
    Data models
"""
from __future__ import unicode_literals
from django.db import models
from django.contrib.auth.models import User
from django_remote_submission.models import Job
from django.forms import model_to_dict

class ReflectivityModel(models.Model):
    """
        Main reflectivity parameters
    """
    data_path = models.TextField(blank=True, default='144761')

    q_min = models.FloatField(blank=True, default=0)
    q_max = models.FloatField(blank=True, default=1)

    scale = models.FloatField(default=1)
    scale_is_fixed = models.BooleanField(blank=True, default=True)
    scale_min = models.FloatField(blank=True, default=0.9)
    scale_max = models.FloatField(blank=True, default=1.1)
    scale_error = models.FloatField(null=True, blank=True, default=0)

    background = models.FloatField(default=0)
    background_is_fixed = models.BooleanField(blank=True, default=True)
    background_min = models.FloatField(blank=True, default=0)
    background_max = models.FloatField(blank=True, default=1e-6)
    background_error = models.FloatField(null=True, blank=True, default=0)

    front_name = models.CharField(max_length=64, blank=True, default='air')
    front_sld = models.FloatField(default=0)
    front_sld_is_fixed = models.BooleanField(blank=True, default=True)
    front_sld_min = models.FloatField(blank=True, default=0)
    front_sld_max = models.FloatField(blank=True, default=1)
    front_sld_error = models.FloatField(null=True, blank=True, default=0)

    back_name = models.CharField(max_length=64, blank=True, default='Si')
    back_sld = models.FloatField(default=2.07)
    back_sld_is_fixed = models.BooleanField(blank=True, default=True)
    back_sld_min = models.FloatField(blank=True, default=2.0)
    back_sld_max = models.FloatField(blank=True, default=2.1)
    back_sld_error = models.FloatField(null=True, blank=True, default=0)

    back_roughness = models.FloatField(default=5.0)
    back_roughness_is_fixed = models.BooleanField(blank=True, default=True)
    back_roughness_min = models.FloatField(blank=True, default=1)
    back_roughness_max = models.FloatField(blank=True, default=5)
    back_roughness_error = models.FloatField(null=True, blank=True, default=0)

    def __unicode__(self):
        return u"id %s: %s" % (self.id, self.data_path)


class ReflectivityLayer(models.Model):
    """
        One layer of a reflectivity model
    """
    name = models.CharField(max_length=64, blank=True, default='material')
    thickness = models.FloatField(default=50.0)
    sld = models.FloatField(default=2.0)
    roughness = models.FloatField(default=1.0)
    remove = models.BooleanField(blank=True, default=False)
    layer_number = models.IntegerField(default=1000)

    # Fitting information
    thickness_is_fixed = models.BooleanField(blank=True, default=True)
    thickness_min = models.FloatField(blank=True, default=10.0)
    thickness_max = models.FloatField(blank=True, default=100.0)
    thickness_error = models.FloatField(null=True, blank=True, default=0)

    sld_is_fixed = models.BooleanField(blank=True, default=True)
    sld_min = models.FloatField(blank=True, default=1.0)
    sld_max = models.FloatField(blank=True, default=4.0)
    sld_error = models.FloatField(null=True, blank=True, default=0)

    roughness_is_fixed = models.BooleanField(blank=True, default=True)
    roughness_min = models.FloatField(blank=True, default=1.0)
    roughness_max = models.FloatField(blank=True, default=10.0)
    roughness_error = models.FloatField(null=True, blank=True, default=0)

    def __unicode__(self):
        return self.name

class FitProblem(models.Model):
    """
        Reflectivity model
    """
    user = models.ForeignKey(User, models.CASCADE)
    reflectivity_model = models.ForeignKey(ReflectivityModel, models.CASCADE)
    layers = models.ManyToManyField(ReflectivityLayer, related_name='_model_layers+')
    remote_job = models.ForeignKey(Job, models.CASCADE)
    timestamp = models.DateTimeField('timestamp', auto_now_add=True)

    def model_to_dicts(self):
        """ Return a dict with all the data values """
        refl_model_dict = model_to_dict(self.reflectivity_model)
        model_layers = []
        i = 0
        for layer in self.layers.all().order_by('layer_number'):
            i += 1
            layer_dict = model_to_dict(layer)
            # Start the ordering number at 1.
            layer_dict['layer_number'] = i
            model_layers.append(layer_dict)
        return refl_model_dict, model_layers

    def show_layers(self):
        """ Useful method to return the layers as a concise string """
        front_name = self.reflectivity_model.front_name
        back_name = self.reflectivity_model.back_name
        layers = [str(i) for i in self.layers.all().order_by('layer_number')]
        if len(layers) > 0:
            layers_str = ', '.join(layers)+', '
        else:
            layers_str = ''
        return u"%s, %s%s" % (front_name, layers_str, back_name)
    show_layers.short_description = "Layers"


class FitterOptions(models.Model):
    """
        Reflectivity model
    """
    user = models.ForeignKey(User, models.CASCADE)
    steps = models.IntegerField(default=1000, help_text='Number of fitter steps')
    burn = models.IntegerField(default=1000, help_text='Number of fitter burn steps')

    class Meta: #pylint: disable=old-style-class, no-init, too-few-public-methods
        verbose_name_plural = "Fitter options"

    def get_dict(self):
        """
            Return an options dictionary
        """
        return dict(steps=self.steps, burn=self.burn)


class Constraint(models.Model):
    """
        Fitting parameter constraints
    """
    user = models.ForeignKey(User, models.CASCADE)
    fit_problem = models.ForeignKey(FitProblem, models.CASCADE)
    definition = models.TextField(blank=True, default='')
    layer = models.ForeignKey(ReflectivityLayer, models.CASCADE)
    parameter = models.TextField(blank=True, default='')
    variables = models.TextField(blank=True, default='')
