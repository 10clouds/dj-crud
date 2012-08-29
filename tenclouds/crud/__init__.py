from tastypie import fields


# Override the default init - every field needs additional url and title param
def __apifield__init__(self, attribute=None, default=fields.NOT_PROVIDED,
                       null=False, blank=False, readonly=False, unique=False,
                       help_text=None, url=None, title=None):
    self.instance_name = None
    self._resource = None
    self.attribute = attribute
    self._default = default
    self.null = null
    self.blank = blank
    self.readonly = readonly
    self.value = None
    self.unique = unique
    self.title = title
    self.url = url

    if help_text:
        self.help_text = help_text

fields.ApiField.__init__ = __apifield__init__


def __relatedfield__init__(self, to, attribute, related_name=None,
                           default=fields.NOT_PROVIDED, null=False, blank=False,
                           readonly=False, full=False, unique=False,
                           help_text=None, url=None, title=None):

    fields.ApiField.__init__(self, attribute, default, null, blank, readonly,
                             unique, help_text, url, title)
    self.to = to
    self.related_name = related_name
    self.full = full
    self.api_name = None
    self.unique = unique
    self._to_class = None

    if self.to == 'self':
        self.self_referential = True
        self._to_class = self.__class__

fields.RelatedField.__init__ = __relatedfield__init__


def __toone__init__(self, *args, **kwargs):
    fields.RelatedField.__init__(self, *args, **kwargs)
    self.fk_resource = None

fields.ToOneField.__init__ = __toone__init__


def __tomany__init__(self, *args, **kwargs):
    fields.RelatedField.__init__(self, *args, **kwargs)
    self.m2m_bundles = []

fields.ToManyField.__init__ = __tomany__init__
