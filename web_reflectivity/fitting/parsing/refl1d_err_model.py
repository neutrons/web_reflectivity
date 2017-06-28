#pylint: disable=consider-using-enumerate, too-many-branches, invalid-name, bare-except, too-many-arguments, line-too-long, too-many-locals, too-many-statements
"""
    Model parser for the strange model representation refl1d uses in its .err file.
"""
import sys
import json
import re
import math
import logging

def find_error(layer_name, par_name, layer_dict, output_params):
    """
        Find the error of a parameter in the list of output parameters.
        @param layer_name: name of the layer
        @param par_name: name of the parameter
        @param layer_dict: dictionary of layer parameters
        @param output_params: list of fit output parameters

        The output parameter list should be in the format: [ [parameter name, value, error], ... ]
    """
    # Because of constraints, the parameter name we are looking for
    # may not be in the layer dictionary. If it's not, find the right one.
    long_name = "%s %s" % (layer_name, par_name)
    long_name = long_name.strip()
    if not long_name in layer_dict:
        for par in layer_dict.keys():
            if par_name in par:
                long_name = par

    if output_params is None:
        return layer_dict[long_name], 0

    # Find the parameter in the list of output parameters
    value = float(layer_dict[long_name])
    error = 0
    _value = value
    for par, val, err in output_params:
        if par == long_name:
            if value == 0:
                diff = math.fabs(float(val))
            else:
                diff = math.fabs((float(val)-_value)/_value)
            if diff<0.001:
                value = val
                error = err
    return value, error

def update_parameter(output_name, layer_name, par_name, layer_dict,
                     output_params, pretty_print=True, **par_dict):
    """
        Update a FitProblem dictionary of parameters with the value and error taken from
        an input refl1d dictionary.

        @param output_name: name of the output dictionary entry
        @param layer_name: name of the layer
        @param par_name: name of the parameter in the input dictionary
        @param layer_dict: input dictionary of layer parameters
        @param output_params: list of fit output parameters
        @param par_dict: output parameter dictionary
    """
    value, error = find_error(layer_name, par_name, layer_dict, output_params)
    if pretty_print:
        value = "%s &#177; %s" % (value, error) if error > 0 else value
    par_dict[output_name] = value
    par_dict["%s_error"] = error
    return par_dict

def translate_model(refl_model, layers, output_params=None):
    """
        Modify a dictionary representing a refl1d model into a dictionary that
        can be mapped to a FitProblem.

        Note that constrained parameter names may be mixed in the reported refl1d model.
        See note below.
    """
    clean_layers = []
    refl_model = update_parameter('scale', '', 'intensity', refl_model, output_params, **refl_model)
    refl_model = update_parameter('background', '', 'background', refl_model, output_params, **refl_model)
    for i in range(len(layers)):
        try:
            name = layers[i].keys()[0].split(' ')[0]
            # Because of constraints, parameters can have the name of another layer.
            # For instance, if we set SiOx_interface of layer A to be equal to Si_interface
            # of layer B, we might see Si_interface in the list of parameters for layer A.
            # To make sure the reported layer name makes sense, use the name associated
            # with the thickness parameter if it's available.
            for par_name in layers[i].keys():
                if 'thickness' in par_name:
                    name = par_name.split(' ')[0]

            if i == 0:
                refl_model['back_name'] = name
                refl_model = update_parameter('back_sld', name, 'rho', layers[i], output_params, **refl_model)
                refl_model = update_parameter('back_roughness', name, 'interface', layers[i], output_params, **refl_model)
            elif i == len(layers)-1:
                refl_model['front_name'] = name
                refl_model = update_parameter('front_sld', name, 'rho', layers[i], output_params, **refl_model)
            else:
                layer_dict = dict(name=name, layer_number=len(layers)-i-1)
                layer_dict = update_parameter('thickness', name, 'thickness', layers[i], output_params, **layer_dict)
                layer_dict = update_parameter('sld', name, 'rho', layers[i], output_params, **layer_dict)
                layer_dict = update_parameter('roughness', name, 'interface', layers[i], output_params, **layer_dict)
                clean_layers.insert(0, layer_dict)
        except:
            logging.error("Could not process %s", str(layers))
            logging.error(sys.exc_value)
    return [refl_model, clean_layers]

def parse_slabs(content):
    """
        Parse the content of a refl1d log file.
        The part we are parsing is the list of models that looks like
        a dump of python objects written in a weird format:

        .sample
          .layers
            [0]
              .interface = Parameter(1.46935, name='Si interface', bounds=(1,5))
              .material
                .irho = Parameter(0, name='Si irho')
                .rho = Parameter(2.07, name='Si rho')
              .thickness = Parameter(0, name='Si thickness')
    """
    refl_model = dict(data_path="none")
    current_layer = {}
    layers = []
    chi2 = 0

    in_probe = False
    in_sample = False
    model_names = []
    model_list = []
    output_params = []

    for l in content.split('\n'):
        if l.startswith("[chisq="):
            in_sample = False
            result = re.search(r'chisq=([\d.]*)', l)
            if result is not None:
                refl_model['chi2'] = result.group(1)
        if l.startswith("[overall chisq="):
            result = re.search(r'chisq=([\d.]*)', l)
            if result is not None:
                chi2 = result.group(1)
        if l.startswith("SIMULTANEOUS"):
            clean_str = l.replace("SIMULTANEOUS ", "")
            model_names = json.loads(clean_str)

        if l.startswith("-- Model"):
            result = re.search(r"-- Model (\d+)", l)
            if result is not None:
                if len(refl_model) > 1:
                    if len(current_layer) > 0:
                        layers.append(current_layer)
                    model_list.append([refl_model, layers])
                layers = []
                current_layer = {}
                refl_model = dict(data_path=model_names[int(result.group(1))])

        if l.startswith('.probe'):
            in_probe = True
        elif in_probe:
            result = re.search(r".(\w*) = Parameter\((.*), name='(\w*)'", l)
            if result is not None:
                if result.group(1) == 'background':
                    refl_model['background'] = result.group(2)
                elif result.group(1) == 'intensity':
                    refl_model['intensity'] = result.group(2)

        if l.startswith('.sample'):
            in_probe = False
            in_sample = True
        elif in_sample:
            result = re.search(r"\[(\d+)\]", l)
            if result is not None:
                if len(current_layer) > 0:
                    layers.append(current_layer)
                current_layer = {}

            for name in [r"\.interface", r"\.irho", r"\.rho", r"\.thickness"]:
                result = re.search(r"%s = Parameter\((.*), name='([\w ]*)'" % name, l)
                if result is not None:
                    current_layer[result.group(2)] = result.group(1)

        par_name, value, error = parse_single_param(l)
        if par_name is not None:
            output_params.append([par_name, value, error])

        if l.startswith("MODEL_PARAMS_END"):
            if len(current_layer) > 0:
                layers.append(current_layer)
            model_list.append([refl_model, layers])

    # Add errors if they are available
    clean_model_list = []
    for r_model, l_model in model_list:
        clean_model_list.append(translate_model(r_model, l_model, output_params))
    return clean_model_list, chi2

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
        val_digits = len(mean_value.replace('.',''))
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
