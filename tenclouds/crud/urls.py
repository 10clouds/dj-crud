from django.conf.urls import defaults

# instead of using default piston Resource class, import patched version that
# would allow us to provide custom type mapping
from tenclouds.crud.resource import Resource
from tenclouds.crud.handler import gen_info_handler, gen_actions_handler


def patterns(handler_cls, authentication=None):
    """Build and return default patterns routing for a CRUD handler.

    Will build additional ``_info/$`` and ``_actions/$`` URLs with info and
    actions handlers for your handler, so the CRUD frontend can know how to
    present the data.
    """

    resource = Resource(handler_cls, authentication=authentication)

    info_handler_cls = gen_info_handler(handler_cls)
    info_resource = Resource(info_handler_cls, authentication=authentication)
    actions_handler_cls = gen_actions_handler(handler_cls)
    actions_resource = Resource(actions_handler_cls, authentication=authentication)

    return defaults.patterns('',
        defaults.url(r'^$',
            resource,
            name=handler_cls.url_name()
        ),
        defaults.url(r'^_info/$',
            info_resource,
            name=info_handler_cls.url_name()
        ),
        defaults.url(r'^_actions/$',
            actions_resource,
            name=actions_handler_cls.url_name()
        )
    )
