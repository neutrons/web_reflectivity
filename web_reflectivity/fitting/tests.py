from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User

class LocalStoreTestCase(TestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        user.save()
        self.client.login(username='john', password='johnpassword')

    def test_file_list(self):
        """Write data in the local store"""
        response = self.client.get('/fit/files/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['file_list'], '[]')

        # Upload data
        with open('test/test_data.txt') as fp:
            response = self.client.post('/fit/files/', {'id_file': 'test_data.txt', 'attachment': fp})
            print(response.context['file_list'])
            #self.assertEqual(response.context['file_list'], '[]')