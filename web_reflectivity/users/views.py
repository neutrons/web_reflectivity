"""
    User management
"""
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.contrib.auth import login, logout, authenticate
from django_remote_submission.remote import RemoteWrapper, deploy_key_if_it_doesnt_exist

# Application-specific imports
from django.conf import settings
from users.view_util import fill_template_values

def perform_login(request):
    """
        Perform user authentication
    """
    user = None
    login_failure = None
    if request.method == 'POST':
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(username=username, password=password)
        if user is not None and not user.is_anonymous():
            try:
                wrapper = RemoteWrapper(hostname=settings.JOB_HANDLING_HOST,
                                        username=username, port=settings.JOB_HANDLING_POST)
                wrapper.connect(password)
                wrapper.close()
                login(request,user)
            except:
                login_failure = ["Could not connect to computing resource: it may be unavailable"]
        else:
            login_failure = ["Invalid username or password"]

    if request.user.is_authenticated():
        # If we came from a given page and just needed
        # authentication, go back to that page.
        if "next" in request.GET:
            redirect_url = request.GET["next"]
            return redirect(redirect_url)
        return redirect(reverse(settings.LANDING_VIEW))
    else:
        # Breadcrumbs
        breadcrumbs = "<a href='%s'>home</a> &rsaquo; login" % reverse(settings.LANDING_VIEW)

        template_values = {'breadcrumbs': breadcrumbs,
                           'user_alert': login_failure}
        template_values = fill_template_values(request, **template_values)
        return render(request, 'users/authenticate.html', template_values)

def perform_logout(request):
    """
        Logout user
    """
    logout(request)
    return redirect(reverse(settings.LANDING_VIEW))
