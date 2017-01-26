#pylint: disable=bare-except
"""
    Data models
    #TODO: move the script generation from the forms to the models
"""
from __future__ import unicode_literals
import sys
import logging
from math import *
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
    remote_job = models.ForeignKey(Job, models.SET_NULL, null=True)
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

    def __unicode__(self):
        return u"%s" % self.reflectivity_model

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
    LAYER_PARAMETER = {'thickness': 'thickness',
                       'sld': 'material.rho',
                       'roughness': 'interface'}

    user = models.ForeignKey(User, models.CASCADE)
    fit_problem = models.ForeignKey(FitProblem, models.CASCADE)
    definition = models.TextField(blank=True, default='')
    layer = models.ForeignKey(ReflectivityLayer, models.CASCADE)
    parameter = models.TextField(blank=True, default='')
    variables = models.TextField(blank=True, default='')

    def __unicode__(self):
        return u"%s_%s" % (self.layer, self.parameter)

    def get_constraint_function(self, alternate_name=None):
        """
            Generate the constraint function
        """
        if alternate_name is not None:
            function_name = alternate_name
        else:
            function_name = "constraint_%s" % self.parameter
        constraint_function = "def %s(%s):\n" % (function_name, self.variables)
        for line in self.definition.splitlines():
            constraint_function += "    %s\n" % line

        return function_name, constraint_function

    def apply_constraint(self, fit_problem):
        """
            Apply the constraint to a fit problem
        """
        # Parse the variables and get their values
        parameters = {}
        variable_list = self.variables.split(',')
        for variable in variable_list:
            clean_variable = variable.strip()
            toks = clean_variable.split('_')
            if len(toks) == 2:
                layer_name = toks[0].strip()
                layer_parameter = toks[1].strip()
                layer_objects = fit_problem.layers.filter(name=layer_name)
                if len(layer_objects) > 0:
                    if hasattr(layer_objects[0], layer_parameter):
                        parameters[clean_variable] = getattr(layer_objects[0], layer_parameter)
        _, constraint_function = self.get_constraint_function(alternate_name='constraint_func')

        try:
            def constraint_func():
                """ Dummy function to avoid pylint error """
                return 1
            exec constraint_function #pylint: disable=exec-used
            setattr(self.layer, self.parameter, constraint_func(**parameters))
            self.layer.save()
            fit_problem.save()
        except:
            logging.error("Could not evaluate constraint: %s", sys.exc_value)

    def get_ranges(self, sample_name='sample', probe_name='probe'):
        """
            Return the constraint code for the refl1d script
        """
        layer_parameter = self.LAYER_PARAMETER.get(self.parameter, self.parameter)
        function_name, constraint = self.get_constraint_function()

        # Example: sample['aSi'].material.rho = get_sld(sample['aSi'].thickness)
        expanded_vars = []
        for item in self.variables.split(','):
            [layer_name, var_name] = item.split('_')
            expanded_vars.append("%s['%s'].%s" % (sample_name,
                                                  layer_name.strip(),
                                                  self.LAYER_PARAMETER.get(var_name.strip(),
                                                                           var_name.strip())))
        constraint += "\n%s['%s'].%s = %s(%s)\n" % (sample_name, self.layer.name,
                                                    layer_parameter,
                                                    function_name,
                                                    ','.join(expanded_vars))

        return constraint

    @classmethod
    def validate_constraint(cls, constraint_code, variables):
        """
            Validate user-submitted constraint code.
        """
        comments = []
        is_valid = True

        # Import statements are not allowed
        if constraint_code.find('import') >= 0:
            comments.append('Imports are not allowed in constraint code.')
            is_valid = False

        # The code must contain a return statement
        if constraint_code.find('return') < 0:
            comments.append("The code must contain a return statement.")
            is_valid = False

        # Prepend function definition
        constraint_function = "def constraint(%s):\n" % ','.join(variables)
        for line in constraint_code.splitlines():
            constraint_function += "    %s\n" % line

        # Check that it compiles
        try:
            def constraint():
                """ Dummy function to avoid pylint error """
                return 1

            compile(constraint_function, 'constraint.py', 'exec')
            exec constraint_function #pylint: disable=exec-used
        except:
            comments.append("Syntax error:\n%s" % sys.exc_value)
            is_valid = False

        parameters_1 = {}
        parameters_2 = {}
        for variable in variables:
            parameters_1[variable] = 1
            parameters_2[variable] = 10
        output_value_1 = constraint(**parameters_1)
        output_value_2 = constraint(**parameters_2)

        if output_value_1 == output_value_2:
            comments.append("Your constraint cannot be a constant")
            is_valid = False

        return is_valid, comments

