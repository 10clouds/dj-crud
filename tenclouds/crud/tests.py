import unittest

#from tenclouds.dev.testhelpers import skip_no_django
#skip_no_django()


from tenclouds.crud.handler import Handler


class CrudHandlerTest(unittest.TestCase):
    pass


class CrudHandlerTestMixin(object):
    handler_class = None

    def setUp(self):
        if not issubclass(self.handler_class, Handler):
            raise RuntimeError('%s test not configured properly. '
                    '"handler_class" has to be "Handler" subclass' \
                            % type(self).__name__)


if __name__ == '__main__':
    unittest.main()
