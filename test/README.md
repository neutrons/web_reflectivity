- conda env create -f test_environment.yml
- source activate webrefl

Make sure you can write in the installation directory, or change it at the top of the Makefile
- ``sudo mkdir /var/www/reflectivity; sudo chown [username] /var/www/reflectivity``
- ``make install``

Go to the installation directory and start the server

- ``cd /var/www/web_reflectivity/app``

Create a test user

- ``python manage.py createsuperuser --username testuser``    pw=test1test
- ``python manage.py runserver``


Start redis and celery

- ``redis-server``
- ``cd /var/www/web_reflectivity/app; celery -A fitting.celery worker --loglevel=debug``