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

        if self.per_page is not None:
            req_per_page = int(self.request_data.get('per_page', 0))
            if req_per_page in self.per_page:
                per_page = self.request_data['per_page']
            elif hasattr(self.per_page, '__iter__'):
                per_page = self.per_page[0]
            else:
                per_page = self.per_page
        else:
            per_page = getattr(settings, 'API_LIMIT_PER_PAGE', 20)

        try:
            per_page = int(per_page)
        except ValueError:
            raise BadRequest("Invalid per_page '%s' provided. Please provide a"
                             " positive integer.")

        if per_page < 1:
            raise BadRequest("Invalid per_page '%s' provided. Please provide an"
                             "integer >= 0.")

        return per_page

    def get_page(self, value_name='page', default=1):
        """
        """
        try:
            page_number = int(self.request_data.get(value_name,
                                                    default))
        except (TypeError, ValueError):
            page_number = default
        if page_number < 1:
            page_number = default
        # Fallback to default if provided page is to large
        total = self.get_count()
        per_page = self.get_per_page()
        if total < per_page or (total / per_page) > page_number:
            page_number = default
        return page_number

    def page(self):
        """
        Generates all pertinent data about the requested page.

        Handles getting the correct ``per_page`` & ``offset``, then slices off
        the correct set of results and returns all pertinent metadata.
        """
        per_page = self.get_per_page()
        total = self.get_count()
        page = self.get_page()

        offset = self.offset or per_page * (page - 1)
        objects = self.get_slice(per_page, offset)

        return {
            'offset': offset,
            'per_page': per_page,
            'page': page,
            'total': total,
            'objects': objects,
        }
