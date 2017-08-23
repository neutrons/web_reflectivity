Django Settings
===============

The following are the important Django settings to consider when deploying or testing the web application.

* REFL1D_PATH

    If REFL1D is not installed in ``/usr/bin``, you may modify its location. When running locally,
    the application will find the REFL1D installation that is part of your environment.

* REFL1D_JOB_DIR

    This is the working directory where the job will be executed. **The supplied directory needs to be writable by the user.**

* JOB_HANDLING_HOST and JOB_HANDLING_POST

    To use a remote compute resource, you can specify a host and post. Using ``localhost`` will run locally.
    The remote host should be able to receive ssh connections.

* JOB_HANDLING_INTERPRETER

    This allows you to specify the python interpreter to use to execute the job script. When running locally,
    the python interpreter from the environment the server is running in will be used.

* CELERY_*

    The Celery settings should not have to be modified. If your Celery server is not running in the
    default configuration, you may have to modify those settings.

* INSTALLED_APPS

    The ``datahandler`` app is listed by default in the ``INSTALLED_APPS``. When it is installed, uploaded data
    will be stored locally. This is the easiest way to deploy the application. Alternatively, once can use a
    `remote data server <https://github.com/neutrons/live_data_server>`_. This is generally not recommended
    and is outside the main scope of this software.





Adding a local settings file
----------------------------

For convenience, it is possible to add a ``local_settings.py`` file next to Django's ``settings.py``.
This file will supplement ``settings.py`` and can be used as a way to modify settings without changing source-controlled code.