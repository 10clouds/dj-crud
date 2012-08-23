from collections import OrderedDict
from tastypie import fields
from tastypie import resources

from tenclouds.crud.paginator import Paginator


class ModelDeclarativeMetaclass(resources.ModelDeclarativeMetaclass):
    def __new__(cls, name, bases, attrs):
        meta = attrs.get('Meta')

        if meta and hasattr(meta, 'queryset'):
            setattr(meta, 'object_class', meta.queryset.model)

        new_class = super(resources.ModelDeclarativeMetaclass, cls).__new__(cls, name, bases, attrs)

        # Define the fields
        new_class.base_fields = new_class.get_fields()
        new_class.visible_fields = OrderedDict([(x, y) for x, y in new_class.base_fields.items()
                                         if y.visible])

        if getattr(new_class._meta, 'include_absolute_url', True):
            if not 'absolute_url' in new_class.base_fields:
                new_class.base_fields['absolute_url'] = fields.CharField(attribute='get_absolute_url', readonly=True)
        elif 'absolute_url' in new_class.base_fields and not 'absolute_url' in attrs:
            del(new_class.base_fields['absolute_url'])

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
        fields_order = self.visible_fields.keys()
        fields_title = {}
        fields_url = {}
        fields_sortable = []
        for name, field in self.visible_fields.items():
            fields_title[name] = field.title
            if hasattr(field, 'url'):
                fields_url[name] = field.url
            if field.sortable:
                fields_sortable.append(name)

        return {
            'fieldsOrder': fields_order,
            'fieldsTitle': fields_title,
            'fieldsURL': fields_url,
            'fieldsSortable': fields_sortable,
            'default_format': self._meta.default_format,
            'filterGroups': self._meta.filter_groups(None),
            'perPage': self._meta.per_page,
            'actions': [],  # TODO: Action handler
            'fieldsURL': fields_url,
            'data': {},
        }

    @classmethod
    def get_fields(cls):
        """
        Build the fields dict basing on model fields and additional
        schema params.
        """
        schema = getattr(cls._meta, 'schema', ())
        fields = OrderedDict([(x.field_name, x) for x in schema])

        final_fields = OrderedDict({})

        if not cls._meta.object_class:
            return final_fields

        for name, field_schema in fields.items():
            # Get the model field
            f = cls._meta.object_class._meta.get_field(name)

            # If field is not present in explicit field listing, skip
            if fields and f.name not in fields.keys():
                continue

            if cls.should_skip_field(f):
                continue

            api_field_class = cls.api_field_from_django_field(f)

            kwargs = {
                'attribute': f.name,
                'help_text': f.help_text,
            }

            if f.null is True:
                kwargs['null'] = True

            kwargs['unique'] = f.unique

            if not f.null and f.blank is True:
                kwargs['default'] = ''

            if f.get_internal_type() == 'TextField':
                kwargs['default'] = ''

            if f.has_default():
                kwargs['default'] = f.default

            final_fields[f.name] = api_field_class(**kwargs)
            final_fields[f.name].instance_name = f.name

            # Append the label, it's neede for display reasons
            final_fields[f.name].title = field_schema.title or f.label
            final_fields[f.name].visible = field_schema.visible
            final_fields[f.name].sortable = field_schema.sortable
            if field_schema.url:
                final_fields[f.name].url = field_schema.url

        return final_fields


class Field(object):
    """A field for JSON schema of objects retured by handlers.

    Field attributes are passed to the frontend by "info" handlers, to
    construct appropriate frontend constructs.
    """

    def __init__(self, field_name, title=None, visible=True, sortable=False,
                 url=None):
        """
        :param field_name: field name
        :param title: title displayed by frontend
        :param visible: whether the field should be visible to the user
        :param sortable: whether the field should be sortable
        :param url: TODO PLS
        """
        self.field_name = field_name
        if title is None:
            title = field_name.replace('_', ' ').capitalize()
        self.title = title
        self.visible = visible
        self.url = url
        self.sortable = sortable

    def __str__(self):
        return ("Field: (field_name='%s', title='%s', sortable=%s, visible=%s,"
                " url='%s')" % (self.field_name, self.title, self.sortable,
                                self.visible, self.url))

    def __repr__(self):
        return str(self)
