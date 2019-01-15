"""
    web_reflectivity URL Configuration
"""
from django.urls import include, path
from django.contrib import admin
from django.views.generic.base import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/fit/')),
    path('fit/', include('fitting.urls')),
    path('tools/', include('tools.urls')),
    path('users/', include('users.urls')),
]
