from django.test import TransactionTestCase

from .factories import EmailFactory


class EmailModelsTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.email = EmailFactory()
        self.email.refresh_from_db()

    def test_email_str(self):
        self.assertTrue(self.email.__str__())
