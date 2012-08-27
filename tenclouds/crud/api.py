from tastypie import api

from django.conf.urls.defaults import *


class Api(api.Api):

    def __init__(self, api_name=None):
        api_name = api_name or "api"
        super(Api, self).__init__(api_name)
