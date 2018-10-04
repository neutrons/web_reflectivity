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
    url(r'^models/$',                                             views.ModelListView.as_view(),  name='show_models'),
    url(r'^problem/(?P<pk>[\w-]+)/delete/$',                      views.FitProblemDelete.as_view(success_url='/fit/list'), name='delete_problem'),
    url(r'^model/(?P<pk>[\w-]+)/delete/$',                        views.SaveModelDelete.as_view(success_url='/fit/models'), name='delete_model'),
    url(r'^simultaneous/(?P<pk>[\w-]+)/delete/$',                 views.remove_simultaneous_model, name='remove_simultaneous_model'),
    url(r'^model/(?P<pk>[\w-]+)/$',                               views.SaveModelUpdate.as_view(success_url='/fit/models'), name='update_model'),
    url(r'^list/$',                                               views.FitListView.as_view(),    name='show_fits'),
    url(r'^options/$',                                            views.FitterOptionsUpdate.as_view(success_url='/fit/options'), name='options'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/info/$',        views.UpdateUserDataView.as_view(), name='data_info'),
    url(r'^files/(?P<pk>[\w-]+)/delete/$',                        views.UserDataDelete.as_view(success_url='/fit/files'), name='data_delete'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/$',             views.FitView.as_view(),        name='fit'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/append/$',      views.FitAppend.as_view(),      name='fit_append'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/model/$',       views.download_model,           name='download_model'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/apply/(?P<pk>[\w-]+)/$', views.apply_model,     name='apply_model'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/save/$',        views.save_model,               name='save_model'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/download/$',    views.download_reduced_data,    name='download_data'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/reverse/$',     views.reverse_model,            name='reverse_model'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/constraints/$', views.ConstraintView.as_view(), name='constraints'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/simultaneous/$', views.SimultaneousView.as_view(), name='simultaneous'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/simultaneous/update/$', views.update_simultaneous_params, name='simultaneous_update'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/constraints/(?P<const_id>\d+)/$', views.ConstraintView.as_view(), name='constraints_edit'),
    url(r'^(?P<instrument>[\w]+)/(?P<data_id>\d+)/constraints/(?P<const_id>\d+)/remove/$', views.remove_constraint, name='constraints_remove'),
]
