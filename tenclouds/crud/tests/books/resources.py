from django.http import HttpResponse

from tenclouds.crud import actions
from tenclouds.crud import fields
from tenclouds.crud import resources

from tenclouds.crud.tests.books.models import Book


class BookResource(resources.ModelResource):
    id = fields.ObjectId(attribute="id")
    title = fields.CharField(attribute="title", url="resource_uri")
    is_available = fields.BooleanField(attribute="is_available")
    author_name = fields.CharField(attribute="author_name", title="Author", null=True)

    class Meta:
        list_allowed_methods = ['get', ]
        queryset = Book.objects.all()
        per_page = 10
        ordering = ['title', 'is_available']
        fields = ['id', 'title', 'is_available', 'author_name']

    def dehydrate_is_available(self, bundle):
        """
        Get the human readable values of is_available
        """
        mapping = {True: "Available", False: "Not available"}
        return mapping.get(bundle.data['is_available'], "Not available")

    @actions.action_handler()
    def get_action(self, request, **kwargs):
        return HttpResponse(content='Here be dragons!')
