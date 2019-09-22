#pylint: disable=invalid-name
"""
    Define url structure
"""
from django.urls import include, path
from . import views

app_name = 'users'
urlpatterns = [
    path('login/', views.perform_login, name='perform_login'),
    path('logout/', views.perform_logout, name='perform_logout'),
]
