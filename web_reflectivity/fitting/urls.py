#pylint: disable=invalid-name, line-too-long
"""
    Define url structure
"""
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$',                                         views.landing_page,       name='modeling'),
    url(r'^(?P<job_id>\d+)/$',                         views.is_completed,       name='is_completed'),
    url(r'^private$',                                  views.private,            name='private'),
    url(r'^files',                                     views.FileView.as_view(), name='show_files'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/$',  views.FitView.as_view(),  name='fit'),
]
