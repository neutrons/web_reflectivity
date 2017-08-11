from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User

class LocalStoreTestCase(TestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()
        user = User.objects.create_user('john', 'john@test.com', 'johnpassword')
        user.save()

    def test_animals_can_speak(self):
        """Write data in the local store"""
        self.client.login(username='john', password='johnpassword')
        response = self.client.get('/fit/files/')

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['file_list'], '[]')
