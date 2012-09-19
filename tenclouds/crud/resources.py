from tastypie.authorization import Authorization
from tastypie.cache import SimpleCache
from tastypie.exceptions import ImmediateHttpResponse
from tastypie import http
from tastypie import resources
from tastypie.utils import trailing_slash

from django.conf.urls.defaults import url
from django.http import QueryDict

from tenclouds.crud import fields
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
        new_class = super(ModelDeclarativeMetaclass, cls).__new__(cls, name, bases, attrs)
        # Don't return the resource_uri in fields order by default.
        new_class.base_fields['resource_uri'].visible = False
        if not hasattr(new_class._meta, 'filters'):
            new_class._meta.filters = ()
        if not hasattr(new_class._meta, 'static_data'):
            new_class._meta.static_data = {}
        if not hasattr(new_class._meta, 'per_page'):
            new_class._meta.per_page = None
        if not hasattr(new_class._meta, 'paginator_class'):
            new_class._meta.paginator_class = Paginator
        if not hasattr(new_class._meta, 'authorization'):
            new_class._meta.authorization = Authorization()
        if not hasattr(new_class._meta, 'cache'):
            new_class._meta.cache = SimpleCache()

        # Set up the fields with url values
        for name, field in new_class.base_fields.items():
            if not field.url:
                continue
            new_class.base_fields[field.url] = fields.CharField(readonly=True)

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
    """
    __metaclass__ = ModelDeclarativeMetaclass

    def __init__(self, api_name=None):
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
        ordering = dict(request.GET)
        if getattr(self._meta, 'ordering', False):
            ordering.setdefault('order_by', self._meta.ordering)
        sorted_objects = self.apply_sorting(objects, options=ordering)

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
        new_post.update({'data': deserialized.get("data", {})})
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

        fields_order = self._meta.fields or self.fields.keys()

        fields_title = dict([(name, field.title or name.capitalize())
                             for name, field in self.fields.items()])
        fields_url = dict([(name, field.url) for name, field in self.fields.items() if field.url])

        return {
            'fieldsOrder': fields_order,
            'fieldsTitle': fields_title,
            'fieldsURL': fields_url,
            'fieldsSortable': self._meta.ordering,
            'default_format': self._meta.default_format,
            'filterGroups': self.filter_groups(None),
            'perPage': self._meta.per_page,
            'actions': self.actions.public,
            'data': self._meta.static_data,
        }

    @classmethod
    def filter_groups(cls, request):
        """Return list of filter groups. By default return structure build by
        the handler metaclass.
        """
        filters = []
        for group in cls._meta.filters:
            filters.append({
                'title': group.name,
                'filters': group.filter_fields_raw(request),
            })
        return filters

    def apply_filters(self, request, applicable_filters):
        query = super(ModelResource, self).apply_filters(request, applicable_filters)
        return self.result_apply_filters(request, query, request.GET)

    def result_apply_filters(self, request, query, filters):
        """For given ``query`` object, apply any number of filters and return
        new query object.
        """
        # apply any filter from "filter_groups" to given query
        if not isinstance(filters, dict):
            groupfilter = filters.get('filters', None)
            groupfilters = (groupfilter,) if groupfilter else ()
        else:
            groupfilters = filters.getlist('filters')

        if not filters:
            return query
        for group in self._meta.filters:
            query = group.apply_filters(request, query, groupfilters)
        return query
