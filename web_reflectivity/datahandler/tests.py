from django.test import TestCase

from .models import DataRun, PlotData, Instrument

class DataHandlerTestCase(TestCase):

    def test_create_data(self):
        """ Test the creation of a local data set """
        instrument = Instrument(name='test')
        instrument.save()
        self.assertEqual(str(instrument), 'test')

        run = DataRun(run_number=1, run_id='first_run', instrument=instrument)
        run.save()
        self.assertEqual(str(run), 'test_1_first_run')

        plot = PlotData(data_run=run, data='...', timestamp=run.created_on)
        plot.save()
        self.assertEqual(str(plot), 'test_1_first_run')



