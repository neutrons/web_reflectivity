# Installation
You can easily deploy and test this application using Conda environments. The ``webrefl_env.yml`` file describes
an environment where we added the ``refl1d`` dependency for local computations, and where we use ``sqlite`` as our database.

        conda env create -f webrefl_env.yml

        source activate webrefltest

The application depends on [redis](https://redis.io/), which you may have to install separately.

The default installation directory is ``/var/www/web_reflectivity``.
Make sure you can write in the installation directory.

        sudo mkdir /var/www/reflectivity; sudo chown [username] /var/www/reflectivity

Make sure ``datahandler`` is one of the INSTALLED_APPS in ``settings.py``.

Install the code:

        make install

Create a test user:

        cd /var/www/web_reflectivity/app; python manage.py createsuperuser --username testuser


# Running the test server
Start redis and celery, and the test server:

        redis-server
        cd /var/www/web_reflectivity/app; celery -A fitting.celery worker --loglevel=debug
        cd /var/www/web_reflectivity/app; python manage.py runserver
