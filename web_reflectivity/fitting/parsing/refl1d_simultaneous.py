#pylint: disable=no-self-use, too-many-branches, invalid-name, too-many-locals, unused-argument
"""
    Model parser for simultaneous fits
"""
import json
import re
import logging
from django.forms import model_to_dict

from .refl1d import parse_single_param, extract_multi_json_from_log, update_model_from_dict
from ..models import ReflectivityModel, ReflectivityLayer


class LayerList(list):
    """ Dummy class to mimic ManyToMany relationship of Django Model objects """
    def all(self):
        """ Emulate the all() method of a ManyToMany query set. """
        return self

    def order_by(self, key):
        """ Emulate order_by() of a query set. """
        return self

class DummyLayer(ReflectivityLayer):
    """
        Dummy layer defined to hold temporary model data
    """
    def save(self, *args, **kwargs):
        """ Dummy save() method """
        return


class DummyProblem(object):
    """
        Dummy FitProblem class used to read in JSON data and produce a dict
        representation that we can feed our forms.
    """
    def __init__(self, json_data, model_name):
        self.reflectivity_model = ReflectivityModel(data_path=model_name)
        self.layers = LayerList()

        # The refl1d JSON output is in reverse order. The first layer
        # in the list is actually the backing medium.
        for i, layer in enumerate(json_data['sample']['layers']):
            if i == 0:
                self.reflectivity_model.back_name = layer['name']
            elif i == len(json_data['sample']['layers']) - 1:
                self.reflectivity_model.front_name = layer['name']
            else:
                self.layers.append(DummyLayer(name=layer['name'],
                                              layer_number=i))

    def model_to_dicts(self):
        """ Return a dict with all the data values """
        refl_model_dict = model_to_dict(self.reflectivity_model)
        model_layers = []
        i = 0
        for layer in self.layers.all():
            i += 1
            layer_dict = model_to_dict(layer)
            # Start the ordering number at 1.
            layer_dict['layer_number'] = i
            model_layers.append(layer_dict)
        return [refl_model_dict, model_layers]

    def save(self, *args, **kwargs):
        """ Dummy save() method """
        return


def check_compatibility(content):
    """
        Check the compatibility of a log. If an older version of refl1d was used,
        we will need to parse the logs differently.
        Starting with version 0.8.6, a JSON representation of models is available
        and the refl1d version is part of the log.
    """
    return content.find('REFL1D_VERSION') >= 0

def json_to_fit_problem(json_data, model_name, error_output, pretty_print=False):
    """
        Turn a json representation of a model into a dictionary compatible with
        our forms.
        :param dict json_data: dict extracted from the json section of the log
        :param str model_name: name of the model
        :param list error_output: list of parameters and values taken from the DREAM output
        :param bool pretty_print: if True, the value will be turned into a value +- error string
    """
    problem = DummyProblem(json_data, model_name)
    update_model_from_dict(problem, json_data, error_output, pretty_print=pretty_print)
    return problem

def parse_models_from_log(content):
    """
        Parse the content of a simultaneous refl1d log file.
        :param str content: block of log text to parse
    """
    chi2 = 0
    chi2_per_model = []
    model_names = []
    error_params = []

    for l in content.split('\n'):
        if l.startswith("[chisq="):
            result = re.search(r'chisq=([\d.]*)', l)
            if result is not None:
                chi2_per_model.append(result.group(1))
        if l.startswith("[overall chisq="):
            result = re.search(r'chisq=([\d.]*)', l)
            if result is not None:
                chi2 = result.group(1)
        if l.startswith("SIMULTANEOUS"):
            clean_str = l.replace("SIMULTANEOUS ", "")
            model_names = json.loads(clean_str)

        # At the end of this section, we may find uncertainty info from the DREAM algorithm
        par_name, value, error = parse_single_param(l)
        if par_name is not None:
            error_params.append([par_name, value, error])

        # There is no useful information past MODEL_PARAMS_END
        if l.startswith("MODEL_PARAMS_END"):
            break

    # Extract models from json log data
    model_list = extract_multi_json_from_log(content)
    if not len(model_list) == len(model_names):
        logging.error("Inconsistent log: number of models doesn't match model names [%s vs %s]",
                      len(model_list), len(model_names))
    if not len(chi2_per_model) == len(model_names):
        logging.error("Inconsistent log: number of chi^2 values doesn't match [%s vs %s]",
                      len(model_list), len(model_names))

    # Add errors if they are available
    clean_model_list = []
    problem_list = []
    for i, [_name, _json_model] in enumerate(model_list):
        problem_list.append(json_to_fit_problem(_json_model, _name, error_params))
        _problem = json_to_fit_problem(_json_model, _name, error_params, pretty_print=True)
        refl_dict, layer_dict = _problem.model_to_dicts()
        refl_dict['chi2'] = chi2_per_model[i]
        clean_model_list.append([refl_dict, layer_dict])
    return clean_model_list, chi2, problem_list
