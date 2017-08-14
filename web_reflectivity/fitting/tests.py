"""
    Test cases for the fitting app
"""
import json
import tempfile
import requests
from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User

from .models import FitterOptions, UserData, FitProblem, SavedModelInfo
from .data_server import data_handler as dh


class UserTestCase(TestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        self.user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        self.user.save()

    def test_login(self):
        """ Test logging in """
        # A simple get will return the login form
        response = self.client.get('/users/login')
        self.assertEqual(response.status_code, 200)

        # A successful login will result in a 302 since we will be redirected to landing page
        with self.settings(JOB_HANDLING_HOST='localhost'):
            response = self.client.post('/users/login', {'username': 'john', 'password': 'johnpassword'})
            self.assertEqual(response.status_code, 302)

        # Requesting the login page once logged in should result in a redirect to the requested page
        # This exercises the processing of 'next'
        response = self.client.get('/users/login?next=/fit/files/')
        self.assertEqual(response.status_code, 302)

    def test_logout(self):
        """ Test logging out """
        self.client.login(username='john', password='johnpassword')
        response = self.client.get('/users/logout')
        # A successful logout will result in a 302 since we will be redirected to landing page
        self.assertEqual(response.status_code, 302)


class TestDataHandling(TestCase):
    def test_key(self):
        """ Test the generation of secret key for a data set """
        with self.settings(LIVE_PLOT_SECRET_KEY='1234'):
            url_with_key = dh.append_key('/', 'refl', 1)
            self.assertEqual(url_with_key, '/?key=3b9a06c28c5b1c0ae87c2bd05ea8603b9b9c0c31')

    def test_remote_server(self):
        """ Test the remote data hanbdling. Since we don't have a data server
            this call will fail """
        class Dummy(object):
            user = 'john'
        with self.settings(LIVE_DATA_SERVER_DOMAIN='localhost'):
            try:
                dh._remote_store(request=Dummy(), file_name='test_file.txt', plot='...')
            except requests.ConnectionError:
                pass
    def test_remote_fetch(self):
        """ Test remote fetch, which should result in None since we are not connected to a remote server """
        with self.settings(LIVE_DATA_SERVER_DOMAIN='localhost'):
            json_data = dh._remote_fetch('john', '1', data_type='html')
            self.assertEqual(json_data, None)

    def test_remote_user_files(self):
        """ Test call to update local file list from remote server. This should not crash, but also do
            nothing since we are not connected to a remote data server """
        class Dummy(object):
            user = 'john'
        with self.settings(LIVE_DATA_SERVER_DOMAIN='localhost'):
            dh.get_user_files_from_server(Dummy())


class FileTestCase(TestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        self.user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        self.user.save()
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

    def test_file_meta_data(self):
        """ Test the view used to change info about an uploaded file """
        # Upload data
        with open('test_data.txt') as fp:
            self.client.post('/fit/files/', {'name': 'test_data.txt', 'file': fp})

        # Verify that the meta data object was created
        response = self.client.get('/fit/john/1/info/')
        self.assertEqual(response.status_code, 200)

        # Modify the meta data
        self.client.post('/fit/john/1/info/', {'user':1, 'file_id':1, 'file_name': 'test_data.txt', 'tags': 'bunch of tags'})
        user_data = UserData.objects.get(user=self.user, file_id=1)
        self.assertEqual(user_data.tags, "bunch of tags")

class FitSubmitTestCase(TestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        self.user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        self.user.save()
        self.client.login(username='john', password='johnpassword')
        # Upload data
        with open('test_data.txt') as fp:
            self.client.post('/fit/files/', {'name': 'test_data.txt', 'file': fp})

    def test_delete_file(self):
        self.assertEqual(len(UserData.objects.all()), 1)
        self.client.post('/fit/files/1/delete/')
        self.assertEqual(len(UserData.objects.all()), 0)

    def test_download_data(self):
        response = self.client.get('/fit/john/1/download/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith("# JOHN Run 1"))

    def test_fit_page(self):
        response = self.client.get('/fit/john/1/')
        self.assertEqual(response.status_code, 200)

        form_data = {u'form-0-roughness_is_fixed': [u'on'], u'front_name': [u'air'], u'back_name': [u'Si'],
                     u'back_roughness_is_fixed': [u'on'], u'scale_max': [u'1.1'], u'data_path': [u'john/1'],
                     u'background_is_fixed': [u'on'], u'front_sld_max': [u'1'], u'form-0-thickness_max': [u'100.0'],
                     u'form-0-id': [u''], u'button_choice': [u'skip'], u'back_sld_min': [u'2.0'], u'scale': [u'1'],
                     u'background_min': [u'0'], u'back_sld_max': [u'2.1'], u'front_sld_min': [u'0'],
                     u'form-0-layer_number': [u'1000'], u'form-MIN_NUM_FORMS': [u'0'], u'background_max': [u'1e-06'],
                     u'back_sld': [u'2.07'], u'form-0-name': [u'material'], u'form-0-sld': [u'2.0'], u'back_roughness_min': [u'1'],
                     u'scale_is_fixed': [u'on'], u'form-TOTAL_FORMS': [u'1'], u'back_sld_is_fixed': [u'on'], u'q_max': [u'1'],
                     u'form-0-thickness_is_fixed': [u'on'], u'background': [u'0'], u'form-INITIAL_FORMS': [u'0'],
                     u'form-0-roughness': [u'1.0'], u'front_sld_is_fixed': [u'on'], u'scale_min': [u'0.9'],
                     u'back_roughness_max': [u'5'], u'form-0-sld_min': [u'1.0'], u'form-MAX_NUM_FORMS': [u'1000'],
                     u'front_sld': [u'0'], u'form-0-sld_is_fixed': [u'on'], u'form-0-thickness_min': [u'10.0'],
                     u'form-0-sld_max': [u'4.0'], u'back_roughness': [u'5.0'], u'form-0-roughness_max': [u'10.0'],
                     u'form-0-roughness_min': [u'1.0'], u'form-0-thickness': [u'50.0'], u'q_min': [u'0']}

        # Submit a model, without fitting or evaluating
        response = self.client.post('/fit/john/1/', form_data)
        # We get a 302 because of a redirect
        self.assertEqual(response.status_code, 302)


class FitProblemViewsTestCase(TestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        self.user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        self.user.save()
        self.client.login(username='john', password='johnpassword')
        # Upload data
        with open('test_data.txt') as fp:
            self.client.post('/fit/files/', {'name': 'test_data.txt', 'file': fp})
        # Create a fit model
        form_data = {u'form-0-roughness_is_fixed': [u'on'], u'front_name': [u'air'], u'back_name': [u'Si'],
                     u'back_roughness_is_fixed': [u'on'], u'scale_max': [u'1.1'], u'data_path': [u'john/1'],
                     u'background_is_fixed': [u'on'], u'front_sld_max': [u'1'], u'form-0-thickness_max': [u'100.0'],
                     u'form-0-id': [u''], u'button_choice': [u'skip'], u'back_sld_min': [u'2.0'], u'scale': [u'1'],
                     u'background_min': [u'0'], u'back_sld_max': [u'2.1'], u'front_sld_min': [u'0'],
                     u'form-0-layer_number': [u'1000'], u'form-MIN_NUM_FORMS': [u'0'], u'background_max': [u'1e-06'],
                     u'back_sld': [u'2.07'], u'form-0-name': [u'material'], u'form-0-sld': [u'2.0'], u'back_roughness_min': [u'1'],
                     u'scale_is_fixed': [u'on'], u'form-TOTAL_FORMS': [u'1'], u'back_sld_is_fixed': [u'on'], u'q_max': [u'1'],
                     u'form-0-thickness_is_fixed': [u'on'], u'background': [u'0'], u'form-INITIAL_FORMS': [u'0'],
                     u'form-0-roughness': [u'1.0'], u'front_sld_is_fixed': [u'on'], u'scale_min': [u'0.9'],
                     u'back_roughness_max': [u'5'], u'form-0-sld_min': [u'1.0'], u'form-MAX_NUM_FORMS': [u'1000'],
                     u'front_sld': [u'0'], u'form-0-sld_is_fixed': [u'on'], u'form-0-thickness_min': [u'10.0'],
                     u'form-0-sld_max': [u'4.0'], u'back_roughness': [u'5.0'], u'form-0-roughness_max': [u'10.0'],
                     u'form-0-roughness_min': [u'1.0'], u'form-0-thickness': [u'50.0'], u'q_min': [u'0']}

        # Submit a model, without fitting or evaluating
        self.client.post('/fit/john/1/', form_data)

    def test_save_model(self):
        # At this point the model should be available in the database
        response = self.client.get('/fit/john/1/save/')
        self.assertEqual(response.status_code, 200)

        # Retrieve the saved model ID
        fit_problem = FitProblem.objects.get(user=self.user,
                                             reflectivity_model__data_path='saved')
        model_info = SavedModelInfo.objects.get(user=self.user, fit_problem=fit_problem)

        # Apply to our data
        response = self.client.get('/fit/john/1/apply/%s/' % model_info.id)
        self.assertEqual(response.status_code, 302)

        # Delete the model
        fit_problem_list = SavedModelInfo.objects.filter(user=self.user,
                                                         fit_problem=fit_problem)
        self.assertEqual(len(fit_problem_list), 1)

        response = self.client.get('/fit/model/%s/delete/' % model_info.id)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Are you sure you want')

        response = self.client.post('/fit/model/%s/delete/' % model_info.id, follow=True)

        fit_problem_list = SavedModelInfo.objects.filter(user=self.user,
                                                         fit_problem=fit_problem)
        self.assertEqual(len(fit_problem_list), 0)

    def test_download_model(self):
        # Get the model as text
        response = self.client.get('/fit/john/1/model/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith("# Reflectivity model"))

    def test_reverse_model(self):
        fit_problem = FitProblem.objects.get(user=self.user,
                                             reflectivity_model__data_path='john/1')
        self.assertEqual(fit_problem.reflectivity_model.back_sld, 2.07)

        response = self.client.get('/fit/john/1/reverse/')
        # The status code is a 302 because of a redirect
        self.assertEqual(response.status_code, 302)

        fit_problem = FitProblem.objects.get(user=self.user,
                                             reflectivity_model__data_path='john/1')
        self.assertEqual(fit_problem.reflectivity_model.back_sld, 0)

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
        option_obj = FitterOptions.objects.get(user=self.user)
        self.assertEqual(option_obj.steps, 500)

