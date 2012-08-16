import json
from collections import namedtuple

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

from piston.utils import rc
from piston.handler import BaseHandler

from handlerutils import AllInList, MetaHandler, CachedMetaHandler


class Handler(BaseHandler):
    """A base CRUD handles class. Bases on piston's Handler class.

    We won't document its basics here, for more info refer to:
        https://bitbucket.org/jespern/django-piston/wiki/Documentation

    For info on how the handler operates and which methods to (re)implement,
    start with the :meth:`read` method documentation.

    :important: All CRUD handlers return objects in the JSON format.
    :tip: For easy-to-use, cached version of this handler, refer to the
          :class:`CachedHandler` class documentation.
    """

    __metaclass__ = MetaHandler

    allowed_methods = ()
    """HTTP methods allowed. One or more of: ``GET``, ``POST``, ``PUT``,
    ``DELETE``. This must be an iterable of strings. Standard practice for
    read-only handler is to define it as this::

        allowed_methods = ("GET", )

    The method mapping same as for ``piston``:

    * :meth:`read` is called on ``GET`` requests, and should never modify data
    * `create` is called on ``POST``, and creates new objects, and should
      return them (or rc.CREATED.)
    * `update` is called on ``PUT``, and should update an existing product and
      return them (or rc.ALL_OK.)
    * `delete` is called on ``DELETE``, and should delete an existing object.
      Should not return anything, just rc.DELETED.
    """

    per_page = 50
    """The number of objects returned per `page`."""

    sort_order = None
    """Desired objects sort order."""

    model = None
    """Model used to retrieve data. It's *not* required, **if** you provide a
    custom :meth:`result_query_set` method, and *don't* use handler actions."""

    schema = ()
    """The schema of returned `objects`. Should be a sequence of :class:`Field`
    class instances. This is the schema reported by handler's meta-info, to be
    processed in frontend.

    You can add ``fields_order`` attibute to specify custom field order, other
    than supplied here."""

    filters = ()
    """The schema of returned `objects`. Should consist of
    :class:`.qfilters.Filter` class (or its derived classes) instances,
    gathered in named :class:`.qfilters.Group` objects. For possible filters,
    look in the :mod:`.qfilters` module.
    """

    static_data = {}
    """Additional static data to be returned by the handler by every request"""

    PaginationValues = namedtuple("PaginationValues", ("page", "per_page",
                                  "offset", "limit"))

    def __init__(self):
        # make a _per_page property which is always an iterable
        if not hasattr(self.per_page, '__iter__'):
            # use AllInList to denote that every value is valid
            self._per_page = AllInList([self.per_page])
        else:
            # only values given in self.per_page will be valid, and pagination
            # will fall back to default value (self.per_page[0]) for invalid
            # ones
            self._per_page = self.per_page

        super(Handler, self).__init__()

    @classmethod
    def url_name(cls):
        """Return django router name.

        Override this if you want this handler to have human-readable URL.
        """
        return 'crud_handler_%s' % cls.__name__

    def read(self, request, *args, **kwargs):
        """Return result for GET `request`.

        The method call chain is as follows:
            1. :meth:`result_query_set` is called to get initial ``QuerySet``
               for the result. If the handler has :attr:`model` specified,
               all model's objects are returned, otherwise you **must**
               implement that method.
            2. For returned ``QuerySet`` we apply filters using the
               :meth:`result_apply_filters` method.
            3. Once we have filtered ``QuerySet``, we apply the sort order
               (if necessary) using the :meth:`result_apply_sort_order` method.
            4. Finally, we call :meth:`result_create` to return the resulting
               dictionary.

        Standard JSON response format for CRUD handlers is as follows:

        .. code-block:: js

            {
                "page": 1,  // page number, starts with 1
                "per_page": 20, // number of objects per page
                "total": 5, // total number of objects matching request criteria
                "objects": [
                    // data...
                ]
            }
        """
        query_set = self.result_query_set(request, *args, **kwargs)
        query_set = self.result_apply_filters(request, query_set, request.GET)
        query_set = self.result_apply_sort_order(request, query_set)
        return self.result_create(request, query_set)

    def result_query_set(self, request):
        """Return initial QuerySet for the request, before applying filters
        and pagination.

        By default, returns `self.model.objects.all()`. You should override
        this method if you want some initial filtering, or simply wish not to
        specify a model.
        """
        if self.model:
            return super(Handler, self).read(request)
        else:
            raise AttributeError("'model' attribute was not provided (and "
                    "the default 'result_query_set()' not overridden)")

    def result_apply_filters(self, request, query, filters,
                             filters_attr="filters"):
        """For given ``query`` object, apply any number of filters and return
        new query object.

        ``filters_attr`` parameter can be used to apply a different group of
        filters (instead of default ``filters``). This should be a string
        naming class property. You can use this parameter to easily switch
        filter sets in your custom methods, or even apply filtering to
        different models.
        """
        # apply any filter from "filter_groups" to given query
        if isinstance(filters, dict):
            groupfilter = filters.get('filters', None)
            groupfilters = (groupfilter,) if groupfilter else ()
        else:
            groupfilters = filters.getlist('filters')

        if not groupfilters:
            return query
        for group in getattr(self, filters_attr):
            query = group.apply_filters(request, query, groupfilters)
        return query

    def result_apply_sort_order(self, request, query):
        """If requested, apply sort order to given ``QuerySet`` and return it.
        """
        sort_attr = request.GET.get('sort', self.sort_order)
        if sort_attr:
            query = query.order_by(sort_attr)

        return query

    def result_per_page(self, request):
        """Get `per_page` from given request if current handler supports more
        than one `per_page` value.

        Always fallback to first possible `per_page` value.
        """
        try:
            per_page = int(request.REQUEST.get('per_page'))
            if not per_page or per_page not in self._per_page:
                raise ValueError()
        except (ValueError, TypeError):
            per_page = self._per_page[0]

        return per_page

    def get_pagination(self, request):
        """Return :class:`PaginationValues` instance, with pagination values
        calculated for a given `request`.

        ``per_page`` is extracted using :meth:`per_page` method, and ``page``
        using :func:`page_from_request`
        """
        per_page = self.result_per_page(request)
        page = page_from_request(request)
        limit = page * per_page
        offset = limit - per_page

        return self.PaginationValues(page, per_page, offset, limit)

    def model_instance_to_raw(self, request, model):
        """Given `model` instance, return its JSON-able representation to be
        returned.
        """
        return model

    def query_convert(self, request, query, offset, limit):
        """Given `request`, `query`, `offset` and `limit`, process query and
        return a dict, containing at least ``objects`` and ``total`` keys.

        Where ``objects`` will be the object in ``objects`` field in returned
        JSON and ``total`` is the reported total number of objects.

        The default behavior is to call ``self.model_instance_to_raw``
        for each object in ``query[offset:limit]``.

        :tip: This is a nice place to apply grouping and other non-trivial
              changes to the result.
        :tip: You can override this method to return ``0`` for ``total``
              to indicate an *endless stream* of results. All standard JS CRUD
              views *should* respect this.
        """
        converter = self.model_instance_to_raw
        objects = [converter(request, o) for o in query[offset:limit]]

        return dict(objects=objects, total=query.count())

    def result_create(self, request, query):
        """Build response for given query, determining ``offset`` and
        ``limit`` for pagination and calling :meth:`query_convert` to get the
        final result.

        Pagination values are extracted using :meth:`get_pagination` method.
        """
        pag = self.get_pagination(request)

        result = self.query_convert(request, query, pag.offset, pag.limit)
        result.update({
            'page': pag.page,
            'per_page': pag.per_page,
        })

        return result

    def prepare_raw_query(self, request, query):
        """Create and return objects query that will be passed to any action
        handler.
        """
        query_set = self.model.objects.all()
        if query.get('id'):
            return query_set.filter(id__in=query['id'])
        return self.result_apply_filters(request, query_set, query.get('filter'))

    @classmethod
    def filter_groups(cls, request):
        """Return list of filter groups. By default return structure build by
        the handler metaclass.
        """
        filters = []
        for group in cls.filters:
            filters.append({
                'title': group.name,
                'filters': group.filter_fields_raw(request),
            })
        return filters


