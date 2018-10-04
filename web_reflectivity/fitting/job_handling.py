#pylint: disable=bare-except, invalid-name, line-too-long, too-many-arguments, too-many-locals
"""
    Abstraction layer for handling fitting jobs
"""
from __future__ import absolute_import, division, print_function
import sys
import string
import os
import numpy as np
import refl1d
import refl1d.names as rf

from django.conf import settings

def create_model_file(data_form, layer_forms, data_file=None, ascii_data="", output_dir='/tmp',
                      fit=True, options={}, constraints=[], template='reflectivity_model.py.template',
                      sample_name='sample', probe_name='probe', expt_name='expt'):
    """
        Create a refl1d model file from a template
    """
    #TODO: rewrite this to take a fit_problem object
    if data_file is None:
        data_file = data_form.cleaned_data['data_path']
    materials = data_form.get_materials()
    layer_list = []
    ranges = ''
    for form in layer_forms:
        if form.info_complete():
            materials += "%s\n" % form.get_materials()
            layer_list.append(form.get_layer())
            if fit is True:
                ranges += form.get_ranges(sample_name=sample_name)

    # Add constraints
    ranges += '\n'
    for item in constraints:
        ranges += item.get_ranges(sample_name=sample_name, probe_name=probe_name)

    layer_list.reverse()
    _layers = ' | '.join(layer_list)
    if len(layer_list) > 0:
        _layers += ' | '
    sample_template = data_form.get_sample_template()
    sample = "%s = " % sample_name + sample_template % _layers
    if fit is True:
        sample_ranges = data_form.get_ranges(sample_name=sample_name, probe_name=probe_name)
    else:
        sample_ranges = data_form.get_predefined_intensity_range(probe_name=probe_name)

    template_dir, _ = os.path.split(os.path.abspath(__file__))
    with open(os.path.join(template_dir, 'job_templates', template), 'r') as fd:
        template = fd.read()
        model_template = string.Template(template)

        # Fitting engine
        engine = options.get('engine', 'dream')

        # Determine number of steps for refl1d
        default_value = 1000 if fit else 1
        if fit is False:
            steps = default_value
            burn = default_value
            engine = 'amoeba'
        else:
            steps = options.get('steps', default_value)
            burn = options.get('burn', default_value)

        # If we are running locally, find the environment's REFL1D
        refl1d_path = settings.REFL1D_PATH
        if settings.JOB_HANDLING_HOST == 'localhost':
            refl1d_path = os.path.split(sys.executable)[0]

        script = model_template.substitute(REDUCED_FILE=data_file,
                                           REFL1D_VERSION=refl1d.__version__,
                                           Q_MIN=data_form.cleaned_data['q_min'],
                                           Q_MAX=data_form.cleaned_data['q_max'],
                                           MATERIALS=materials,
                                           SAMPLE=sample,
                                           SAMPLE_NAME=sample_name,
                                           PROBE_NAME=probe_name,
                                           EXPT_NAME=expt_name,
                                           RANGES=ranges,
                                           ENGINE=engine,
                                           ASCII_DATA=ascii_data,
                                           OUTPUT_DIR=output_dir,
                                           REFL1D_PATH=refl1d_path,
                                           REFL1D_STEPS=steps,
                                           REFL1D_BURN=burn,
                                           SAMPLE_RANGES=sample_ranges)

    return script

def assemble_data_setup(data_list):
    """ Write the portion of the job script related to data files """
    template_dir, _ = os.path.split(os.path.abspath(__file__))
    script = ''
    with open(os.path.join(template_dir, 'job_templates', 'simultaneous_data.py.template'), 'r') as fd:
        template = fd.read()
        model_template = string.Template(template)

    for data_file, ascii_data in data_list:
        script += model_template.substitute(REDUCED_FILE=data_file,
                                            ASCII_DATA=ascii_data)
    return script

def assemble_job(model_script, data_script, expt_names, data_ids, options, work_dir, output_dir='/tmp'):
    """ Write the portion of the job script related to data files """
    template_dir, _ = os.path.split(os.path.abspath(__file__))
    script = ''
    with open(os.path.join(template_dir, 'job_templates', 'simultaneous_job.py.template'), 'r') as fd:
        template = fd.read()
        model_template = string.Template(template)
        # If we are running locally, find the environment's REFL1D
        refl1d_path = settings.REFL1D_PATH
        if settings.JOB_HANDLING_HOST == 'localhost':
            refl1d_path = os.path.split(sys.executable)[0]
        script += model_template.substitute(PROCESS_DATA=data_script,
                                            REFL1D_VERSION=refl1d.__version__,
                                            MODELS=model_script,
                                            WORK_DIR=work_dir,
                                            EXPT_LIST='[%s]' % ','.join(expt_names),
                                            EXPT_IDS = '[%s]' % ','.join(['\"%s\"' % d for d in data_ids]),
                                            ENGINE=options.get('engine', 'dream'),
                                            OUTPUT_DIR=output_dir,
                                            REFL1D_PATH=refl1d_path,
                                            REFL1D_STEPS=options.get('steps', 1000),
                                            REFL1D_BURN=options.get('burn', 1000))
    return script

def compute_reflectivity(q, r, dr, dq, fit_problem):
    """
        Create a refl1d model file from a template
        :param list q: q values
        :param list r: reflectivity values
        :param list dr: error on the reflectivity values
        :param list dq: q resolution as FWHM
        :param FitProblem fit_problem: fit problem object
    """
    q = np.asarray(q)
    dq = np.asarray(dq)
    zeros = np.zeros(len(q))
    i_min = min([i for i in range(len(q)) if q[i]>fit_problem.reflectivity_model.q_min])
    i_max = max([i for i in range(len(q)) if q[i]<fit_problem.reflectivity_model.q_max])+1

    # SNS data is FWHM
    dq_std = dq/2.35
    probe = rf.QProbe(q[i_min:i_max], dq_std[i_min:i_max], data=(zeros, zeros))

    sample = rf.Slab(material=rf.SLD(name=fit_problem.reflectivity_model.back_name,
                                     rho=fit_problem.reflectivity_model.back_sld),
                     interface=fit_problem.reflectivity_model.back_roughness)
    for layer in fit_problem.layers.all().order_by('-layer_number'):
        sample = sample | rf.Slab(material=rf.SLD(name=layer.name,
                                                  rho=layer.sld,
                                                  irho=layer.i_sld),
                                  thickness=layer.thickness,
                                  interface=layer.roughness)

    sample = sample | rf.Slab(material=rf.SLD(name=fit_problem.reflectivity_model.front_name,
                                              rho=fit_problem.reflectivity_model.front_sld))

    probe.intensity = rf.Parameter(value=fit_problem.reflectivity_model.scale, name='scale')
    probe.background = rf.Parameter(value=fit_problem.reflectivity_model.background, name='background')
    expt = rf.Experiment(probe=probe, sample=sample)
    q, _r = expt.reflectivity()
    z, sld, _ = expt.smooth_profile()

    if r is not None and dr is not None:
        chi2 = np.sum((r[i_min:i_max]-_r)**2/dr[i_min:i_max]**2)/len(_r)
    else:
        chi2 = None

    return q, _r, z, sld, chi2
