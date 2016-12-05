"""
    Data models
"""
from __future__ import unicode_literals
from django.db import models
from django.contrib.auth.models import User
from django_remote_submission.models import Job

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


class ReflectivityLayer(models.Model):
    """
        One layer of a reflectivity model
    """
    name = models.CharField(max_length=64, blank=True, default='')
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


class FitProblem(models.Model):
    """
        Reflectivity model
    """
    user = models.ForeignKey(User)
    reflectivity_model = models.ForeignKey(ReflectivityModel)
    layers = models.ManyToManyField(ReflectivityLayer, related_name='_model_layers+')
    remote_job = models.ForeignKey(Job)
    timestamp = models.DateTimeField('timestamp', auto_now_add=True)

