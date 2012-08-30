from tenclouds.crud import urls as crud_urls

from django.conf.urls.defaults import patterns, url, include

from tenclouds.crud.tests.books.resources import BookResource

urlpatterns = patterns('',
    url(r'^',
        include(crud_urls.patterns(resource=BookResource(),
                                   api_name="test_api"))),
)
