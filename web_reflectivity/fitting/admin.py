"""
    Admin views for models
"""
from django.contrib import admin
from fitting.models import ReflectivityModel, FitProblem, ReflectivityLayer

class FitProblemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'reflectivity_model', 'show_layers', 'remote_job', 'timestamp')
    list_filter = ('user', 'reflectivity_model__data_path')

class ReflectivityModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_path', 'scale', 'front_name', 'back_name')
    list_filter = ('data_path',)

class ReflectivityLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'thickness', 'sld', 'roughness', 'layer_number')
    list_filter = ('name',)

admin.site.register(ReflectivityModel, ReflectivityModelAdmin)
admin.site.register(FitProblem, FitProblemAdmin)
admin.site.register(ReflectivityLayer, ReflectivityLayerAdmin)
