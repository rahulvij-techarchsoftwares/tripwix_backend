import json

from django.test import Client, TestCase
from django.urls import reverse

from .factories import ContentFactory


class KubiContentTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.Content = ContentFactory._meta.model

    def test_crud_page_content(self):
        # create
        page_content = ContentFactory(unique_name='test-content')

        # read
        self.assertEqual(page_content.unique_name, 'test-content')
        self.assertEqual(page_content.pk, page_content.id)
        self.assertQuerysetEqual(self.Content.objects.all(), ['<Content: test-content (1ZEYaEQ)>'])

        # update
        page_content.unique_name = 'new-name'
        page_content.save()
        self.assertQuerysetEqual(self.Content.objects.all(), ['<Content: new-name (1ZEYaEQ)>'])
