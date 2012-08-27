import functools
import json

from django.http import HttpResponse

from tenclouds.crud.http import HttpDone


class ActionResponse(object):
    def to_response(self):
        raise NotImplementedError


class ActionDone(ActionResponse):
    def to_response(self):
        return HttpDone()


class ActionFileResponse(ActionResponse):
    def __init__(self, filename, fileobj, content_length=None):
        self.filename = filename
        self.fileobj = fileobj
        self.content_length = content_length

    def to_response(self):
        response = HttpResponse(self.fileobj)

        response["Content-Disposition"] = "attachment; filename=%s" % (self.filename,)

        if self.content_length:
            response["Content-Length"] = self.content_length
        return response


class ProcessingOffline(ActionResponse):
    def __init__(self, *status_keys):
        self.status_keys = status_keys

    def to_response(self):
        # currently only first key return is supported
        if self.status_keys:
            return {'statuskey': self.status_keys[0]}
        return HttpDone()


class Redirect(ActionResponse):
    def __init__(self, url):
        self.url = url

    def to_response(self):
        # currently only first key return is supported
        if self.url:
            return {'redirect_url': self.url}
        return HttpDone()


class InvalidFormData(ActionResponse):
    def __init__(self, form):
        self.form = form

    def to_response(self):
        html = unicode(self.form.as_p())
        return HttpResponse(json.dumps(html), status=400,
                            mimetype='application/json')


class ActionHandler(object):
    def __init__(self, public, name, codename, input_form):
        self.public = public
        self.name = name
        self.codename = codename
        self.input_form = input_form


class action_handler(object):
    def __init__(self, public=True, name=None, codename=None, input_form=None):
        self.public = public
        self.name = name
        self.codename = codename
        self.input_form = input_form

    def __call__(self, func):
        codename = self.codename or func.__name__
        name = self.name or codename.replace('_', ' ').capitalize()

        @functools.wraps(func)
        def wrapper(handler, request, *args, **kwargs):
            res = None
            if self.input_form:
                data = json.loads(request.raw_post_data).get('data', {})
                form = self.input_form(data)
                if not form.is_valid():
                    res = InvalidFormData(form)
                args = list(args)
                args.append(form)
            if res is None:
                res = func(handler, request, *args, **kwargs)

            if isinstance(res, ActionResponse):
                return res.to_response()
            return res

        wrapper.action_handler = ActionHandler(self.public, name, codename,
                self.input_form)
        return wrapper
