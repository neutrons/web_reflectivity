from django.contrib import admin
from .models import DataRun, Instrument, PlotData

class PlotDataAdmin(admin.ModelAdmin):
    readonly_fields=('data_run',)
    list_display = ('id', 'data_run', 'timestamp')

class DataRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'run_number', 'run_id', 'instrument', 'created_on')

admin.site.register(DataRun, DataRunAdmin)
admin.site.register(Instrument)
admin.site.register(PlotData, PlotDataAdmin)