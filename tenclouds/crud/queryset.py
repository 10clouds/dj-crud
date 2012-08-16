import types


class QuerySetAdapter(object):
    """Experimental, simple class to mock some functionality of Django's
    ``QuerySet`` class.

    Use it to mock QuerySet and use CRUD's goodness for results that are not
    extracted from Django's ORM, or are impossible to be presented in that way.

    The format of returned data is solely dependent on generator or iterable
    you supply to the constructor.

    What works:
        - iteration
        - ``count()`` / ``len()``

    What's to do:
        - ``filter()``, ``exclude()``
        - possibly, other things.
    """

    def __init__(self, iterable, count_or_func, **extra):
        """
        :param iterable: any iterable.
        :param count_or_func: an int or function returning total number of
                              elements in iterable.
        :param extra: any other attributes to be set on this object.
        """
        self.iterable = iterable

        if type(count_or_func) == types.FunctionType:
            self.count_func = count_or_func
        else:
            self.count_func = lambda: count_or_func

        for k, v in extra.iteritems():
            setattr(self, k, v)

    def __iter__(self):
        return (item for item in self.iterable)

    def __len__(self):
        return self.count()

    def count(self):
        return self.count_func()
