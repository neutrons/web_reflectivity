#pylint: disable=line-too-long, bare-except, consider-using-enumerate, invalid-name, too-many-locals
"""
    Handle multiple FitProblem objects for simultaneous fitting.
"""
import sys
import logging
import io
import pandas
import numpy as np
from django_remote_submission.models import Log
from ..models import SimultaneousModel, SimultaneousFit
from ..parsing import refl1d_err_model, refl1d, refl1d_simultaneous
from .. import view_util, job_handling, data_server

def get_simultaneous_models(request, fit_problem, setup_request=False):
    """
        Find related models and return a list of dictionary representing them.

        :param Request request: http request object
        :param FitProblem fit_problem: FitProblem object
        :param bool setup_request: if True, the model will get set up from related fit problems
    """
    error_list = []
    model_list = []
    fitproblem_list = None
    chi2 = None

    # Find the latest fit
    simul_list = SimultaneousFit.objects.filter(user=request.user, fit_problem=fit_problem)
    fit_exists = len(simul_list) > 0
    can_update = False
    if not setup_request and len(simul_list) > 0:
        try:
            remote_job = simul_list[0].remote_job
            if remote_job is not None:
                can_update = remote_job.status not in [remote_job.STATUS.success,
                                                       remote_job.STATUS.failure]
                error_list.append("Job status: %s" % remote_job.status)
                job_logs = Log.objects.filter(job=remote_job)
                if len(job_logs) > 0:
                    latest = job_logs.latest('time')
                    # Check whether we need to deal with a legacy log
                    if refl1d_simultaneous.check_compatibility(latest.content):
                        model_list, chi2, fitproblem_list = refl1d_simultaneous.parse_models_from_log(latest.content)
                    else:
                        logging.error("Found a legacy log. FitProblem=%s", fit_problem.id)
                        model_list, chi2 = refl1d_err_model.parse_slabs(latest.content)
                    if chi2 is None:
                        error_list.append("The fit results appear to be incomplete.")
                else:
                    error_list.append("No results found")
        except:
            logging.error("Problem retrieving results: %s", sys.exc_value)
            error_list.append("Problem retrieving results")
            raise

    # If we could not find results, use the individual fits as a starting point
    if len(model_list) == 0:
        data_list = [fit_problem]
        # Find the extra data sets to fit together
        for item in SimultaneousModel.objects.filter(fit_problem=fit_problem):
            instrument_, data_id_ = view_util.parse_data_path(item.dependent_data)
            _, extra_fit = view_util.get_fit_problem(request, instrument_, data_id_)
            if extra_fit is None:
                error_list.append("No existing fit found for %s: fit it by itself first" % item.dependent_data)
            else:
                data_list.append(extra_fit)
        # Assemble the models to display
        model_list = []
        for item in data_list:
            model_list.append(item.model_to_dicts())

    return model_list, error_list, chi2, fit_exists, can_update, fitproblem_list

def assemble_plots(request, fit_problem, result_fitproblems=None):
    """
        Find all that needs to be plotted for this fit problem.

        :param Request request: http request object
        :param FitProblem fit_problem: FitProblem object
        :param list result_fitproblems: list of FitProblem-like objects
    """
    r_plot = ""
    # Check whether we need to change the y-axis scale
    rq4 = request.session.get('rq4', False)

    if result_fitproblems is not None:
        data_list, data_names, sld_list, sld_names = create_plots_from_fit_problem(result_fitproblems, rq4)
    else:
        data_list, data_names, sld_list, sld_names = create_plots_from_legacy_log(request, fit_problem)

    y_title = u"Reflectivity x Q<sup>4</sup> (1/A<sup>4</sup>)" if rq4 else u"Reflectivity"

    if len(data_list) > 0:
        r_plot = view_util.plot1d(data_list, data_names=data_names, x_title=u"Q (1/A)", y_title=y_title)

    # Compute asymmetry
    if len(data_list) == 4:
        asym_data = compute_asymmetry(data_list[0], data_list[2])
        asym_theory = compute_asymmetry(data_list[1], data_list[3])
        chi2_asym = np.sum(np.sqrt((asym_data[1]-asym_theory[1])**2/asym_data[2]**2))/len(asym_data[0])
        extra_plot = view_util.plot1d([asym_data, asym_theory],
                                      x_log=True, y_log=False,
                                      data_names=[u'(r1 - r2) / r1', u'Fit [\u03a7\u00b2 = %2.2g]' % chi2_asym],
                                      x_title=u"Q (1/A)", y_title=u'Asymmetry')
        r_plot = "<div>%s</div><div>%s</div>" % (r_plot, extra_plot)

    if len(sld_list) > 0:
        extra_plot = view_util.plot1d(sld_list, x_log=False, y_log=False,
                                      data_names=sld_names, x_title=u"Z (A)",
                                      y_title=u'SLD (10<sup>-6</sup>/A<sup>2</sup>)')
        r_plot = "<div>%s</div><div>%s</div>" % (r_plot, extra_plot)

    return r_plot

