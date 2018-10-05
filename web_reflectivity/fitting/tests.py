"""
    Test cases for the fitting application
"""
import json
import tempfile
from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User
from django.forms import model_to_dict

from .models import FitterOptions, UserData, FitProblem, SavedModelInfo, SimultaneousModel, Constraint, SimultaneousConstraint
from .data_server import data_handler as dh
from . import view_util
from . import forms
from . import job_handling
from .parsing import refl1d, refl1d_err_model, refl1d_simultaneous
from .simultaneous import model_handling

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

class FileTestCase(TestCase):
    """ File handling tests """
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
    """ Test submission of a model and file handling """
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
        """ Delete a user data file """
        self.assertEqual(len(UserData.objects.all()), 1)
        self.client.post('/fit/files/1/delete/')
        self.assertEqual(len(UserData.objects.all()), 0)

    def test_download_data(self):
        """ Download data """
        response = self.client.get('/fit/john/1/download/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith("# JOHN Run 1"))

    def test_fit_page(self):
        """ Vuew fit page and submit a model """
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
                     u'form-0-roughness_min': [u'1.0'], u'form-0-thickness': [u'50.0'], u'q_min': [u'0'],
                     u'form-0-i_sld_min': [u'0.0'], u'form-0-i_sld_max': [u'2.0'], u'form-0-i_sld': [u'1.0'],
                     u'form-0-i_sld_is_fixed': [u'on']}

        # Submit a model, without fitting or evaluating
        response = self.client.post('/fit/john/1/', form_data)
        # We get a 302 because of a redirect
        self.assertEqual(response.status_code, 302)

class SimultaneousViewsTestCase(TestCase):
    """ Test simultaneous fitting """
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
                     u'form-0-roughness_min': [u'1.0'], u'form-0-thickness': [u'50.0'], u'q_min': [u'0'],
                     u'form-0-i_sld_min': [u'0.0'], u'form-0-i_sld_max': [u'2.0'], u'form-0-i_sld': [u'1.0'],
                     u'form-0-i_sld_is_fixed': [u'on']}

        # Submit a model, without fitting or evaluating
        self.client.post('/fit/john/1/', form_data)

        # Second data set
        with open('test_data.txt') as fp:
                fp2 = tempfile.TemporaryFile()
                fp2.write(fp.read())
                fp2.seek(0)
                self.client.post('/fit/files/', {'name': 'test_data_2.txt', 'file': fp2})
        # Verify that the file was written
        UserData.objects.get(user=self.user, file_id=2)

        fit_problem = FitProblem.objects.get(user=self.user)
        new_problem = view_util.copy_fit_problem(fit_problem, self.user)
        data_path = 'john/2'
        new_problem.reflectivity_model.data_path = data_path
        new_problem.save()

    def test_script(self):
        """ Test that we can generate a simultaneous fitting script """
        data_script = job_handling.assemble_data_setup([['john/1', ['0.01, 1., 0.1']], ['john/2', ['0.01, 1., 0.1']]])
        script = job_handling.assemble_job('# test', data_script, ['exp1', 'exp2'], ['john/1','john/2'], {}, '/tmp', '/tmp')
        self.assertTrue("problem = FitProblem([exp1,exp2])" in script)

    def test_asymmetry(self):
        """ Test asymmetry code """
        d1 = [[0.1, 0.2], [0.5, 0.5], [0.1, 0.1]]
        d2 = [[0.1, 0.2], [1.5, 1.5], [0.1, 0.1]]
        result = model_handling.compute_asymmetry(d1, d2)
        self.assertEqual(result[1][0], -2)

    def test_simultaneous_view(self):
        """ Test simultaneous view """
        response = self.client.get('/fit/john/1/simultaneous/')
        self.assertEqual(response.status_code, 200)
        # Add a simultaneous fit constraint
        response = self.client.post('/fit/john/1/simultaneous/update/', {u'id_sld_1': [u'id_sld_2']})
        self.assertEqual(response.status_code, 200)
        items = SimultaneousConstraint.objects.all()
        self.assertEqual(len(items), 1)
        script = items[0].get_constraint(sample_name='sample')
        self.assertEqual(script, "sample1['material'].material.rho = sample2['material'].material.rho")

