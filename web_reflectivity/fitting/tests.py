import json
import tempfile
from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User

from .models import FitterOptions

class FileViewTestCase(TestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        user.save()
        self.client.login(username='john', password='johnpassword')

    def test_file_list(self):
        """ Write data in the local store """
        response = self.client.get('/fit/files/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['file_list'], '[]')

        # Upload data
        with open('test_data.txt') as fp:
            self.client.post('/fit/files/', {'name': 'test_data.txt', 'file': fp})

        # Verify that the data is there
        response = self.client.get('/fit/files/')
        self.assertEqual(response.status_code, 200)
        json_data = response.context['file_list']
        data_list = json.loads(json_data)
        self.assertEqual(len(data_list), 1)

        # Error message list should be empty
        self.assertEqual(response.context['user_alert'], [])

    def test_bad_file(self):
        """ Test the upload of a badly formatted file """
        # Create a temporary file
        fp = tempfile.TemporaryFile()
        fp.write(b'bad data')
        fp.seek(0)

        # Upload the file. The request should complete but an error message should be returned
        response = self.client.post('/fit/files/', {'name': 'bad_data.txt', 'file': fp})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['user_alert']), 1)
        self.assertTrue(u'Could not parse data file' in response.context['user_alert'][0], "Missing error message")

class FitterOptionsTestCase(TestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        self.user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        self.user.save()
        self.client.login(username='john', password='johnpassword')

    def test_current_options(self):
        """ Test options """
        # Exercise the request to get current options
        response = self.client.get('/fit/options/')
        self.assertEqual(response.status_code, 200)

        # Verify that we can change option
        option_obj = FitterOptions.objects.get(user=self.user)
        self.assertEqual(option_obj.steps, 1000)
        self.client.post('/fit/options/', {'steps': 500, 'burn':500, 'engine': 'dream' })
        self.assertEqual(option_obj.steps, 500)
