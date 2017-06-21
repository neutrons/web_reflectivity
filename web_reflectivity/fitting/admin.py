#pylint: disable=missing-docstring
"""
    Admin views for models
"""
from django.contrib import admin
from fitting.models import ReflectivityModel, FitProblem, ReflectivityLayer, FitterOptions, Constraint, SavedModelInfo, UserData, SimultaneousModel, SimultaneousConstraint

class FitProblemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'reflectivity_model', 'show_layers', 'remote_job', 'timestamp')
    list_filter = ('user', 'reflectivity_model__data_path')

class ReflectivityModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_path', 'scale', 'front_name', 'back_name')
    list_filter = ('data_path',)

class ReflectivityLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'thickness', 'sld', 'roughness', 'layer_number')
    list_filter = ('name',)

class FitterOptionsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'steps', 'burn')
    list_filter = ('user',)

class ConstraintAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'fit_problem', 'layer', 'parameter', 'variables')
    list_filter = ('user', 'fit_problem')

class SavedModelInfoAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'fit_problem', 'title')
    list_filter = ('user',)

class UserDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'file_id', 'file_name', 'tags', 'timestamp')
    list_filter = ('user',)

class SimultaneousModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'fit_problem', 'dependent_data', 'active')

class SimultaneousConstraintAdmin(admin.ModelAdmin):
    list_display = ('id', 'fit_problem', 'dependent_id', 'dependent_parameter',
                    'variable_id', 'variable_parameter')

admin.site.register(ReflectivityModel, ReflectivityModelAdmin)
admin.site.register(FitProblem, FitProblemAdmin)
admin.site.register(ReflectivityLayer, ReflectivityLayerAdmin)
admin.site.register(Constraint, ConstraintAdmin)
admin.site.register(FitterOptions, FitterOptionsAdmin)
admin.site.register(SavedModelInfo, SavedModelInfoAdmin)
admin.site.register(UserData, UserDataAdmin)
admin.site.register(SimultaneousModel, SimultaneousModelAdmin)
admin.site.register(SimultaneousConstraint, SimultaneousConstraintAdmin)
