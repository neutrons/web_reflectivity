from django.contrib import admin
from fitting.models import ReflectivityModel, FitProblem, ReflectivityLayer

class FitProblemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'reflectivity_model', 'show_layers', 'remote_job', 'timestamp')
    list_filter = ('user', 'reflectivity_model__data_path')

    def show_layers(self, model):
        front_name = model.reflectivity_model.front_name
        back_name = model.reflectivity_model.back_name
        layers = [str(i) for i in model.layers.all().order_by('layer_number')]
        if len(layers) > 0:
            layers_str = ', '.join(layers)+', '
        else:
            layers_str = ''
        return u"%s, %s%s" % (front_name, layers_str, back_name)
    show_layers.short_description = "Layers"

class ReflectivityModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_path', 'scale', 'front_name', 'back_name')
    list_filter = ('data_path',)

class ReflectivityLayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'thickness', 'sld', 'roughness', 'layer_number')
    list_filter = ('name',)

admin.site.register(ReflectivityModel, ReflectivityModelAdmin)
admin.site.register(FitProblem, FitProblemAdmin)
admin.site.register(ReflectivityLayer, ReflectivityLayerAdmin)
