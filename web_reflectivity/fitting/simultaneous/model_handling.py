#pylint: disable=line-too-long, bare-except
"""
    Handle multiple FitProblem objects for simultaneous fitting.
"""
import sys
import logging
from django_remote_submission.models import Log
from ..models import SimultaneousModel, SimultaneousFit
from ..parsing import refl1d_err_model
from .. import view_util

def get_simultaneous_models(request, fit_problem, setup_request=False):
    """
        Find related models and return a list of dictionary representing them.
        #TODO: CHI^2
    """
    error_list = []
    model_list = []
    chi2 = 1

    # Find the latest fit
    simul_list = SimultaneousFit.objects.filter(user=request.user, fit_problem=fit_problem)
    results_ready = len(simul_list) > 0
    if not setup_request and len(simul_list) > 0:
        remote_job = simul_list[0].remote_job
        if remote_job is not None:
            try:
                error_list.append("Job status: %s" % remote_job.status)
                job_logs = Log.objects.filter(job=remote_job)
                if len(job_logs) > 0:
                    latest = job_logs.latest('time')
                    model_list, chi2 = refl1d_err_model.parse_slabs(latest.content)
                    #TODO: do we need to apply constraints?
                    if chi2 is None:
                        error_list.append("The fit results appear to be incomplete.")
                else:
                    error_list.append("No results found")
            except:
                logging.error("Problem retrieving results: %s", sys.exc_value)
                error_list.append("Problem retrieving results")

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

    return model_list, error_list, chi2, results_ready
