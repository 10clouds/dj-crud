from tastypie import api

from django.conf.urls.defaults import *

from tastypie.utils import trailing_slash


class Api(api.Api):

    def __init__(self, api_name=None):
        api_name = api_name or "api"
        super(Api, self).__init__(api_name)

    def override_urls(self):
        """
        A hook for adding your own URLs or overriding the default URLs.
        """
        pattern_list = [
            url(r"^(?P<api_name>%s)%s$" % (self.api_name, trailing_slash()), self.wrap_view('dispatch_list'), name="api_%s_dispatch_list" % self.api_name),
            url(r"^(?P<api_name>%s)%s/top_level/$" % (self.api_name, trailing_slash()), self.wrap_view('top_level'), name="api_%s_top_level" % self.api_name),
        ]

        return pattern_list
