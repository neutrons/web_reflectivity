#pylint: disable=invalid-name, line-too-long
"""
    Define url structure
"""
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^capacity/$', views.ChargeRateView.as_view(), name='capacity'),
]
