import json
from mongoengine import connect
from mongoengine.connection import disconnect

from django.conf import settings
from django.core.management import call_command
from django.core.urlresolvers import reverse
from django.db.models import loading
from django import test


from tenclouds.crud.tests.books.models import Book
from tenclouds.crud.tests.books.resources import BookResource


class TestCase(test.TestCase):
    apps = ('tenclouds.crud.tests.books', )
    urls = 'tenclouds.crud.tests.books.urls'
    fixtures = ['tenclouds/crud/tests/books/fixtures/initial_data.json', ]

    def _pre_setup(self):
        # Add the test models to the db
        disconnect('crud-local')
        connect('crud-test-local')
        self._original_installed_apps = settings.INSTALLED_APPS
        settings.INSTALLED_APPS = self.apps
        settings.TASTYPIE_FULL_DEBUG = True
        loading.cache.loaded = False
        call_command('syncdb', interactive=False, verbosity=0)
        # Call the original method that does the fixtures etc.
        #super(TestCase, self)._pre_setup()

    def setUp(self):
        self.resource = BookResource()
        self.url_kwargs = {'resource_name': self.resource._meta.resource_name,
                           'api_name': "test_api"}
        self.c = test.client.Client()

    def test_database(self):
        self.assertEqual(Book.objects.count(), 12)

    def test_resource_meta(self):
        self.assertEqual(self.resource._meta.ordering, ['title', 'is_available'])
        self.assertEqual(self.resource._meta.per_page, 10)
        self.assertEqual(self.resource._meta.list_allowed_methods, ['get', ])

    def test_resource_actions(self):
        self.assertEqual(len(self.resource.actions.public), 1)
        self.assertEqual(len(self.resource.actions.secret), 0)

        # Test an existing method
        self.assertTrue(self.resource.get_action.__name__ in
                        self.resource.actions.mapping)
        actions_url = reverse('api_dispatch_actions', kwargs=self.url_kwargs)

        response = self.c.post(actions_url,
                               json.dumps({"action": "get_action"}),
                               "text/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, "Here be dragons!")

        # And test another one that does not exist
        self.assertFalse('some_other_method' in self.resource.actions.mapping)
        actions_url = reverse('api_dispatch_actions', kwargs=self.url_kwargs)

        response = self.c.post(actions_url,
                               json.dumps({"action": "some_other_method"}),
                               "text/json")
        self.assertEqual(response.status_code, 501)

    def test_schema(self):
        schema_url = reverse('api_get_schema', kwargs=self.url_kwargs)
        response = self.c.get(schema_url, {}, "text/json")
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(content['fieldsSortable'],
                         self.resource._meta.ordering)
        self.assertEqual(content['fieldsOrder'], self.resource._meta.fields)

    def test_allowed_requests(self):
        list_url = reverse('api_dispatch_list', kwargs=self.url_kwargs)
        response = self.c.get(list_url, {}, "text/json")
        print response
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(content['total'], 12)

    def test_forbidden_requests(self):
        kwargs = self.url_kwargs.copy()
        kwargs.update({'pk_list': '1;2'})
        get_multiple_url = reverse('api_get_multiple', kwargs=kwargs)
        response = self.c.post(get_multiple_url, {}, "text/json")
        self.assertEqual(response.status_code, 405)

        list_url = reverse('api_dispatch_list', kwargs=self.url_kwargs)
        response = self.c.delete(list_url, {}, "text/json")
        self.assertEqual(response.status_code, 405)

    def _post_teardown(self):
        # Call the original method.
        #super(TestCase, self)._post_teardown()
        # Restore the settings.
        settings.INSTALLED_APPS = self._original_installed_apps
        loading.cache.loaded = False
        disconnect('crud-test-local')
