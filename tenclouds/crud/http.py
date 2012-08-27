from django.http import HttpResponse


class HttpDone(HttpResponse):
    status_code = 200
