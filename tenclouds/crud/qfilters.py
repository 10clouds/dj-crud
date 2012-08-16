import copy

from django.db.models import Q


class Group(object):
    def __init__(self, name, *fields, **kwargs):
        self.name = name
        self.fields = fields
        self.query_joiner = kwargs.get('join', 'and')
        if self.query_joiner not in ['and', 'or']:
            raise TypeError('Unknown query joiner: %s' % self.query_joiner)

    def filter_fields(self, request):
        """Yield filters"""
        for f in self.fields:
            if isinstance(f, DynamicFilter):
                for ff in f.filter_fields(request):
                    yield ff
            else:
                yield f

    def filter_fields_raw(self, request):
        """Return raw, JSONable list of filters.
        """
        raw = []
        for f in self.filter_fields(request):
            raw.append(f.to_raw_field())
        return raw

    def filter_by_key(self, key, request):
        """Return filter with given ``key`` or ``None`` if not found in
        current group.
        """
        for field in self.filter_fields(request):
            if field.affected_by(key):
                return field
        return None

    def apply_filters(self, request, query, filter_keys):
        """Apply filters to given `query`. `filter_keys` list may contain keys
        that do not belong to current filter group.
        """
        filters = ((self.filter_by_key(key, request), key)
                   for key in filter_keys)
        filters = [(f, k) for f, k in filters if f]

        # filter using AND
        if self.query_joiner == 'and':
            for f, key in filters:
                query = query.filter(f.build_filters(key))
            return query

        # filter using OR
        elif self.query_joiner == 'or':
            q = Q()
            for f, key in filters:
                q |= f.build_filters(key)
            return query.filter(q)

        raise TypeError('Unknown query joiner: %s' % self.query_joiner)


class BaseFilter(object):
    def affected_by(self, key):
        return self.key == key

    def build_filters(self, raw_key):
        raise NotImplementedError

    def to_raw_field(self):
        """
        Return value will be available in the JS filter code
        """
        raise NotImplementedError


class Filter(BaseFilter):
    value = None
    field_type = 'choice'

    def __init__(self, name, query=None, **filters):
        """Initialize the filter.

        :param name: the filter name.
        :param query: (optional) a django Q object to perform filtering
        :param **filters: kwargs filters to be applied

        If `query` is given, `filters` are not considered.
        """
        self.name = name
        self.filters = filters
        self.key = self.build_key()
        self.query = query

    def build_key(self):
        """Return filter `id` for current :class:`Filter` instance
        """
        parts = []
        for k, v in self.filters.iteritems():
            parts.append('%s:%s' % (k, v))
        return '.'.join(parts)

    def build_filters(self, raw_key):
        """Apply filter's query (Q object) or build a Q from Filter's
        filters.
        """
        return self.query or Q(**self.filters)

    def to_raw_field(self):
        return {
            'key': self.key,
            'name': self.name,
            'type': self.field_type,
        }


class RadioFilterField(Filter):
    field_type = 'radio'

    @property
    def group_key(self):
        return self.key.split(':', 1)[0]

    def to_raw_field(self):
        return {
            'key': self.key,
            'groupKey': self.group_key,
            'name': self.name,
            'type': self.field_type,
        }


class RadioNoFilterField(RadioFilterField):
    field_type = 'radio:nofilter'

    def __init__(self, name, group_key):
        self.name = name
        self.key = group_key

    @property
    def group_key(self):
        return self.key


class DynamicFilter(object):
    def filter_fields(self, request):
        raise NotImplementedError


class ChoicesFilter(DynamicFilter):
    def __init__(self, choices, filter_attr):
        self.choices = choices
        self.filter_attr = filter_attr

    def filter_fields(self, request):
        for query_value, name in self.choices:
            yield Filter(name, **{self.filter_attr: query_value})


class RadioFilter(DynamicFilter):
    def __init__(self, choices, filter_attr, no_filter=None):
        self.choices = choices
        self.filter_attr = filter_attr
        self.no_filter = no_filter

    def filter_fields(self, request):
        if self.no_filter:
            yield RadioNoFilterField(self.no_filter, self.filter_attr)
        for name, query_value in self.choices:
            f = {self.filter_attr: query_value}
            yield RadioFilterField(name, **f)


class QueryFilter(DynamicFilter):
    def __init__(self, query, filter_attr):
        self._query = query
        self.filter_attr = filter_attr

    @property
    def query(self):
        # hope this would help us to avoid query cache
        return copy.copy(self._query)

    def filter_fields(self, request):
        for key, name in self.query:
            yield Filter(name, **{self.filter_attr: key})


class FullTextSearch(BaseFilter):
    field_type = 'text'

    def __init__(self, key, *filters):
        self.key = key
        self.filters = filters
        self.name = None

    def affected_by(self, key):
        try:
            return key.split(':', 1)[0] == self.key
        except IndexError:
            return False

    def build_filters(self, raw_key):
        q = Q()
        value = raw_key.split(':', 1)[1]
        for f in self.filters:
            q |= Q(**{f: value})
        return q

    def to_raw_field(self):
        return {
            'key': self.key,
            'name': self.name,
            'type': self.field_type,
        }


class AliasFilter(DynamicFilter):
    """A filter that consists of filter "aliases", to hide internal DB
    structure, or to simplify join queries.

    The filter takes one argument, a dict, defining aliased filters, in
    format::

        "param_name": {
            "param_value1": <Q object OR
                             a callable that takes request and returns Q>,
            "param_value2": ...
            ...
        }

    Such defined filter may be used now in this way:
        ``http://some.api.url?filters=param_name:param_value1``

    TODO make it more flexible?
    """
    def __init__(self, aliases):
        self.aliases = aliases

    def filter_fields(self, request):
        """Will yield new Filter objects basing on aliases config"""

        for name, values in self.aliases.iteritems():
            for alias, query in values.iteritems():
                # determine whether "query" is a callable or not
                if callable(query) and request is not None:
                    q = query(request)
                else:
                    q = query

                # define Filter classes on the fly: make them "respond"
                # to param_name:param_value queries.
                class F(Filter):
                    def build_key(self):
                        return "{0}:{1}".format(name, alias)

                yield F(alias, query=q)

