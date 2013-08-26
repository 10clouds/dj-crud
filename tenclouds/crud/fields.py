from tastypie import fields


def create_field_class(name):
    tastypie_class = getattr(fields, name)

    def __init__(self, *args, **kwargs):
        self.title = kwargs.pop('title', None)
        self.url = kwargs.pop('url', None)
        tastypie_class.__init__(self, *args, **kwargs)

    return type(name, (tastypie_class, ), {'__init__': __init__})


def declare_field_classes(names):
    module = globals()
    for name in names:
        module[name] = create_field_class(name)


declare_field_classes(['ApiField', 'BooleanField', 'CharField', 'DateField',
                       'DateTimeField', 'DecimalField', 'DictField',
                       'FileField', 'FloatField', 'ForeignKey', 'IntegerField',
                       'ListField', 'ManyToManyField', 'OneToManyField',
                       'OneToOneField', 'RelatedField', 'TimeField',
                       'ToManyField', 'ToOneField'])
