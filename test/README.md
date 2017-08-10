- conda env create -f test_environment.yml
- source activate webrefl
- ``make install``

Go to the installation directory and start the server

- ``cd /var/www/web_reflectivity/app``

Create a test user

- ``python manage.py createsuperuser --username testuser``    pw=test1test
- ``python manage.py runserver``
