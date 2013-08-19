import json

from django.http import HttpResponse


class HttpDone(HttpResponse):
    status_code = 200


class HttpJson(HttpResponse):
    def __init__(self, content, status=None):
        super(HttpJson, self).__init__(
            content=json.dumps(content, ensure_ascii=False).encode('utf-8'),
            content_type='application/json; charset=UTF-8',
            status=status)