class FitProblemViewsTestCase(TestCase):
    """ Test functionality related to fits """
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
                     u'form-0-roughness_min': [u'1.0'], u'form-0-thickness': [u'50.0'], u'q_min': [u'0'],
                     u'form-0-i_sld_min': [u'0.0'], u'form-0-i_sld_max': [u'2.0'], u'form-0-i_sld': [u'1.0'],
                     u'form-0-i_sld_is_fixed': [u'on']}

        # Submit a model, without fitting or evaluating
        self.client.post('/fit/john/1/', form_data)

    def test_view_fit(self):
        """ Fit view """
        response = self.client.get('/fit/john/1/')
        self.assertEqual(response.status_code, 200)

    def test_view_fit_list(self):
        response = self.client.get('/fit/list/')
        self.assertEqual(response.status_code, 200)

    def test_scripting(self):
        """ Generate a refl1d script """
        fit_problem = FitProblem.objects.get(user=self.user)
        data_dict = model_to_dict(fit_problem.reflectivity_model)
        layer_dict = model_to_dict(fit_problem.layers.all()[0])

        data_form = forms.ReflectivityFittingForm(data_dict, instance=fit_problem)
        self.assertTrue(data_form.is_valid())
        layers_form = forms.LayerForm(layer_dict)
        self.assertTrue(layers_form.is_valid())

        template = 'reflectivity_model.py.template'
        script = job_handling.create_model_file(data_form, [layers_form], template=template,
                                                data_file='/tmp/__data.txt', ascii_data='0.1 1.1 0.1 0.01',
                                                output_dir='/tmp/', fit=True, options={}, constraints=[])

        self.assertTrue("sample = (  Si(0, 5.0) | material(50.0, 1.0) | air )" in script)

    def test_process_single_fit(self):
        """ Process a fit request """
        fit_problem = FitProblem.objects.get(user=self.user)
        script, _, _, _ = view_util._process_fit_problem(fit_problem, 'john', '1', {}, '/tmp', '/tmp')
        self.assertTrue("sample1 = (  Si(0, 5.0) | material(50.0, 1.0) | air )" in script)

    def test_bad_constraint(self):
        """ Test constraint requests """
        response = self.client.get('/fit/john/1/constraints/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/fit/john/1/constraints/', {u'definition': [u'return 1'], u'layer': [u'1'],
                                                                 u'variables': [u'material_thickness'],
                                                                 u'button_choice': [u'submit'],
                                                                 u'parameter': [u'thickness']})
        self.assertTrue(response.context['user_alert'][0].startswith("Your constraint"))
        self.assertEqual(len(Constraint.objects.all()), 0)


    def test_good_constraint(self):
        """ Test constraint requests """
        response = self.client.get('/fit/john/1/constraints/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/fit/john/1/constraints/', {u'definition': [u'return material_thickness'], u'layer': [u'1'],
                                                                 u'variables': [u'material_thickness'],
                                                                 u'button_choice': [u'submit'],
                                                                 u'parameter': [u'thickness']})

        self.assertEqual(len(Constraint.objects.all()), 1)
        response = self.client.get('/fit/john/1/constraints/')
        self.assertEqual(response.status_code, 200)

        # Apply the constraint
        fit_problem = FitProblem.objects.get(user=self.user)
        constraint = Constraint.objects.get(fit_problem=fit_problem)
        constraint.apply_constraint(fit_problem)
        script = constraint.get_ranges()
        self.assertTrue("sample['material'].thickness = constraint_thickness(sample['material'].thickness)" in script)

        # Delete the constraint
        response = self.client.get('/fit/john/1/constraints/1/remove/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(Constraint.objects.all()), 0)

    def test_append(self):
        """ Append a data set to a view so we can do simultaneous fitting """
        with open('test_data.txt') as fp:
                fp2 = tempfile.TemporaryFile()
                fp2.write(fp.read())
                fp2.seek(0)
                self.client.post('/fit/files/', {'name': 'test_data_2.txt', 'file': fp2})
        # Verify that the file was written
        UserData.objects.get(user=self.user, file_id=2)

        fit_problem = FitProblem.objects.get(user=self.user)
        new_problem = view_util.copy_fit_problem(fit_problem, self.user)
        data_path = 'john/2'
        new_problem.reflectivity_model.data_path = data_path
        new_problem.save()

        fit_problem_list = FitProblem.objects.filter(user=self.user)
        self.assertEqual(len(fit_problem_list), 2)

        response = self.client.post('/fit/john/1/append/', {u'dependent_data': [data_path], u'simult_choice': [u'add data']}, follow=True)
        self.assertEqual(response.status_code, 200)
        # Verify that the SimultaneousModel object exists
        sim = SimultaneousModel.objects.get(dependent_data='john/2')
        response = self.client.post('/fit/simultaneous/%s/delete/' % sim.id, success='/fit/john/1/')
        sim_list = SimultaneousModel.objects.all()
        self.assertEqual(len(sim_list), 0)

    def test_save_model(self):
        """ Save a model """
        # At this point the model should be available in the database
        response = self.client.get('/fit/john/1/save/')
        self.assertEqual(response.status_code, 200)

        # Retrieve the saved model ID
        fit_problem = FitProblem.objects.get(user=self.user,
                                             reflectivity_model__data_path='saved')
        model_info = SavedModelInfo.objects.get(user=self.user, fit_problem=fit_problem)

        # List models
        response = self.client.get('/fit/models/')
        self.assertEqual(response.status_code, 200)

        # Update model info
        response = self.client.post('/fit/model/%s/' % model_info.id, {u'notes': [u'ff'], u'title': [u'test']}, follow=True)
        self.assertEqual(response.status_code, 200)

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
        """ Get model as text """
        response = self.client.get('/fit/john/1/model/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith("# Reflectivity model"))

    def test_delete_fit_problem(self):
        """ Delete a fit problem """
        fit_problem = FitProblem.objects.get(user=self.user,
                                             reflectivity_model__data_path='john/1')
        self.client.post('/fit/problem/%s/delete/' % fit_problem.id)
        fit_problem_list = FitProblem.objects.filter(user=self.user)
        self.assertEqual(len(fit_problem_list), 0)

    def test_reverse_model(self):
        """ Test layer order reversal """
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
    """ Test fitter options """
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

class ParsingTestCase(TestCase):
    """ Test refl1d result parsers """
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
                     u'form-0-roughness_min': [u'1.0'], u'form-0-thickness': [u'50.0'], u'q_min': [u'0'],
                     u'form-0-i_sld_min': [u'0.0'], u'form-0-i_sld_max': [u'2.0'], u'form-0-i_sld': [u'1.0'],
                     u'form-0-i_sld_is_fixed': [u'on']}

        # Submit a model, without fitting or evaluating
        self.client.post('/fit/john/1/', form_data)
        self.log = """REFL_START
# intensity: 1.00030009
# background: 0
#           Q (1/A)             dQ (1/A)                    R                   dR               theory              fresnel
           0.0102867 0.000279645531914894               1.0504             0.092293    0.672359425194163    0.594669882371317
           0.0103895           0.00028074              1.02078            0.0891921    0.575304923739536    0.463527378297117
           0.0104934 0.000281845106382979              0.96715             0.083779    0.483326478154947    0.384295074421221
           0.0105984 0.000282961276595745             0.968514            0.0823192    0.403253968461261    0.328342479333087
           0.0107044 0.000284088936170213             0.970881            0.0800768    0.338097436951066    0.285870884527548
           0.0108114 0.000285227659574468             0.966073             0.078124    0.287281884866939    0.252187825023649
           0.0109195 0.000286377872340426             0.958078            0.0750923    0.248218604645389    0.224650862907597
           0.0110287 0.000287539574468085             0.988613            0.0743383    0.217913575946419    0.201654706393432
            0.011139 0.000288712765957447               1.0373            0.0733602    0.193813155832526    0.182136509371316
           0.0112504 0.000289897872340426               1.0549            0.0722738    0.174081580491961    0.165356290813667
           0.0113629 0.000291094468085106              1.08183            0.0708015    0.157509690044471    0.150778618670228
           0.0114765 0.000292303404255319              1.02828            0.0674534    0.143294977412524    0.138004058076455
           0.0115913 0.000293524255319149             0.949667            0.0624834    0.130972784201475    0.126717934709103
           0.0117072 0.000294757446808511             0.972319            0.0620833     0.12015965132879    0.116693156594169
           0.0118243 0.000296002978723404              1.00425            0.0616489    0.110577305479999    0.107732605415522
           0.0119425  0.00029726085106383             0.990207            0.0598001    0.102042376516003   0.0996919778441593
           0.0120619 0.000298531063829787              1.00483            0.0497519    0.094391975323907   0.0924402136226794
           0.0121826 0.000299814468085106             0.972616            0.0773795   0.0874968890938523   0.0858704553000646
           0.0123044 0.000301110212765957             0.886992            0.0721816   0.0812673974202752   0.0799085687045494
           0.0124274 0.000302419574468085             0.934188            0.0717378   0.0756139294509646   0.0744772274874641
           0.0125517 0.000303741276595745             0.993151            0.0712753    0.070462699687341   0.0695118367314475
           0.0126772 0.000305076595744681             0.976735            0.0688063   0.0657594719690125   0.0649649039276407
            0.012804 0.000306425531914894             0.957027            0.0658492   0.0614507257404519   0.0607884205820601
            0.012932 0.000307787659574468             0.919041            0.0629992   0.0574971907072747   0.0569472486004717
           0.0130613 0.000309163404255319             0.875214            0.0596586   0.0538589100500488   0.0534048934490426
            0.013192 0.000310552765957447             0.824697            0.0566901   0.0505017826360823   0.0501300086660019
           0.0133239 0.000311956170212766             0.768672            0.0533049   0.0474032755072363    0.047102114506158
           0.0134571 0.000313373617021277             0.674587            0.0486649   0.0445364084140841   0.0442960915327297
           0.0135917 0.000314805106382979             0.574285            0.0433027    0.041877870349777   0.0416901316847105
REFL_END
MODEL_PARAMS_START
.probe
  .back_absorption = Parameter(1, name='back_absorption')
  .background = Parameter(0, name='background')
  .intensity = Parameter(1.0003, name='intensity', bounds=(0.9993,1.0013))
  .theta_offset = theta_offset
.sample
  .layers
    [0]
      .interface = Parameter(5, name='Si interface')
      .material
        .irho = Parameter(0, name='Si irho')
        .rho = Parameter(2.07, name='Si rho')
      .thickness = Parameter(0, name='Si thickness')
    [1]
      .interface = Parameter(1, name='material interface')
      .material
        .irho = Parameter(0, name='material irho')
        .rho = Parameter(2, name='material rho')
      .thickness = Parameter(50, name='material thickness')
    [2]
      .interface = Parameter(0, name='air interface')
      .material
        .irho = Parameter(0, name='air irho')
        .rho = Parameter(0, name='air rho')
      .thickness = Parameter(0, name='air thickness')
  .thickness = stack thickness:50

[chisq=108.1844(30), nllf=18012.7]
        Parameter       mean  median    best [   68% interval] [   95% interval]
 1            intensity  1.084(31)  1.0991  1.1000 [  1.062   1.100] [  1.000   1.100]
 2            background  1.084(31)  1.0991  1.1000 [  1.062   1.100] [  1.000   1.100]
 3         material rho 3.99975(26) 3.999830 3.999999 [3.99953 3.99995] [3.99903 3.99999]
 4   material thickness  88.79(35)  88.794  88.793 [  88.45   89.14] [  88.10   89.47]
 5   material interface  88.79(35)  88.794  88.793 [  88.45   89.14] [  88.10   89.47]
 6   Si interface  88.79(35)  88.794  88.793 [  88.45   89.14] [  88.10   89.47]

MODEL_PARAMS_END
MODEL_BEST_VALUES_START
intensity 1.00030009

MODEL_BEST_VALUES_END
SLD_START
  1.80000000   2.02515965   0.00000000
  2.80000000   2.02014178   0.00000000
  3.80000000   2.01565391   0.00000000
  4.80000000   2.01179693   0.00000000
  5.80000000   2.00861171   0.00000000
  6.80000000   2.00608405   0.00000000
  7.80000000   2.00415660   0.00000000
  8.80000000   2.00274427   0.00000000
  9.80000000   2.00174985   0.00000000
SLD_END
Done: 2.40629 sec
"""
    def test_update_model(self):
        """ Update model from log """
        fit_problem = FitProblem.objects.get(user=self.user)
        chi2 = refl1d.update_model(self.log, fit_problem)
        self.assertEqual(chi2, 108.1844)

    def test_update_from_slabs(self):
        """ Update model from encoded slab model in the log """
        data, _ = refl1d_err_model.parse_slabs(self.log)
        self.assertEqual(data[0][0]['chi2'], '108.1844')

class SimultaneousParsingTestCase(TestCase):
    """ Test refl1d result parsers for simultaneous fits"""
    def setUp(self):
        self.log = """SIMULTANEOUS ["ref_l/154461","ref_l/154461","ref_l/157294"]
MODEL_PARAMS_START
-- Model 0 None
.probe
  .back_absorption = Parameter(1, name='back_absorption')
  .background = Parameter(1.03506e-06, name='background', bounds=(0,1e-05))
  .intensity = Parameter(0.900023, name='intensity', bounds=(0.9,1.1))
  .theta_offset = theta_offset
.sample
  .layers
    [0]
      .interface = Parameter(27.4311, name='electrolyte interface', bounds=(1,65))
      .material
        .irho = Parameter(0, name='electrolyte irho')
        .rho = Parameter(1.42365, name='electrolyte rho', bounds=(0,2))
      .thickness = Parameter(0, name='electrolyte thickness')
    [1]
      .interface = Parameter(21.6022, name='silicate interface', bounds=(1,55))
      .material
        .irho = Parameter(0, name='silicate irho')
        .rho = Parameter(2.56156, name='silicate rho', bounds=(1,4))
      .thickness = Parameter(373.1, name='silicate thickness', bounds=(250,1000))
    [2]
      .interface = Parameter(23.7308, name='aSi interface', bounds=(1,35))
      .material
        .irho = Parameter(0, name='aSi irho')
        .rho = Parameter(2.09996, name='aSi rho', bounds=(1.8,2.1))
      .thickness = Parameter(496.203, name='aSi thickness', bounds=(400,1000))
    [3]
      .interface = Parameter(4.99994, name='Cu interface', bounds=(1,5))
      .material
        .irho = Parameter(0, name='Cu irho')
        .rho = Parameter(6.40677, name='Cu rho', bounds=(6.4,6.8))
      .thickness = Parameter(246.306, name='Cu thickness', bounds=(150,250))
    [4]
      .interface = Parameter(4.07152, name='SiOx interface', bounds=(1,5))
      .material
        .irho = Parameter(0, name='SiOx irho')
        .rho = Parameter(1.97449, name='SiOx rho', bounds=(1,4))
      .thickness = Parameter(18.4523, name='SiOx thickness', bounds=(10,30))
    [5]
      .interface = Parameter(0, name='Si interface')
      .material
        .irho = Parameter(0, name='Si irho')
        .rho = Parameter(2.07, name='Si rho')
      .thickness = Parameter(0, name='Si thickness')
  .thickness = stack thickness:1134.06

[chisq=15.89(11), nllf=1271.09]
-- Model 1 None
.probe
  .back_absorption = Parameter(1, name='back_absorption')
  .background = Parameter(1.03506e-06, name='background', bounds=(0,1e-05))
  .intensity = Parameter(0.900023, name='intensity', bounds=(0.9,1.1))
  .theta_offset = theta_offset
.sample
  .layers
    [0]
      .interface = Parameter(27.4311, name='electrolyte interface', bounds=(1,65))
      .material
        .irho = Parameter(0, name='electrolyte irho')
        .rho = Parameter(1.42365, name='electrolyte rho', bounds=(0,2))
      .thickness = Parameter(0, name='electrolyte thickness')
    [1]
      .interface = Parameter(21.6022, name='silicate interface', bounds=(1,55))
      .material
        .irho = Parameter(0, name='silicate irho')
        .rho = Parameter(2.56156, name='silicate rho', bounds=(1,4))
      .thickness = Parameter(373.1, name='silicate thickness', bounds=(250,1000))
    [2]
      .interface = Parameter(23.7308, name='aSi interface', bounds=(1,35))
      .material
        .irho = Parameter(0, name='aSi irho')
        .rho = Parameter(2.09996, name='aSi rho', bounds=(1.8,2.1))
      .thickness = Parameter(496.203, name='aSi thickness', bounds=(400,1000))
    [3]
      .interface = Parameter(4.99994, name='Cu interface', bounds=(1,5))
      .material
        .irho = Parameter(0, name='Cu irho')
        .rho = Parameter(6.40677, name='Cu rho', bounds=(6.4,6.8))
      .thickness = Parameter(246.306, name='Cu thickness', bounds=(150,250))
    [4]
      .interface = Parameter(4.07152, name='SiOx interface', bounds=(1,5))
      .material
        .irho = Parameter(0, name='SiOx irho')
        .rho = Parameter(1.97449, name='SiOx rho', bounds=(1,4))
      .thickness = Parameter(18.4523, name='SiOx thickness', bounds=(10,30))
    [5]
      .interface = Parameter(0, name='Si interface')
      .material
        .irho = Parameter(0, name='Si irho')
        .rho = Parameter(2.07, name='Si rho')
      .thickness = Parameter(0, name='Si thickness')
  .thickness = stack thickness:1134.06

[chisq=15.89(11), nllf=1271.09]
-- Model 2 None
.probe
  .back_absorption = Parameter(1, name='back_absorption')
  .background = Parameter(9.73296e-07, name='background', bounds=(0,5e-06))
  .intensity = Parameter(1, name='normalization')
  .theta_offset = theta_offset
.sample
  .layers
    [0]
      .interface = Parameter(15.0266, name='PC interface', bounds=(1,25))
      .material
        .irho = Parameter(0, name='PC irho')
        .rho = Parameter(5.9018, name='PC rho')
      .thickness = Parameter(0, name='PC thickness')
    [1]
      .interface = Parameter(54.8788, name='oxy interface', bounds=(2,55))
      .material
        .irho = Parameter(0, name='oxy irho')
        .rho = Parameter(4.37687, name='oxy rho', bounds=(1.2,5))
      .thickness = Parameter(99.5173, name='oxy thickness', bounds=(10,300))
    [2]
      .interface = Parameter(18.0588, name='Ge interface', bounds=(1,35))
      .material
        .irho = Parameter(0, name='Ge irho')
        .rho = Parameter(3.4267, name='Ge rho', bounds=(3,3.55))
      .thickness = Parameter(257.185, name='Ge thickness', bounds=(250,450))
    [3]
      .interface = Parameter(1.108, name='Cu interface')
      .material
        .irho = Parameter(0, name='Cu irho')
        .rho = Parameter(6.6773, name='Cu rho')
      .thickness = Parameter(99.117, name='Cu thickness')
    [4]
      .interface = Parameter(1.379, name='SiOx interface')
      .material
        .irho = Parameter(0, name='SiOx irho')
        .rho = Parameter(2.651, name='SiOx rho')
      .thickness = Parameter(21.716, name='SiOx thickness')
    [5]
      .interface = Parameter(0, name='Si interface')
      .material
        .irho = Parameter(0, name='Si irho')
        .rho = Parameter(2.0649, name='Si rho')
      .thickness = Parameter(0, name='Si thickness')
  .thickness = stack thickness:477.536

[chisq=1.686(58), nllf=134.86]
[overall chisq=11.741(59), nllf=2677.04]

MODEL_PARAMS_END
MODEL_BEST_VALUES_START
background 1.03505540166325e-06
intensity 0.900022651589221
electrolyte interface 27.4310881356407
electrolyte rho 1.42365286811703
silicate interface 21.602217625566
silicate rho 2.56156491610497
silicate thickness 373.099532344799
aSi interface 23.7307599037164
aSi rho 2.09996200877021
aSi thickness 496.203014608982
Cu interface 4.99993566248069
Cu rho 6.40677324961631
Cu thickness 246.305564933279
SiOx interface 4.07151622062367
SiOx rho 1.97448945578209
SiOx thickness 18.4523106339436
background 9.73295637100827e-07
PC interface 15.0265655211584
oxy interface 54.8787742858312
oxy rho 4.37687209566682
oxy thickness 99.5172696142951
Ge interface 18.0587506467274
Ge rho 3.42669755016813
Ge thickness 257.185290226391

MODEL_BEST_VALUES_END
EXPT_START 0
REFL_START
# intensity: 0.900022651589221
# background: 1.03505540166325e-06
#           Q (1/A)             dQ (1/A)                    R                   dR               theory              fresnel
           0.0103014 0.000271035319148936             0.417362            0.0369575    0.728242647754449   0.0044453041591313
           0.0105075 0.000273051914893617             0.442497            0.0353783    0.712857543062051  0.00414688075083677
           0.0107176 0.000275108510638298             0.456046            0.0339778    0.694971134319048  0.00386743512655457
REFL_END
SLD_START
  0.50673559   2.00099446   0.00000000
  1.50673559   2.01753155   0.00000000
  2.50673559   2.03403557   0.00000000
SLD_END
EXPT_END 0
EXPT_START 1
REFL_START
# intensity: 0.900022651589221
# background: 1.03505540166325e-06
#           Q (1/A)             dQ (1/A)                    R                   dR               theory              fresnel
          0.00933032 0.000261530638297872             0.569889            0.0304425    0.774396797227444  0.00626003382226123
          0.00951693 0.000263357021276596             0.522858            0.0270741    0.768592154819365  0.00584980677112973
          0.00970727           0.00026522             0.511766            0.0224388    0.761257713002612  0.00546452495571829
REFL_END
SLD_START
  0.50673559   2.00099446   0.00000000
  1.50673559   2.01753155   0.00000000
  2.50673559   2.03403557   0.00000000
SLD_END
EXPT_END 1
EXPT_START 2
REFL_START
# intensity: 1
# background: 9.73295637100827e-07
#           Q (1/A)             dQ (1/A)                    R                   dR               theory              fresnel
          0.00828506 0.000251300425531915             0.841288            0.0698717     1.00000097329564                    1
          0.00845076 0.000252922553191489             0.933339            0.0673631     1.00000097329564                    1
          0.00861978 0.000254576595744681             0.949315             0.060806     1.00000097329564                    1
REFL_END
SLD_START
  0.72030344   5.07606602   0.00000000
  1.72030344   5.03433233   0.00000000
  2.72030344   4.99285891   0.00000000
SLD_END
EXPT_END 2
Done: 15.7372 sec
"""
    def test_sld_parsing(self):
        """ Test that we can parse several SLD profiles in a log """
        data = refl1d.extract_multi_sld_from_log(self.log)
        self.assertEqual(len(data), 3)

    def test_data_parsing(self):
        """ Test that we can parse several refl profiles in a log """
        data = refl1d.extract_multi_data_from_log(self.log)
        self.assertEqual(len(data), 3)


class ToolsTestCase(TestCase):
    """ Test the SLD and capacity tools """
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        self.user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        self.user.save()
        self.client.login(username='john', password='johnpassword')

    def test_sld(self):
        response = self.client.get('/tools/capacity/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/tools/capacity/', {u'material_formula': u'Si', u'electrode_radius': 2,
                                                         u'electrode_thickness': 75, u'ion_packing':3.75,
                                                         u'valence_change':1, u'electrode_density':1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['capacity'], ' 0.337')

    def test_sld_empty_density(self):
        response = self.client.get('/tools/capacity/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/tools/capacity/', {u'material_formula': u'Si', u'electrode_radius': 2,
                                                         u'electrode_thickness': 75, u'ion_packing':3.75,
                                                         u'valence_change':1, u'electrode_density':''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['capacity'], ' 0.786')

class JsonParsingTestCase(TestCase):
    """ Test JSON parsing """
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
                     u'form-0-roughness_min': [u'1.0'], u'form-0-thickness': [u'50.0'], u'q_min': [u'0'],
                     u'form-0-i_sld_min': [u'0.0'], u'form-0-i_sld_max': [u'2.0'], u'form-0-i_sld': [u'1.0'],
                     u'form-0-i_sld_is_fixed': [u'on']}

        # Submit a model, without fitting or evaluating
        self.client.post('/fit/john/1/', form_data)

        self.log = """REFL1D_VERSION 0.8.6
SIMULTANEOUS ["john/1"]
MODEL_PARAMS_START
[chisq=72.4369(32), nllf=11408.8]
MODEL_PARAMS_END
MODEL_JSON_START
{"sample": {"layers": [{"name": "Si", "thickness": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [0, Infinity]}, "value": 0, "name": "Si thickness"}, "irho": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 0.0, "name": "Si irho"}, "rho": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 2.07, "name": "Si rho"}, "interface": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [0, Infinity]}, "value": 5.0, "name": "Si interface"}, "type": "Slab"}, {"name": "SiOx", "thickness": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [0, Infinity]}, "value": 15.0, "name": "SiOx thickness"}, "irho": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 0.0, "name": "SiOx irho"}, "rho": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 3.2, "name": "SiOx rho"}, "interface": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [0, Infinity]}, "value": 1.0, "name": "SiOx interface"}, "type": "Slab"}, {"name": "PS", "thickness": {"fixed": false, "type": "Parameter", "bounds": {"type": "Bounded", "limits": [1800.0, 3000.0]}, "value": 2896.0047607421875, "name": "PS thickness"}, "irho": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 0.0, "name": "PS irho"}, "rho": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 2.055, "name": "PS rho"}, "interface": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [0, Infinity]}, "value": 1.0, "name": "PS interface"}, "type": "Slab"}, {"name": "air", "thickness": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [0, Infinity]}, "value": 0, "name": "air thickness"}, "irho": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 0.0, "name": "air irho"}, "rho": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 0.0, "name": "air rho"}, "interface": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [0, Infinity]}, "value": 0, "name": "air interface"}, "type": "Slab"}], "type": "Stack"}, "type": "Experiment", "probe": {"back_absorption": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [0, 1]}, "value": 1, "name": "back_absorption"}, "intensity": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 1.0, "name": "normalization"}, "type": "QProbe", "theta_offset": {"fixed": true, "type": "Constant", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 0, "name": "theta_offset"}, "background": {"fixed": true, "type": "Parameter", "bounds": {"type": "Unbounded", "limits": [-Infinity, Infinity]}, "value": 0.0, "name": "background"}}, "refl1d": "0.8.6"}
MODEL_JSON_END
Done: 0.981189 sec
"""

    def test_log_parsing(self):
        _, _, problem_list = refl1d_simultaneous.parse_models_from_log(self.log)
        _, data_names, _, _ = model_handling.create_plots_from_fit_problem(problem_list)
        self.assertEqual(len(data_names), 2)
