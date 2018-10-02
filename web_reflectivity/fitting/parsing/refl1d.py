#pylint: disable=too-many-branches, too-many-statements, too-many-nested-blocks, bare-except, line-too-long
"""
    Interface to refl1d
"""
import logging
import re
import json
from .refl1d_err_model import parse_single_param

def update_with_results(fit_problem, par_name, value, error):
    """
        Update a mode with a parameter value.

        :param FitProblem fit_problem: fit problem object to update
        :param str par_name: parameter name
        :param float value: parameter value
        :param float error: parameter error
    """
    toks = par_name.split(' ')
    # The first token is the layer name or top-level parameter name
    if toks[0] == 'intensity':
        fit_problem.reflectivity_model.scale = value
        fit_problem.reflectivity_model.scale_error = error
    elif toks[0] == 'background':
        fit_problem.reflectivity_model.background = value
        fit_problem.reflectivity_model.background_error = error
    elif toks[1] == 'rho':
        if toks[0] == fit_problem.reflectivity_model.front_name:
            fit_problem.reflectivity_model.front_sld = value
            fit_problem.reflectivity_model.front_sld_error = error
        elif toks[0] == fit_problem.reflectivity_model.back_name:
            fit_problem.reflectivity_model.back_sld = value
            fit_problem.reflectivity_model.back_sld_error = error
        else:
            for layer in fit_problem.layers.all():
                if toks[0] == layer.name:
                    layer.sld = value
                    layer.sld_error = error
                    layer.save()
    elif toks[1] == 'thickness':
        for layer in fit_problem.layers.all():
            if toks[0] == layer.name:
                layer.thickness = value
                layer.thickness_error = error
                layer.save()
    elif toks[1] == 'irho':
        for layer in fit_problem.layers.all():
            if toks[0] == layer.name:
                layer.i_sld = value
                layer.i_sld_error = error
                layer.save()
    elif toks[1] == 'interface':
        if toks[0] == fit_problem.reflectivity_model.back_name:
            fit_problem.reflectivity_model.back_roughness = value
            fit_problem.reflectivity_model.back_roughness_error = error
        else:
            for layer in fit_problem.layers.all():
                if toks[0] == layer.name:
                    layer.roughness = value
                    layer.roughness_error = error
                    layer.save()
    fit_problem.save()

def update_model_from_dict(fit_problem, experiment):
    """
        Parse a json representation of the experiment
    """
    for layer in experiment['sample']['layers']:
        for par_name in ['thickness', 'rho', 'irho', 'interface']:
            if layer[par_name]['fixed'] is False:
                update_with_results(fit_problem, '%s %s' % (layer['name'], par_name), layer[par_name]['value'], error=0.0)

    if experiment['probe']['intensity']['fixed'] is False:
        update_with_results(fit_problem, 'intensity', experiment['probe']['intensity']['value'], error=0.0)

    if experiment['probe']['background']['fixed'] is False:
        update_with_results(fit_problem, 'intensity', experiment['probe']['background']['value'], error=0.0)

def update_model_from_json(content, fit_problem):
    """
        Update a model described by a FitProblem object according to the contents
        of a REFL1D log.

        :param str content: log contents
        :param FitProblem fit_problem: fit problem object to update
    """
    key_start = 'MODEL_JSON_START'
    key_end = 'MODEL_JSON_END'
    _index_start = content.find(key_start)
    _index_end = content.find(key_end)
    if _index_start >= 0 and _index_end > 0:
        _json = content[_index_start+len(key_start):_index_end]
        _expt = json.loads(_json)
        update_model_from_dict(fit_problem, _expt)

def update_model(content, fit_problem):
    """
        Update a model described by a FitProblem object according to the contents
        of a REFL1D log.

        :param str content: log contents
        :param FitProblem fit_problem: fit problem object to update
    """
    start_err_file = False
    found_errors = False
    chi2 = None
    for line in content.split('\n'):
        if start_err_file:
            try:
                par_name, value, error = parse_single_param(line)
                if par_name is not None:
                    found_errors = True
                    update_with_results(fit_problem, par_name, value, error)
            except:
                logging.error("Could not parse line %s", line)

        # Find chi^2, which comes just before the list of parameters
        if line.startswith('[chi'):
            try:
                result = re.search(r'chisq=([\d.]*)', line)
                chi2 = float(result.group(1))
            except:
                chi2 = None

        if line.startswith('MODEL_PARAMS_START'):
            start_err_file = True
        if line.startswith('MODEL_PARAMS_END'):
            start_err_file = False

    # If we didn't use the DREAM algorithm, we won't found the errors and need to parse the full json data
    if not found_errors:
        update_model_from_json(content, fit_problem)
    return chi2

def extract_data_from_log(log_content):
    """
        Extract data from log.

        :param log_content: string buffer of the job log
    """
    data_block_list = extract_multi_data_from_log(log_content)
    if data_block_list is not None and len(data_block_list) > 0:
        return data_block_list[0][1]
    return None

def extract_multi_data_from_log(log_content):
    """
        Extract data block from a log. For simultaneous fits, an EXPT_START tag
        precedes every block:

            EXPT_START 0
            REFL_START

        :param str log_content: string buffer of the job log
    """
    # Parse out the portion we need
    data_started = False
    data_content = []
    data_block_list = []
    model_names = []

    for line in log_content.split('\n'):
        if line.startswith("SIMULTANEOUS"):
            clean_str = line.replace("SIMULTANEOUS ", "")
            model_names = json.loads(clean_str)
        if line.startswith("REFL_START"):
            data_started = True
        elif line.startswith("REFL_END"):
            data_started = False
            if len(data_content) > 0:
                data_path = ''
                if len(model_names) > len(data_block_list):
                    data_path = model_names[len(data_block_list)]
                data_block_list.append([data_path, '\n'.join(data_content)])
            data_content = []
        elif data_started is True:
            data_content.append(line)
    return data_block_list

def extract_sld_from_log(log_content):
    """
        Extract a single SLD profile from a REFL1D log.

        :param str log_content: string buffer of the job log
    """
    data_block_list = extract_multi_sld_from_log(log_content)
    if data_block_list is not None and len(data_block_list) > 0:
        return data_block_list[0][1]
    return None

def extract_multi_sld_from_log(log_content):
    """
        Extract multiple SLD profiles from a simultaneous REFL1D fit.

        :param str log_content: string buffer of the job log
    """
    # Parse out the portion we need
    data_started = False
    data_content = []
    data_block_list = []
    model_names = []

    for line in log_content.split('\n'):
        if line.startswith("SIMULTANEOUS"):
            clean_str = line.replace("SIMULTANEOUS ", "")
            model_names = json.loads(clean_str)
        if line.startswith("SLD_START"):
            data_started = True
        elif line.startswith("SLD_END"):
            data_started = False
            if len(data_content) > 0:
                data_path = ''
                if len(model_names) > len(data_block_list):
                    data_path = model_names[len(data_block_list)]
                data_block_list.append([data_path, '\n'.join(data_content)])
            data_content = []
        elif data_started is True:
            data_content.append(line)
    return data_block_list
