import unittest

#from tenclouds.dev.testhelpers import skip_no_django
#skip_no_django()

from piston.resource import Resource

from tenclouds.crud.utils import to_piston_fields
from tenclouds.crud.handler import Handler


class CrudHandlerTest(unittest.TestCase):
    def test_to_piston_fields(self):
        f = ('a', 'b__c1', 'd', 'e__f__g', 'b__c2')
        expected = ('a', 'd', ('b', ('c1', 'c2')), ('e', ('f', ('g', ))))
        result = to_piston_fields(f)
        self.assertEqual(sorted(result), sorted(expected))


class CrudHandlerTestMixin(object):
    handler_class = None

    def setUp(self):
        if not issubclass(self.handler_class, Handler):
            raise RuntimeError('%s test not configured properly. '
                    '"handler_class" has to be "Handler" subclass' \
                            % type(self).__name__)

    def test_methods_presence(self):
        for http_method, callback_name in Resource.callmap.items():
            callback_exist = hasattr(self.handler_class, callback_name)
            method_allowed = http_method in self.handler_class.allowed_methods
            if method_allowed and not callback_exist:
                self.fail("Missing callback: %s" % callback_name)
            elif not method_allowed and callback_exist:
                self.fail("Callback defined, but method not allowed: %s" % \
                        http_method)


if __name__ == '__main__':
    unittest.main()
