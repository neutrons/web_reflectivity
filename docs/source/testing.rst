Testing
=======

The application code includes tests that exercise the majority of the functionality, including error scenarios.
For example, the tests found in ``web_reflectivity/fitting/tests.py`` use the django framework to create a test server that
includes an empty database to execute the tests with. Most of the functionality of the application can be tested
without actually executing the Refl1D jobs.


Running a test server
---------------------

You can easily deploy and test this application using Conda environments. The ``webrefl_env.yml`` file describes
an environment where we added the ``refl1d`` dependency for local computations, and where we use ``sqlite`` as our database::

        cd test/environment

        conda env create -f webrefl_env.yml

        source activate webrefl

The application depends on `redis <https://redis.io/>`_, which you may have to install separately.

The default installation directory is ``/var/www/web_reflectivity``.
Make sure you can write in the installation directory::

        sudo mkdir /var/www/web_reflectivity; sudo chown [username] /var/www/web_reflectivity

Make sure ``datahandler`` is one of the INSTALLED_APPS in ``settings.py``.

Install the code::

        make install

Create a test user::

        cd /var/www/web_reflectivity/app; python manage.py createsuperuser --username testuser


Start redis and celery, and the test server::

        redis-server
        cd /var/www/web_reflectivity/app; celery -A fitting.celery worker --loglevel=debug
        cd /var/www/web_reflectivity/app; python manage.py runserver


Using Refl1D
------------

The application creates and submits Refl1D jobs. In a production environment, those jobs are not running
locally and Refl1D is not installed on the web server. It is possible to test the functionality of most of
the application without actually executing the jobs. To execute the jobs locally, you have to set the following
variables in the Django settings.py file located in ``web_reflectivity/web_reflectivity/settings.py``:

        REFL1D_PATH = '[path to your anaconda installation]/anaconda/envs/webrefl/bin'
        REFL1D_JOB_DIR = '[path to a writable location where you want output files]'


Running system tests
--------------------

You can run the system tests included in the code by running::

    python manage.py test


.. toctree::
   :maxdepth: 2
   :caption: Contents: