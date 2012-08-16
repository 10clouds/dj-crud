from piston import resource, handler
from piston.emitters import Emitter
from piston.utils import coerce_put_post, HttpStatusCode
from piston.utils import rc, translate_mime, MimerDataException

from django.db.models.query import QuerySet
from django.views.decorators.vary import vary_on_headers
from django.http import HttpResponse, Http404, HttpResponseNotAllowed


class Resource(resource.Resource):
    """Patched version of piston's Resource implementation.

    Instead of using global `typemapper`, allow passing custom mapping
    dictionary, which should allow us to specify multiple CRUD handlers for
    single model.
    """

    @property
    def typemapper(self):
        # this has to be lazy, so that we could see all other handlers
        handler_cls = type(self.handler)
        typemapper = handler.typemapper.copy()
        if hasattr(handler_cls, 'model'):
            typemapper[handler_cls] = (handler_cls.model, None)
        return typemapper

    @vary_on_headers('Authorization')
    def __call__(self, request, *args, **kwargs):
        """This is mostly copy-paste from piston code, extept that we're not
        using global typemapper if local is provided
        """
        rm = request.method.upper()

        # Django's internal mechanism doesn't pick up
        # PUT request, so we trick it a little here.
        if rm == "PUT":
            coerce_put_post(request)

        actor, anonymous = self.authenticate(request, rm)

        if anonymous is resource.CHALLENGE:
            return actor()
        else:
            handler = actor

        # Translate nested datastructs into `request.data` here.
        if rm in ('POST', 'PUT'):
            try:
                translate_mime(request)
            except MimerDataException:
                return rc.BAD_REQUEST
            if not hasattr(request, 'data'):
                if rm == 'POST':
                    request.data = request.POST
                else:
                    request.data = request.PUT

        if not rm in handler.allowed_methods:
            return HttpResponseNotAllowed(handler.allowed_methods)

        meth = getattr(handler, self.callmap.get(rm, ''), None)
        if not meth:
            raise Http404

        # Support emitter both through (?P<emitter_format>) and ?format=emitter.
        em_format = self.determine_emitter(request, *args, **kwargs)
        if not em_format:
            request_has_accept = 'HTTP_ACCEPT' in request.META
            if request_has_accept and self.strict_accept:
                return rc.NOT_ACCEPTABLE
            em_format = self.default_emitter

        kwargs.pop('emitter_format', None)

        # Clean up the request object a bit, since we might
        # very well have `oauth_`-headers in there, and we
        # don't want to pass these along to the handler.
        request = self.cleanup_request(request)

        try:
            result = meth(request, *args, **kwargs)
        except Exception, e:
            result = self.error_handler(e, request, meth, em_format)

        try:
            emitter, ct = Emitter.get(em_format)
            fields = handler.fields

            if hasattr(handler, 'list_fields') and isinstance(result, (list, tuple, QuerySet)):
                fields = handler.list_fields
        except ValueError:
            result = rc.BAD_REQUEST
            result.content = "Invalid output format specified '%s'." % em_format
            return result

        status_code = 200

        # If we're looking at a response object which contains non-string
        # content, then assume we should use the emitter to format that
        # content
        if self._use_emitter(result):
            status_code = result.status_code
            # Note: We can't use result.content here because that method attempts
            # to convert the content into a string which we don't want.
            # when _is_string is False _container is the raw data
            result = result._container

        # >>> CUSTOM CRUD CODE HERE <<<

        # use local typemapper
        srl = emitter(result, self.typemapper, handler, fields, anonymous)

        # END CUSTOM CODE
        #
        # ORIGINAL WAS:
        #   srl = emitter(result, typemapper, handler, fields, anonymous)

        try:
            """
            Decide whether or not we want a generator here,
            or we just want to buffer up the entire result
            before sending it to the client. Won't matter for
            smaller datasets, but larger will have an impact.
            """
            if self.stream:
                stream = srl.stream_render(request)
            else:
                stream = srl.render(request)

            if not isinstance(stream, HttpResponse):
                resp = HttpResponse(stream, mimetype=ct, status=status_code)
            else:
                resp = stream

            resp.streaming = self.stream

            return resp
        except HttpStatusCode, e:
            return e.response
