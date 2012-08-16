from functools import wraps

from piston import handler
from piston.handler import HandlerMetaClass
from tenclouds.crud.utils import to_piston_fields


class Actions(object):
    def __init__(self):
        self.public = []
        self.secret = []
        self.mapping = {}

    def codename_to_callback(self, codename):
        return self.mapping[codename]


class AllInList(list):
    """A small utility class used to avoid some possibly complicated logic.

    This is a list that responds to all "in" queries, and can be used e.g.
    as an object defining valid values: getting elements from it and iteration
    is perfectly standard, only "x in AllInList()" always returns True.
    """
    def __contains__(self, item):
        return True


class MetaHandler(HandlerMetaClass):
    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)
        handler.handler_tracker.append(new_cls)

        # CRUD handlers should not be visible to other piston handlers. That's
        # why we're detaching it from global typemapper

        return new_cls

    def __init__(cls, name, bases, dt):
        fields = []
        visible_fields = []
        for f in cls.schema:
            if f.visible is True:
                visible_fields.append(f.attr_name)
            fields.append(f.attr_name)
            if f.url:
                fields.append(f.url)

        if fields:
            if not 'fields_order' in dt:
                # do not check cls.fields_order, but the class dict, to ensure
                # that every derived class will have its own "fields_order"
                # attribute (attribute checking goes down to base class)
                cls.fields_order = visible_fields
            cls.fields = to_piston_fields(fields)

        # create list of actions
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

        super(MetaHandler, cls).__init__(name, bases, dt)


class CachedMetaHandler(MetaHandler):
    """A metaclass for the CachedHandler.

    Wraps handler's `read` method in the usual cache get/set bloat,
    using `_cached_result` and `_set_cached_result`.

    You can pass "?nocache=true" GET parameter to avoid caching.
    """

    def __init__(cls, name, bases, dt):
        # bind a "cached" version of the read method
        cls.read = CachedMetaHandler.__cache_wrapper(cls.read)

        super(CachedMetaHandler, cls).__init__(name, bases, dt)

    @staticmethod
    def __cache_wrapper(meth):

        @wraps(meth)
        def wrapper(self, request, *args, **kwargs):
            nocache = request.GET.get("nocache")

            if nocache != "true":
                # try to get the result from cache
                cached = self._cached_result(request, *args)
                if cached:
                    return cached

            # set the result in cache
            result = meth(self, request, *args, **kwargs)
            self._set_cached_result(result, request, *args)
            return result

        return wrapper
