#pylint: disable=invalid-name, line-too-long
"""
    Define url structure
"""
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$',                 views.modeling,     name='modeling'),
    url(r'^(?P<job_id>\d+)/$', views.is_completed, name='is_completed'),
    url(r'^private$',          views.private,      name='private'),

]