class CachedHandler(Handler):
    """A cached version of the CRUD handler. Every GET (:meth:`read`)
    request is cached.

    Returned results should be pickleable in order to make caching work.
    You can pass ``?nocache=true`` GET parameter to avoid caching.

    This class uses the
    :class:`tenclouds.django.crud.handlerutils.CachedMetaHandler` metaclass
    to decorate the :meth:`read` method.
    """

    __metaclass__ = CachedMetaHandler

    cache_enable = not settings.DEBUG
    """Whether to enable cache. Set to Django's ``not settings.DEBUG`` by
    default. You can change this on existing handlers to disable/enable
    caching dynamically."""

    cache_duration = 60 * 10
    """The cache duration (in seconds). By default, 10 minutes.
    ``0`` cache duration means cache "forever"."""

    cache_prefix = ""
    """The prefix that will be added to each cache key being get/set.
    Useful for cache versioning/invalidation."""

    cache_suffix = ""
    """The suffix that will be added to each cache key being get/set."""

    cache_key_length_limit = 255
    """Cache key length limit. Note that memcache accepts keys up to 255 in
    length. Keys of length above this limit will be trimmed."""

    def cache_key(self, request):
        """Method returning desired cache key for each request. By default,
        the cache key is parametrized by all HTTP GET parameters and their
        values.

        You probably want to override this.
        """
        data = request.GET.iteritems()
        return (self.__class__.__name__ +
                ":".join("%s:%s" % (arg, val) for arg, val in data))

    def _cached_result(self, request):
        """Get the cached result. `request` is used to call the `_key` method.
        """
        if not self.cache_enable:
            return None

        return cache.get(self._key(request))

    def _set_cached_result(self, result, request):
        """Set the cached result. `request` is used to call the `_key` method.
        """
        if not self.cache_enable:
            return

        cache.set(self._key(request), result, self.cache_duration)

    def _key(self, request):
        """Build the cache key using prefix and suffix and respecting the
        limit.
        """
        return "".join((self.cache_prefix, self.cache_key(request),
                       self.cache_suffix))[:self.cache_key_length_limit]


