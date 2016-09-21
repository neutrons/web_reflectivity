"""
    Data models
"""
from __future__ import unicode_literals
from django.db import models


class Instrument(models.Model):
    """
        Table of instruments
    """
    name = models.CharField(max_length=128, unique=True)
    run_id_type = models.IntegerField(default=0)

    def __unicode__(self):
        return self.name


class DataRun(models.Model):
    """
        Table of runs
    """
    run_number = models.IntegerField()
    # Optional free-form run identifier
    run_id = models.TextField()
    experiment = models.TextField()
    # Location can either be a url or a file path
    location = models.TextField()

    instrument = models.ForeignKey(Instrument)
    created_on = models.DateTimeField('Timestamp', auto_now_add=True)

    def __unicode__(self):
        return "%s_%d_%s" % (self.instrument, self.run_number, self.run_id)


class PlotData(models.Model):
    """
        Table of plot data.
    """
    ## DataRun this run status belongs to
    data_run = models.ForeignKey(DataRun)
    ## json data
    data = models.TextField()
    timestamp = models.DateTimeField('Timestamp')

    def __unicode__(self):
        return "%s" % self.data_run


class ModelParameters(models.Model):
    """
        Table of model parameters
    """
    ## DataRun this run status belongs to
    data_run = models.ForeignKey(DataRun)
    ## Model parameters (json)
    parameters = models.TextField()
    timestamp = models.DateTimeField('Timestamp')

    def __unicode__(self):
        return "%s" % self.data_run
