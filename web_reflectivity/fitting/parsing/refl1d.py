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

def update_model(content, fit_problem):
    """
        Update a model described by a FitProblem object according to the contents
        of a REFL1D log.

        :param str content: log contents
        :param FitProblem fit_problem: fit problem object to update

        .. note::
            [chisq=23.426(15), nllf=1850.62]

                          Parameter       mean  median    best [   68% interval] [   95% interval]

             1            intensity  1.084(31)  1.0991  1.1000 [  1.062   1.100] [  1.000   1.100]

             2              air rho 0.91(91)e-3 0.00062 0.00006 [ 0.0001  0.0017] [ 0.0000  0.0031]

    """
    start_err_file = False
    start_par_file = False
    found_errors = False
    for line in content.split('\n'):
        if start_err_file:
            try:
                par_name, value, error = parse_single_param(line)
                if par_name is not None:
                    found_errors = True
                    update_with_results(fit_problem, par_name, value, error)
            except:
                logging.error("Could not parse line %s", line)

        if start_par_file and not found_errors:
            try:
                par_name, value = parse_par_file_line(line)
                if par_name is not None:
                    update_with_results(fit_problem, par_name, value, error=0.0)
            except:
                logging.error("Could not parse line %s", line)

        # Find chi^2, which comes just before the list of parameters
        if line.startswith('[chi'):
            try:
                result = re.search(r'chisq=([\d.]*)', line)
                chi2 = result.group(1)
            except:
                chi2 = "unknown"

        if line.startswith('MODEL_PARAMS_START'):
            start_err_file = True
        if line.startswith('MODEL_PARAMS_END'):
            start_err_file = False
        if line.startswith('MODEL_BEST_VALUES_START'):
            start_par_file = True
        if line.startswith('MODEL_BEST_VALUES_END'):
            start_par_file = False

    try:
        chi2_value = float(chi2)
    except:
        chi2_value = None
    return chi2_value

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

def parse_par_file_line(line):
    """
        Parse a line from the __model.par file

        :param str line: string to be parsed
    """
    result = re.search(r'^(.*) ([\d.-]+)(e?[\d-]*)', line.strip())
    value_float = None
    par_name = None
    if result is not None:
        par_name = result.group(1).strip()
        value = "%s%s" % (result.group(2), result.group(3))
        value_float = float(value)
        value_float = float("%g" % value_float)
    return par_name, value_float
