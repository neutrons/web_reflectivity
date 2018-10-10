#pylint: disable=too-many-branches, too-many-statements, too-many-nested-blocks, bare-except, line-too-long
"""
    Interface to refl1d
"""
import logging
import re
import json
import numbers
import numpy as np


def round_(value):
    """ Rounding function to make sure things look good on the web page """
    try:
        return float("%.4g" % value)
    except:
        return value

def update_with_results(fit_problem, par_name, value, error):
    """
        Update a mode with a parameter value.

        :param FitProblem fit_problem: fit problem object to update
        :param str par_name: parameter name
        :param float value: parameter value
        :param float error: parameter error
    """
    # Round the number to something legible. Avoid strings.
    if isinstance(value, numbers.Number):
        value = round_(value)
        error = round_(error)
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

def find_error(layer_name, par_name, value, error_output, tolerance=0.001, pretty_print=False):
    """
        Find the error of a parameter in the list of output parameters.
        @param layer_name: name of the layer
        @param par_name: name of the parameter
        @param value: output value, so we can recognize the entry
        @param error_output: list of fit output parameters from the DREAM output

        The output parameter list should be in the format: [ [parameter name, value, error], ... ]
        The DREAM outputs are not grouped by sample/experiment, so we have to use the
        parameter values to determine which is which.

        Because of constraints, parameters can have any name, so key on the parameter
        value to assign the errors, but don't change the reported value in case we
        incorrectly assign errors.
    """
    if error_output is None:
        return value, 0.0

    # Find the parameter in the list of output parameters
    long_name = "%s %s" % (layer_name, par_name)
    long_name = long_name.strip()
    _value = value
    _error = 0
    for par, val, err in error_output:
        if par == long_name:
            if value == 0:
                diff = np.abs(float(val))
            else:
                diff = np.abs((float(val)-value)/value)
            if diff < tolerance:
                _error = err
    if pretty_print:
        _value = "%.4g &#177; %.4g" % (value, _error) if _error > 0 else value
    return _value, _error

def update_model_from_dict(fit_problem, experiment, error_output=None, pretty_print=False):
    """
        Parse a json representation of the experiment
        :param FitProblem fit_problem: FitProblem-like ojbect
        :param dict experiment: dictionary representation of the fit problem read from the json output
        :param list error_output: list of DREAM output parameters, with errors.
        :param bool pretty_print: if True, the value will be turned into a value +- error string
    """
    for layer in experiment['sample']['layers']:
        for par_name in ['thickness', 'rho', 'irho', 'interface']:
            if layer[par_name]['fixed'] is False:
                _value, _error = find_error(layer['name'], par_name, layer[par_name]['value'], error_output, pretty_print=pretty_print)
                update_with_results(fit_problem, '%s %s' % (layer['name'], par_name), _value, error=_error)

    if experiment['probe']['intensity']['fixed'] is False:
        _value, _error = find_error('', par_name, experiment['probe']['intensity']['value'], error_output, pretty_print=pretty_print, tolerance=0.01)
        update_with_results(fit_problem, 'intensity', _value, error=_error)

    if experiment['probe']['background']['fixed'] is False:
        _value, _error = find_error('', par_name, experiment['probe']['background']['value'], error_output, pretty_print=pretty_print, tolerance=0.01)
        update_with_results(fit_problem, 'background', _value, error=_error)

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

def extract_multi_data_from_log(log_content):
    """
        Extract data block from a log. For simultaneous fits, an EXPT_START tag
        precedes every block:

            EXPT_START 0
            REFL_START

        :param str log_content: string buffer of the job log
    """
    return _extract_multi_block_from_log(log_content, "REFL")

def extract_multi_sld_from_log(log_content):
    """
        Extract multiple SLD profiles from a simultaneous REFL1D fit.

        :param str log_content: string buffer of the job log
    """
    return _extract_multi_block_from_log(log_content, "SLD")

def extract_multi_json_from_log(log_content):
    """
        Extract multiple JSON blocks from a REFL1D fit log.
    """
    _json_list = _extract_multi_block_from_log(log_content, "MODEL_JSON")
    return [[item[0], json.loads(item[1])] for item in _json_list]

def _extract_multi_block_from_log(log_content, block_name):
    """
        Extract multiple data blocks from a simultaneous REFL1D fit log.
        The start tag of each block will be [block_name]_START
        and the end tag of each block will be [block_name]_END.

        :param str log_content: string buffer of the job log
        :param str block_name: name of the block to extract
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
        if line.startswith("%s_START" % block_name):
            data_started = True
        elif line.startswith("%s_END" % block_name):
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

def parse_single_param(line):
    """
        Parse a line of the refl1d DREAM output log
        1            intensity  1.084(31)  1.0991  1.1000 [  1.062   1.100] [  1.000   1.100]
        2              air rho 0.91(91)e-3 0.00062 0.00006 [ 0.0001  0.0017] [ 0.0000  0.0031]

    """
    result = re.search(r'^\d+ (.*) ([\d.-]+)\((\d+)\)(e?[\d-]*)\s* [\d.-]+\s* ([\d.-]+)(e?[\d-]*) ', line.strip())
    value_float = None
    error_float = None
    par_name = None
    if result is not None:
        par_name = result.group(1).strip()
        exponent = result.group(4)
        mean_value = "%s%s" % (result.group(2), exponent)
        error = "%s%s" % (result.group(3), exponent)
        best_value = "%s%s" % (result.group(5), result.group(6))

        # Error string does not have a .
        err_digits = len(error)
        val_digits = len(mean_value.replace('.', ''))
        err_value = ''
        i_digit = 0

        for c in mean_value: #pylint: disable=invalid-name
            if c == '.':
                err_value += '.'
            else:
                if i_digit < val_digits - err_digits:
                    err_value += '0'
                else:
                    err_value += error[i_digit - val_digits + err_digits]
                i_digit += 1

        error_float = float(err_value)
        value_float = float(best_value)
    return par_name, value_float, error_float
