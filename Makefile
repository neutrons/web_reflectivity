ifndef REFL_INSTALL_DIR
    prefix = /var/www/web_reflectivity
else
    prefix = $(REFL_INSTALL_DIR)
endif

app_dir := web_reflectivity
DJANGO_COMPATIBLE:=$(shell python -c "import django;t=0 if django.VERSION[1]<9 else 1; print t")
DJANGO_VERSION:=$(shell python -c "import django;print django.__version__")

ifndef PYTHON
PYTHON := python
endif

all:
	@echo "Run make install to install the live data server"

check:
	# Check dependencies
	@python -c "import django" || echo "\nERROR: Django is not installed: www.djangoproject.com\n"
	@python -c "import psycopg2" || echo "\nWARNING: psycopg2 is not installed: http://initd.org/psycopg\n"
	@python -c "import cython" || echo "\nWARNING: cython is not installed\n"
	@python -c "import pandas" || echo "\nWARNING: pandas is not installed\n"
	@python -c "import plotly" || echo "\nWARNING: plotly is not installed\n"
	@python -c "import plotly.offline" || echo "\nWARNING: plotly.offline is not installed\n"

ifeq ($(DJANGO_COMPATIBLE),1)
	@echo "Detected Django $(DJANGO_VERSION)"
else
	$(error Detected Django $(DJANGO_VERSION) < 1.9. The web monitor requires at least Django 1.9)
endif

deps:
	$(PYTHON) -m pip install -r requirements.txt

install: webapp

webapp/core:
	# Make sure the install directories exist
	test -d $(prefix) || mkdir -m 0755 -p $(prefix)
	test -d $(prefix)/app || mkdir -m 0755 $(prefix)/app
	test -d $(prefix)/static || mkdir -m 0755 $(prefix)/static
	test -d $(prefix)/media || mkdir -m 0755 $(prefix)/media
	
	# Install application code
	cp $(app_dir)/manage.py $(prefix)/app
	cp -R $(app_dir)/web_reflectivity $(prefix)/app
	echo "INSTALLATION_DIR = '$(prefix)'" >> $(prefix)/app/web_reflectivity/local_settings.py
	cp -R $(app_dir)/templates $(prefix)/app
	cp -R $(app_dir)/fitting $(prefix)/app
	cp -R $(app_dir)/datahandler $(prefix)/app
	cp -R $(app_dir)/users $(prefix)/app
	cp -R $(app_dir)/tools $(prefix)/app
	cp -R $(app_dir)/static $(prefix)/app

webapp: webapp/core
	# Collect the static files and install them
	cd $(prefix)/app; python manage.py collectstatic --noinput

	# Create migrations and apply them
	cd $(prefix)/app; python manage.py makemigrations
	cd $(prefix)/app; python manage.py migrate
	
	# Prepare web monitor cache: RUN THIS ONCE BY HAND
	#cd $(prefix)/app; python manage.py createcachetable webcache
	
	
	@echo "\n\nReady to go: run apachectl restart\n"
	
first_install: webapp/core
	# Modify and copy the wsgi configuration
	cp apache/apache_django_wsgi.conf /etc/httpd/conf.d

start:
	apachectl restart
	/sbin/service redis restart
	/sbin/service celery restart

create_app_dir:
	# Create deploy directory as root since it's in /var/www
	test -d $(prefix) || sudo mkdir -m 0755 -p $(prefix); sudo chown $(shell whoami) $(prefix);

start_test_server:
	redis-server
	cd $(prefix)/app; celery -A fitting.celery worker --loglevel=debug
	cd $(prefix)/app; python manage.py runserver

.PHONY: start
.PHONY: check
.PHONY: install
.PHONY: webapp
.PHONY: webapp/core
.PHONY: first_install
