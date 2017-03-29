#pylint: disable=invalid-name, line-too-long
"""
    Define url structure
"""
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$',                                                    views.FileView.as_view(),       name='modeling'),
    url(r'^(?P<job_id>\d+)/$',                                    views.is_completed,             name='is_completed'),
    url(r'^private/$',                                            views.private,                  name='private'),
    url(r'^files/$',                                              views.FileView.as_view(),       name='show_files'),
    url(r'^list/$',                                               views.FitListView.as_view(),    name='show_fits'),
    url(r'^options/$',                                            views.FitterOptionsUpdate.as_view(success_url='/fit/options'), name='options'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/$',             views.FitView.as_view(),        name='fit'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/model/$',       views.download_model,           name='download_model'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/download/$',    views.download_fit_data,        name='download_data'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/reverse/$',     views.reverse_model,            name='reverse_model'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/constraints/$', views.ConstraintView.as_view(), name='constraints'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/constraints/(?P<const_id>\d+)/$', views.ConstraintView.as_view(), name='constraints_edit'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/constraints/(?P<const_id>\d+)/remove/$', views.remove_constraint, name='constraints_remove'),
]
