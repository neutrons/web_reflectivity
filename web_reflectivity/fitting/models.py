"""
    Data models
"""
from __future__ import unicode_literals
from django.db import models

class ReflectivityModel(models.Model):
    """
        Main reflectivity parameters
    """
    data_path = models.TextField(unique=True, blank=True, default='144761')
    # widget=forms.TextInput(attrs={'class' : 'font_resize'}))

    q_min = models.FloatField(blank=True, default=0)
    q_max = models.FloatField(blank=True, default=1)

    scale = models.FloatField(default=1)
    scale_is_fixed = models.BooleanField(blank=True, default=True)
    scale_min = models.FloatField(blank=True, default=0.9)
    scale_max = models.FloatField(blank=True, default=1.1)
    scale_error = models.FloatField(blank=True, default=0)

    background = models.FloatField(default=0)
    background_is_fixed = models.BooleanField(blank=True, default=True)
    background_min = models.FloatField(blank=True, default=0)
    background_max = models.FloatField(blank=True, default=1e-6)
    background_error = models.FloatField(blank=True, default=0)

    front_name = models.CharField(max_length=64, blank=True, default='air')
    front_sld = models.FloatField(default=0)
    front_sld_is_fixed = models.BooleanField(blank=True, default=True)
    front_sld_min = models.FloatField(blank=True, default=0)
    front_sld_max = models.FloatField(blank=True, default=1)
    front_sld_error =models.FloatField(blank=True, default=0)

    back_name = models.CharField(max_length=64, blank=True, default='Si')
    back_sld = models.FloatField(default=2.07)
    back_sld_is_fixed = models.BooleanField(blank=True, default=True)
    back_sld_min = models.FloatField(blank=True, default=2.0)
    back_sld_max = models.FloatField(blank=True, default=2.1)
    back_sld_error = models.FloatField(blank=True, default=0)

    back_roughness = models.FloatField(default=5.0)
    back_roughness_is_fixed = models.BooleanField(blank=True, default=True)
    back_roughness_min = models.FloatField(blank=True, default=1)
    back_roughness_max = models.FloatField(blank=True, default=5)
    back_roughness_error = models.FloatField(blank=True, default=0)

class FitProblem(models.Model):
    reflectivity_model = models.ForeignKey(ReflectivityModel)
    timestamp = models.DateTimeField('timestamp')
    
