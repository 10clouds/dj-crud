from django.conf.urls import defaults

# Import the patched tastypie Api and register our resource
from tenclouds.crud.api import Api


def patterns(resource, api_name=None, authentication=None):
    """Build and return default patterns routing for a CRUD handler.

    Will build additional `schema/$`` and ``_actions/$`` URLs with info and
    actions handlers for your handler, so the CRUD frontend can know how to
    present the data.
    """

    api = Api(api_name=api_name)  # default api_name is "api"
    api.register(resource)

    return defaults.patterns('',
        (r'^', defaults.include(api.urls)),
    )
