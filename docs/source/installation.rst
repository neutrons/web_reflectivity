Test installation
=================

The information below describes how one would deploy the application in production. For a simpler test deployment,
see the instructions to [run a test server](test/README.md). Those instructions will walk you through a basic 
installation process and will give you a list of dependencies you'll need.

Production configuration and installation
=========================================

Production dependencies
-----------------------

A basic set of requirements for the application can be found in `requirements.txt`.
This is only recommended if you are installing more than a test environment and will be deploying your
own database and adjusting your configuration yourself. It will not be sufficient for testing (see the test
installation section above). Depending on which database and authentication solution you choose, your
dependencies may change.


Database installation
---------------------

The Django application will need a database. It was developed using PostgreSQL, but can be used with any database.
You can enter your database details in the `web_reflectivity/web_reflectivity/settings.py` file.


Authentication
--------------

The application supports both users local to the application or users authenticated through LDAP.
To use LDAP, the authentication settings should be entered in ``web_reflectivity/web_reflectivity/settings.py``.
For that purpose, ``openssl`` should be installed.

If you do not want to use LDAP and want to avoid unnecessary error messages, remove ``django_auth_ldap.backend.LDAPBackend``
from the list of authentication backends::

    AUTHENTICATION_BACKENDS = (
                               'django_auth_ldap.backend.LDAPBackend',
                               'django.contrib.auth.backends.ModelBackend',
                               )

Once a user is logged in, the application will submit jobs to your compute resources on the user's behalf, through celery.
An ssh key should be generated and placed in the apache user's .ssh directory. It should also be copied in the celery user's .ssh directory.


Apache configuration
--------------------

The application was developed using ``apache`` and ``mod_wsgi``, although it could be served by other methods compatible with Django.
An example apache configuration is available in ``apache/apache_django_wsgi.conf``. This file can be modified with your SSL details
and put in ``/etc/httpd/cond.d``.


Redis configuration
-------------------
Redis can be run with default configuration.


Celery configuration
--------------------

On a production system, you will want to run celery as a service.
To do this, copy the ``web_reflectivity/web_reflectivity/celeryd`` file into ``/etc/default/celeryd``

Install the application
-----------------------

The application installs in ``/var/www/web_reflectivity``::

    sudo make install


Starting the application
------------------------

Start redis::

    sudo /sbin/service redis start


Start celery::

    sudo /sbin/service celeryd start


Start apache::

    sudo /sbin/service httpd restart




.. toctree::
   :maxdepth: 2
   :caption: Contents:
