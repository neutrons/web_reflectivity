prefix := /var/www/web_reflectivity
app_dir := web_reflectivity
DJANGO_COMPATIBLE:=$(shell python -c "import django;t=0 if django.VERSION[1]<9 else 1; print t")
DJANGO_VERSION:=$(shell python -c "import django;print django.__version__")

all:
	@echo "Run make install to install the live data server"

check:
	# Check dependencies
	@python -c "import django" || echo "\nERROR: Django is not installed: www.djangoproject.com\n"
	@python -c "import psycopg2" || echo "\nWARNING: psycopg2 is not installed: http://initd.org/psycopg\n"
	@python -c "import corsheaders" || echo "\nWARNING: django-cors-headers is not installed: https://github.com/ottoyiu/django-cors-headers\n"

ifeq ($(DJANGO_COMPATIBLE),1)
	@echo "Detected Django $(DJANGO_VERSION)"
else
	$(error Detected Django $(DJANGO_VERSION) < 1.9. The web monitor requires at least Django 1.9)
endif


install: webapp

webapp/core:
	# Make sure the install directories exist
	test -d $(prefix) || mkdir -m 0755 -p $(prefix)
	test -d $(prefix)/app || mkdir -m 0755 $(prefix)/app
	test -d $(prefix)/static || mkdir -m 0755 $(prefix)/static
	
	# Install application code
	cp $(app_dir)/manage.py $(prefix)/app
	cp -R $(app_dir)/web_reflectivity $(prefix)/app
	cp -R $(app_dir)/templates $(prefix)/app
	cp -R $(app_dir)/fitting $(prefix)/app
	cp -R $(app_dir)/static $(prefix)/app

	# The following should be done with the proper apache user
	#chgrp apache $(prefix)/static/web_monitor
	#chown apache $(prefix)/static/web_monitor

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

.PHONY: check
.PHONY: install
.PHONY: webapp
.PHONY: webapp/core
.PHONY: first_install
