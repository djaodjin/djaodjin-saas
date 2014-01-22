import os.path

from django.contrib.auth.models import User
from casper.tests import CasperTestCase

from saas.models import UserModel, Signature

class UpdateCardTest(CasperTestCase):
    fixtures = ['test_data']

    def test_sunny(self):
        u = UserModel.objects.get(username='demo')
        Signature.objects.create_signature('terms_of_use', u)
        self.client.login(username='demo', password='yoyo')
        self.assertTrue(self.casper(
            os.path.join(os.path.dirname(__file__),
                'casper-tests/sunny.js')))
