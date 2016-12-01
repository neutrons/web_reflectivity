import warnings
from scipy.stats.distributions import chi2
warnings.filterwarnings("ignore", module="matplotlib")
import numpy as np
import pandas
import logging
import re

import plotly.offline as py
import plotly.graph_objs as go


def plot_r(data, log_type='log'):
    traces = []
    err_y = dict(type='data', array=data['dr'], visible=True, thickness=1, width=2)
    traces.append(go.Scatter(name="Data", x=data['q'], y=data['r'], error_y=err_y,
                             mode="markers", marker=dict(size=4)))
    traces.append(go.Scatter(name="Fit", x=data['q'], y=data['theory'],
                             line=dict(color="rgb(102, 102, 102)",width=1)))

    x_layout = dict(title=u"Q (1/\u212b)", zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True, type='log',
                    showline=True, mirror="all", ticks="inside")

    y_layout = dict(title="Reflectivity", zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True, type=log_type,
                    showline=True, mirror="all", ticks="inside")

    layout = go.Layout(
        showlegend=False,
        autosize=True,
        width=800,
        height=500,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode='closest',
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout
    )

    fig = go.Figure(data=traces, layout=layout)
    py.iplot(fig, show_link=False)

def plot_sld(data):
    # Plot the SLD profile
    sld_trace = go.Scatter(name="Fit", x=data['z'], y=data['rho'],
                           line=dict(color="rgb(102, 102, 102)",width=1))
    

    x_layout = dict(title=u"Depth (\u212b)", zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True, type='linear',
                    showline=True, mirror="all", ticks="inside")

    y_layout = dict(title=u"SLD (10<sup>-6</sup> \u212b<sup>-2</sup>)", zeroline=False, exponentformat="power",
                    showexponent="all", showgrid=True, type='linear',
                    showline=True, mirror="all", ticks="inside")
    layout = go.Layout(
        showlegend=False,
        autosize=True,
        width=800,
        height=500,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode='closest',
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout
    )
    layout["xaxis"] = x_layout
    layout["yaxis"] = y_layout
    fig = go.Figure(data=[sld_trace], layout=layout)
    py.iplot(fig, show_link=False)

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

def prepare_fit(reduced_file):
    import os
    with open('__model.py', 'r') as fd:
        c=fd.read().replace("{{REDUCED_FILE}}", '"%s"' % reduced_file)
    with open('__model.py', 'w') as fd:
        fd.write(c)
    base_name = os.path.basename(reduced_file)
    filename, _ = os.path.splitext(base_name)
    return "%s_results" % filename

def report_fit(output_dir, model_basename='__model', log_type='log'):
    print("Results saved in: %s\n" % output_dir)
    parse_params('%s/%s.err' % (output_dir, model_basename))
    
    # Read the reflectivity output and plot it
    DATASET_NAME = '%s/%s-refl.dat' % (output_dir, model_basename)
    raw_data = pandas.read_csv(DATASET_NAME, delim_whitespace=True, comment='#', names=['q','dq','r','dr','theory','fresnel'])
    plot_r(raw_data, log_type=log_type)

    # Read the SLD profile and plot it
    DATASET_NAME = '%s/%s-profile.dat' % (output_dir, model_basename)
    sld_data = pandas.read_csv(DATASET_NAME, delim_whitespace=True, comment='#', names=['z','rho','irho'])
    plot_sld(sld_data)
    
    # Bumps output images
    from IPython.core.display import Image, display
    display(Image("%s/__model-vars.png" % output_dir))
    display(Image("%s/__model-corr.png" % output_dir))