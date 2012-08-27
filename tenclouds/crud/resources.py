from tastypie.authorization import Authorization
from tastypie.exceptions import ImmediateHttpResponse
from tastypie import http
from tastypie import resources
from tastypie.utils import trailing_slash

from django.conf.urls.defaults import url
from django.http import QueryDict

from tenclouds.crud.paginator import Paginator


class Actions(object):
    def __init__(self):
        self.public = []
        self.secret = []
        self.mapping = {}

    def codename_to_callback(self, codename):
        return self.mapping[codename]


class ModelDeclarativeMetaclass(resources.ModelDeclarativeMetaclass):
    def __new__(cls, name, bases, attrs):
        """
        Get the class from super and apply the schema definitons to all
        existing fields
        """
        new_class = super(ModelDeclarativeMetaclass, cls).__new__(cls, name,
                                                                  bases, attrs)
        new_class.apply_schema_fields()

        return new_class

    def __init__(cls, name, bases, dt):
        # Create the list of actions
        actions = Actions()
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if not hasattr(attr, 'action_handler'):
                continue
            action_info = {
                'codename': attr.action_handler.codename,
                'name': attr.action_handler.name,
            }
            if attr.action_handler.input_form:
                action_info['form'] = str(attr.action_handler.input_form().as_p())
            if attr.action_handler.public:
                actions.public.append(action_info)
            else:
                actions.secret.append(action_info)
            actions.mapping[attr.action_handler.codename] = attr_name
        cls.actions = actions

        super(ModelDeclarativeMetaclass, cls).__init__(name, bases, dt)


class ModelResource(resources.ModelResource):
    """
    This is a patched verion of tastypie resource. We use the
    schema element which contains our own Field() objects.
    They contain information needed by the frontend to know how to
    display the data.

    We also use a per_page list that can contain many pagination options.
    For this need we have our own Paginator class that implements all
    the necessary logic for the frontend that wasn't present in tastypie's
    implementation.

    # TODO: filters, groups
    """
    __metaclass__ = ModelDeclarativeMetaclass

    def __init__(self, api_name=None):
        self._meta.paginator_class = Paginator
        self._meta.authorization = Authorization()  # Don't block any actions
        self._meta.filter_groups = lambda x: None  # TODO
        self._meta.schema = ()
        super(ModelResource, self).__init__(api_name)

    def get_list(self, request, **kwargs):
        """
        Returns a serialized list of resources.

        Calls ``obj_get_list`` to provide the data, then handles that result
        set and serializes it.

        Should return a HttpResponse (200 OK).
        """
        # TODO: Uncached for now. Invalidation that works for everyone may be
        #       impossible.
        objects = self.obj_get_list(request=request, **self.remove_api_resource_names(kwargs))
        sorted_objects = self.apply_sorting(objects, options=request.GET)

        paginator = self._meta.paginator_class(request.GET, sorted_objects,
                                               resource_uri=self.get_resource_list_uri(),
                                               per_page=self._meta.per_page)
        to_be_serialized = paginator.page()

        # Dehydrate the bundles in preparation for serialization.
        bundles = [self.build_bundle(obj=obj, request=request) for obj in to_be_serialized['objects']]
        to_be_serialized['objects'] = [self.full_dehydrate(bundle) for bundle in bundles]
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        return self.create_response(request, to_be_serialized)

    def dispatch_actions(self, request, **kwargs):
        """
        The custom actions dispatcher.

        Get the POST request, deserialize it, check wether the methods
        are allowed and return the action result.
        """
        deserialized = self._meta.serializer.deserialize(request.raw_post_data,
                                                         format='application/json')
        action_name = deserialized.get("action", None)
        if not action_name or not self.actions.mapping.get(action_name, None):
            raise ImmediateHttpResponse(response=http.HttpNotImplemented())

        # Get only the data that are needed for further processing
        new_post = QueryDict("")
        new_post = new_post.copy()
        new_post.update(deserialized.get("query", {}))
        request.POST = new_post

        # Get the request method out of method name and convert the request
        # This ensures all tastypie mechanisms will work properly
        request_method = action_name.split("_")[:-1]
        if request.method in ['get', 'put', 'delete', 'patch']:
            request = resources.convert_post_to_VERB(request, request_method.upper())

        # Check wether the desired method is allowed here
        self.method_check(request, allowed=self._meta.allowed_methods)

        # Get the action method
        action = getattr(self, action_name, None)
        if action is None:
            raise ImmediateHttpResponse(response=http.HttpNotImplemented())

        # Check all needed permissions
        self.is_authenticated(request)
        self.is_authorized(request)
        self.throttle_check(request)

        # At last return the method result
        return action(request, **kwargs)

    def override_urls(self):
        """
        Append the actions handler method.
        """
        return [
            url(r"^(?P<resource_name>%s)/_actions%s$" % (self._meta.resource_name, trailing_slash()),
                self.wrap_view('dispatch_actions'),
                name="api_dispatch_actions"),
        ]

    def build_schema(self):
        """
        Returns a dictionary of all the fields on the resource and some
        properties about those fields.

        Used by the ``schema/`` endpoint to describe what will be available.
        """

        return {
            'fieldsOrder': self._meta.fields,
            'fieldsTitle': self.fields_title,
            'fieldsURL': self.fields_url,
            'fieldsSortable': self._meta.ordering,
            'default_format': self._meta.default_format,
            'filterGroups': self._meta.filter_groups(None),
            'perPage': self._meta.per_page,
            'actions': self.actions.public,
            'fieldsURL': self.fields_url,
            'data': {},
        }

    @classmethod
    def apply_schema_fields(cls):
        """Apply CRUD schema params to each field set for this resource"""
        schema = getattr(cls._meta, 'schema', None)
        if not schema:
            return

        # Set the list of fields to return, this also defines the column order
        cls._meta.fields = [x.attr_name for x in schema if x.visible]

        # Set the fields that should have an url
        cls.fields_url = dict([(x.attr_name, x.url) for x in schema
                               if hasattr(x, 'url') and x.url])

        # And the field titles
        cls.fields_title = dict([(x.attr_name, x.title) for x in schema])

        # And define which ones should be sortable
        cls._meta.ordering = [x.attr_name for x in schema if x.sortable]


class Field(object):
    """A field for JSON schema of objects retured by handlers.

    Field attributes are passed to the frontend by "info" handlers, to
    construct appropriate frontend constructs.
    """

    def __init__(self, attr_name, title=None, visible=True, sortable=False,
                 url=None):
        """
        :param field_name: field name
        :param title: title displayed by frontend
        :param visible: whether the field should be visible to the user
        :param sortable: whether the field should be sortable
        :param url: TODO PLS
        """
        self.attr_name = attr_name
        if title is None:
            title = attr_name.replace('_', ' ').capitalize()
        self.title = title
        self.visible = visible
        self.url = url
        self.sortable = sortable

    def __str__(self):
        return ("Field: (attr_name='%s', title='%s', sortable=%s, visible=%s,"
                " url='%s')" % (self.attr_name, self.title, self.sortable,
                                self.visible, self.url))

    def __repr__(self):
        return str(self)
