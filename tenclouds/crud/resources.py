from collections import OrderedDict
from tastypie import fields
from tastypie import resources

from tenclouds.crud.paginator import Paginator


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

    # TODO: filters, groups and actions
    """
    __metaclass__ = ModelDeclarativeMetaclass

    def __init__(self, api_name=None):
        self._meta.paginator_class = Paginator
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

    def build_schema(self):
        """
        Returns a dictionary of all the fields on the resource and some
        properties about those fields.

        Used by the ``schema/`` endpoint to describe what will be available.
        """

        return {
            'fieldsOrder': self.ordering,
            'fieldsTitle': self.fields_title,
            'fieldsURL': self.fields_url,
            'fieldsSortable': self.fields_sortable,
            'default_format': self._meta.default_format,
            'filterGroups': self._meta.filter_groups(None),
            'perPage': self._meta.per_page,
            'actions': [],  # TODO: Action handler
            'fieldsURL': self.fields_url,
            'data': {},
        }

    @classmethod
    def apply_schema_fields(cls):
        """Apply CRUD schema params to each field set for this resource"""
        schema = getattr(cls._meta, 'schema', None)
        if not schema:
            return

        # Apply the ordering
        cls.ordering = [x.attr_name for x in schema]
        cls.fields = [x.attr_name for x in schema if x.visible]
        cls.fields_url = dict([(x.attr_name, x.url) for x in schema
                               if hasattr(x, 'url') and x.url])
        cls.fields_title = dict([(x.attr_name, x.title) for x in schema])
        cls.fields_sortable = [x.attr_name for x in schema if x.sortable]


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
