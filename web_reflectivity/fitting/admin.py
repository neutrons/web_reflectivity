#pylint: disable=missing-docstring
"""
    Admin views for models
"""
from django.contrib import admin
from fitting.models import ReflectivityModel, FitProblem, ReflectivityLayer, FitterOptions, Constraint, CatalogCache
from fitting.models import SavedModelInfo, UserData, SimultaneousModel, SimultaneousConstraint, SimultaneousFit

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

class SimultaneousFitAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'fit_problem', 'remote_job', 'timestamp')

class CatalogCacheAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_path', 'title', 'proposal', 'timestamp')

admin.site.register(ReflectivityModel, ReflectivityModelAdmin)
admin.site.register(FitProblem, FitProblemAdmin)
admin.site.register(ReflectivityLayer, ReflectivityLayerAdmin)
admin.site.register(Constraint, ConstraintAdmin)
admin.site.register(FitterOptions, FitterOptionsAdmin)
admin.site.register(SavedModelInfo, SavedModelInfoAdmin)
admin.site.register(UserData, UserDataAdmin)
admin.site.register(SimultaneousModel, SimultaneousModelAdmin)
admin.site.register(SimultaneousConstraint, SimultaneousConstraintAdmin)
admin.site.register(SimultaneousFit, SimultaneousFitAdmin)
admin.site.register(CatalogCache, CatalogCacheAdmin)
