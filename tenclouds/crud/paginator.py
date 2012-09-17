from tastypie import paginator
from tastypie.exceptions import BadRequest

from django.conf import settings


class Paginator(paginator.Paginator):

    def __init__(self, request_data, objects, resource_uri=None, per_page=None,
                 offset=0):
        """
        Instantiates the ``Paginator`` and allows for some configuration.

        The ``request_data`` argument ought to be a dictionary-like object.
        May provide ``per_page`` and/or ``offset`` to override the defaults.
        Commonly provided ``request.GET``. Required.

        The ``objects`` should be a list-like object of ``Resources``.
        This is typically a ``QuerySet`` but can be anything that
        implements slicing. Required.

        Optionally accepts a ``per_page`` argument, which specifies how many
        items to show at a time. Defaults to ``None``, which is no limit.

        Optionally accepts an ``offset`` argument, which specifies where in
        the ``objects`` to start displaying results from. Defaults to 0.
        """
        self.request_data = request_data
        self.objects = objects
        self.per_page = per_page
        self.offset = offset
        self.resource_uri = resource_uri

    def get_per_page(self):
        """
        Determines the proper maximum number of results to return.

        In order of importance, it will use:

            * The user-requested ``per_page`` from the GET parameters, if
              specified
            * The first item of object-level ``per_page`` list if specified.
            * ``settings.API_LIMIT_PER_PAGE`` if specified.

        Default is 20 per page.
        """

        per_page = getattr(settings, 'API_LIMIT_PER_PAGE', 20)

        if self.per_page is not None:
            per_page = self.per_page
            req_per_page = int(self.request_data.get('per_page', 0))
            if hasattr(self.per_page, '__iter__'):
                per_page = self.per_page[0]
                if req_per_page in self.per_page:
                    per_page = req_per_page

        try:
            per_page = int(per_page)
        except ValueError:
            raise BadRequest("Invalid per_page '%s' provided. Please provide a"
                             " positive integer.")

        if per_page < 1:
            raise BadRequest("Invalid per_page '%s' provided. Please provide an"
                             "integer >= 0.")

        return per_page

    def get_page(self, value_name='page', default_min=1,
            total=None, per_page=None):
        """Returns sanitized page number based on self.request_data.
        It is, one of the three: ``default_min``, max available page or the
        request value under ``value_name``.

        Keyword arguments:
        value_name -- name of the variable to look for in self.request_data
        default_min -- page number returned if the page is too small or missing
        total, per_page -- precomputed results (pass if avaialable)

        """
        def _clean_page_number(pgno):
            # too small
            if pgno < 1:
                return default_min

            # too big
            total = self.get_count()
            per_page = self.get_per_page()
            max_page = total / per_page
            if pgno > max_page:
                return max_page

            # all fine
            return pgno
        try:
            page_number = int(self.request_data.get(value_name, default_min))
            return _clean_page_number(page_number)
        except (TypeError, ValueError):
            return default_min

    def page(self):
        """
        Generates all pertinent data about the requested page.

        Handles getting the correct ``per_page`` & ``offset``, then slices off
        the correct set of results and returns all pertinent metadata.
        """
        per_page = self.get_per_page()
        total = self.get_count()
        page = self.get_page(total=total, per_page=per_page)

        offset = self.offset or per_page * (page - 1)
        objects = self.get_slice(per_page, offset)

        return {
            'offset': offset,
            'per_page': per_page,
            'page': page,
            'total': total,
            'objects': objects,
        }