def create_plots_from_fit_problem(problem_list, rq4=False):
    """
        Create reflectivity and SLD plots from a set of FitProblem-like objects.
        :param list problem_list: list of FitProblem-like objects
        :param bool rq4: if True, we plot R*Q^4
    """
    data_list = []
    data_names = []
    sld_list = []
    sld_names = []
    for problem in problem_list:
        instrument, data_id = view_util.parse_data_path(problem.reflectivity_model.data_path)
        # If we have the data, compute the theory curve and return it
        html_data = data_server.data_handler.get_plot_data_from_server(instrument, data_id)
        if html_data is not None:
            current_str = io.StringIO(view_util.extract_ascii_from_div(html_data))
            current_data = pandas.read_csv(current_str, delim_whitespace=True, comment='#', names=['q','r','dr','dq'])
            _q, _r, _z, _sld, _ = job_handling.compute_reflectivity(current_data['q'], current_data['r'],
                                                                    current_data['dr'], current_data['dq'], problem)

            # Raw data
            _r_data = current_data['r'] * current_data['q']**4 if rq4 else current_data['r']
            _dr_data = current_data['dr'] * current_data['q']**4 if rq4 else current_data['dr']
            data_list.append([current_data['q'], _r_data, _dr_data])
            data_names.append(problem.reflectivity_model.data_path)

            _r = _r * _q**4 if rq4 else _r
            data_list.append([_q, _r])
            data_names.append(problem.reflectivity_model.data_path)
            sld_list.append([_z, _sld])
            sld_names.append(problem.reflectivity_model.data_path)


    return data_list, data_names, sld_list, sld_names

# --------------------------------------------------------------------------------------
# LEGACY CODE for backward compatibility only
def _process_rq4(request, data, tag):
    """
        Process the user's request for R * Q^4.
    """
    rq4 = request.session.get('rq4', False)
    if rq4 is True:
        return data[tag] * data['q']**4
    return data[tag]

def create_plots_from_legacy_log(request, fit_problem):
    """
        Legacy log parsing code. Only used when we encounter an old log.
    """
    data_list = []
    data_names = []
    sld_list = []
    sld_names = []

    # Find the latest fit
    simul_list = SimultaneousFit.objects.filter(user=request.user, fit_problem=fit_problem)
    if len(simul_list) > 0 and simul_list.latest('timestamp').remote_job is not None:
        remote_job = simul_list.latest('timestamp').remote_job
        try:
            job_logs = Log.objects.filter(job=remote_job)
            if len(job_logs) > 0:
                latest = job_logs.latest('time')
                i_problem = -1
                for data_path, data_log in refl1d.extract_multi_data_from_log(latest.content):
                    i_problem += 1
                    raw_data = pandas.read_csv(io.StringIO(data_log), delim_whitespace=True,
                                               comment='#', names=['q', 'dq', 'r', 'dr', 'theory', 'fresnel'])
                    data_list.extend([[raw_data['q'], _process_rq4(request, raw_data, 'r'), _process_rq4(request, raw_data, 'dr')],
                                      [raw_data['q'], _process_rq4(request, raw_data, 'theory')]])
                    data_names.extend([data_path, data_path])

                # Extract SLD
                sld_block_list = refl1d.extract_multi_sld_from_log(latest.content)
                for data_path, data_log in sld_block_list:
                    raw_data = pandas.read_csv(io.StringIO(data_log), delim_whitespace=True,
                                               comment='#', names=['z', 'rho', 'irho'])
                    sld_list.append([raw_data['z'], raw_data['rho']])
                    sld_names.append(data_path)
        except:
            logging.error("Could not extract data from log for %s", fit_problem.reflectivity_model.data_path)
            logging.error(sys.exc_value)
    return data_list, data_names, sld_list, sld_names
# --------------------------------------------------------------------------------------

def compute_asymmetry(data_1, data_2):
    """
        Compute asymmetry between two data sets.

        :param array data_1: data array
        :param array data_2: data array
    """
    asym_q = []
    asym_values = []
    asym_errors = []

    q1, r1 = data_1[0], data_1[1]
    q2, r2 = data_2[0], data_2[1]
    dr1 = data_1[2] if len(data_1) == 3 else None
    dr2 = data_2[2] if len(data_2) == 3 else None

    for i in range(len(q1)):
        for j in range(len(q2)):
            if np.fabs(q1[i] - q2[j]) < 0.0001:
                try:
                    asym = (r1[i] - r2[j]) / r1[i]
                    if dr1 is not None and dr2 is not None:
                        asym_err = np.sqrt(dr2[j]**2/r1[i]**2 + r2[j]**2*dr1[i]**2/r1[i]**4)
                    asym_q.append(q1[i])
                    asym_values.append(asym)
                    asym_errors.append(asym_err)
                except:
                    # Bad point, skip it
                    pass
    if len(asym_errors) == len(asym_q):
        return [np.asarray(asym_q), np.asarray(asym_values), np.asarray(asym_errors)]
    return [np.asarray(asym_q), np.asarray(asym_values)]
