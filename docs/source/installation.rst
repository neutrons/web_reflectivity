Installation
============

Prerequisite
------------

Requirements for the application can be found in `requirements.txt`, which can be installed using::

    make deps


You will also need to install `redis-server <https://redis.io/>`_.

Test installation
-----------------

The information below describes how one would deploy the application in production. For a simpler test deployment,
see the instructions to :doc:`run a test server </testing>`.


Database installation
---------------------

The Django application will need a database. It was developed using PostgreSQL, but can be used with any database.
You can enter your database details in the `web_reflectivity/web_reflectivity/settings.py` file.


Authentication
--------------

The application supports both users local to the application or users authenticated through LDAP.
To use LDAP, the authentication settings should be entered in ``web_reflectivity/web_reflectivity/settings.py``.
For that purpose, ``openssl`` should be installed.

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