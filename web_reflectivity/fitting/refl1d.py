"""
    Interface to refl1d
"""
import logging
import re

def parse_params(model_err_content):
    """
        [chisq=23.426(15), nllf=1850.62]
                      Parameter       mean  median    best [   68% interval] [   95% interval]
         1            intensity  1.084(31)  1.0991  1.1000 [  1.062   1.100] [  1.000   1.100]
         2              air rho 0.91(91)e-3 0.00062 0.00006 [ 0.0001  0.0017] [ 0.0000  0.0031]
    """
    output = {}
    start_data = False

    for line in model_err_content.split('\n'):
        if start_data:
            try:
                par_name, value, error = parse_single_param(line)
                if par_name is not None:
                    toks = par_name.split(' ')
                    if toks[0] not in output:
                        output[toks[0]] = {'name':toks[0]}
                    if toks[0] == 'intensity':
                        output['scale'] = value
                        output['scale_error'] = error
                    elif toks[0] == 'background':
                        output['background'] = value
                        output['background_error'] = error
                    elif toks[0] == 'background':
                        output[toks[0]]['background'] = value
                        output[toks[0]]['background_error'] = error
                    elif toks[1] == 'rho':
                        output[toks[0]]['sld'] = value
                        output[toks[0]]['sld_error'] = error
                    elif toks[1] == 'thickness':
                        output[toks[0]]['thickness'] = value
                        output[toks[0]]['thickness_error'] = error
                    elif toks[1] == 'interface':
                        output[toks[0]]['roughness'] = value
                        output[toks[0]]['roughness_error'] = error
            except:
                logging.error("Could not parse line %s", line)

        # Find chi^2, which comes just before the list of parameters
        if line.startswith('[chi'):
            start_data = True
            try:
                result = re.search('chisq=([\d.]*)', line)
                chi2=result.group(1)
            except:
                chi2="unknown"
        if line.startswith('Done:'):
            start_data = False

    try:
        output['chi2'] = float(chi2)
    except:
        output['chi2'] = None
    return output

def get_latest_results(content, initial_values, initial_layers):
    """
        Look for the latest results for this data set.
    """
    params = parse_params(content)

    for item in initial_layers:
        if item['name'] in params:
            item.update(params[item['name']])

    for boundary in ['front', 'back']:
        boundary_name = boundary+'_name'
        if initial_values[boundary_name] in params:
            for key in ['sld', 'roughness', 'thickness', 'sld_error', 'roughness_error', 'thickness_error']:
                if key in params[initial_values[boundary_name]]:
                    initial_values['%s_%s' % (boundary, key)] = params[initial_values[boundary_name]][key]
            initial_values.update(params[initial_values[boundary_name]])

    for item in ['scale', 'background', 'scale_error', 'background_error']:
        if item in params:
            initial_values[item] = params[item]
    return initial_values, initial_layers, params['chi2']

def extract_data_from_log(log_content, log_type='log'):
    """
        @param log_content: string buffer of the job log
    """
    # Parse out the portion we need
    data_started = False
    data_content = []
    for line in log_content.split('\n'):
        if line.startswith("REFL_START"):
            data_started = True
        elif line.startswith("REFL_END"):
            data_started = False
        elif data_started is True:
            data_content.append(line)
    if len(data_content) == 0:
        return None
    data_str = '\n'.join(data_content)
    return data_str

def parse_single_param(line):
    result = re.search(r'^\d (.*) ([\d.-]+)\((\d+)\)(e?[\d-]*)\s* [\d.-]+\s* ([\d.-]+) ', line.strip())
    value_float = None
    error_float = None
    par_name = None
    if result is not None:
        par_name = result.group(1).strip()
        exponent = result.group(4)
        mean_value = "%s%s" % (result.group(2), exponent)
        error = "%s%s" % (result.group(3), exponent)
        best_value = "%s%s" % (result.group(5), exponent)

        # Error string does not have a .
        err_digits = len(error)
        val_digits = len(mean_value.replace('.',''))
        err_value = ''
        i_digit = 0

        for c in mean_value:
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