class Field(object):
    """A field for JSON schema of objects retured by handlers.

    Field attributes are passed to the frontend by "info" handlers, to
    construct appropriate frontend constructs.
    """

    def __init__(self, attr_name, title=None, visible=True, sortable=False,
                 url=None):
        """
        :param attr_name: attribute name
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


def gen_info_handler(h):
    """Return handler that should provide info about any piston handler::

        {
            'fieldsOrder': <order of fields>,
            'fieldsTitle': <titles of fields>,
            'fieldsURL': <TODO>,
            'fieldsSortable': <fields which are sortable>,
            'filterGroups': <filter groups>,
            'perPage': <per_page values>,
            'actions': <public actions for a handler>,
            'data': <handler.static_data>
        }

    :warning: This is pretty internal function, please use
              :func:`tenclouds.django.crud.urls.patterns` to automatically
              create info and action handlers for a CRUD handler.
    """

    class HandlerInfo(Handler):
        allowed_methods = ('GET', )
        handler = h

        def __init__(self):
            super(HandlerInfo, self).__init__()

            # cache the response to avoid overhead (the handler info should
            # not change once it has been created)
            self.__cached_response = self.__get_cached_response()

        def read(self, request):
            return self.__cached_response

        def __get_cached_response(self):
            fields_order = getattr(self.handler, 'fields_order',
                                   self.handler.fields)

            fields_url = {}
            fields_title = {}
            fields_sortable = []
            for f in self.handler.schema:
                if f.title:
                    fields_title[f.attr_name] = f.title
                else:
                    name = f.attr_name.replace('_', ' ').capitalize()
                    fields_title[f.attr_name] = name
                if f.url:
                    fields_url[f.attr_name] = f.url
                if f.sortable:
                    fields_sortable.append(f.attr_name)

            per_page = self.handler.per_page
            if not hasattr(per_page, '__iter__'):
                per_page = (per_page, )

            info = {
                'fieldsOrder': fields_order,
                'fieldsTitle': fields_title,
                'fieldsURL': fields_url,
                'fieldsSortable': fields_sortable,
                'filterGroups': self.handler.filter_groups(None),
                'perPage': per_page,
                'actions': self.handler.actions.public,
                'data': self.handler.static_data,
            }

            return HttpResponse(json.dumps(info),
                                content_type="application/json")

        @classmethod
        def url_name(cls):
            return cls.handler.url_name() + '_info'

    return HandlerInfo


def gen_actions_handler(h):
    """Return handler that should process action requests for given handler.

    :warning: This is pretty internal function, please use
              :func:`tenclouds.django.crud.urls.patterns` to automatically
              create info and action handlers for a CRUD handler.
    """

    class ActionsHandler(Handler):
        allowed_methods = ('GET', 'POST')
        handler = h

        def read(self, request):
            return self.handler.actions.public

        def create(self, request):
            # sometimes request.data contains junk instead of deserialized
            # python object :(
            post_data = request.POST.get('data') or request.raw_post_data
            attrs = json.loads(post_data)

            action = attrs.get('action', None)
            query = attrs.get('query', None)
            if action is None or query is None:
                return rc.BAD_REQUEST
            h = self.handler()
            action_handler = getattr(h, h.actions.mapping[action], None)
            if action_handler is None:
                return rc.BAD_REQUEST
            resp = action_handler(request, h.prepare_raw_query(request, query))
            if resp:
                return resp
            return rc.ALL_OK

        @classmethod
        def url_name(cls):
            return cls.handler.url_name() + '_actions'

    return ActionsHandler


def page_from_request(request, value_name='page', default=1):
    """Utility function: get page number from given `request` object.

    If not found or not valid, return `default` value.
    """
    try:
        page_number = int(request.REQUEST.get(value_name, default))
    except (TypeError, ValueError):
        page_number = default
    if page_number < 1:
        page_number = default
    return page_number
