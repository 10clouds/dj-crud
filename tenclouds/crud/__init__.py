from tastypie import fields


# Override the default init - every field needs
def __init__(self, attribute=None, default=fields.NOT_PROVIDED, null=False,
             blank=False, readonly=False, unique=False, help_text=None,
             url=None, title=None):
    """
    Sets up the field. This is generally called when the containing
    ``Resource`` is initialized.

    Optionally accepts an ``attribute``, which should be a string of
    either an instance attribute or callable off the object during the
    ``dehydrate`` or push data onto an object during the ``hydrate``.
    Defaults to ``None``, meaning data will be manually accessed.

    Optionally accepts a ``default``, which provides default data when the
    object being ``dehydrated``/``hydrated`` has no data on the field.
    Defaults to ``NOT_PROVIDED``.

    Optionally accepts a ``null``, which indicated whether or not a
    ``None`` is allowable data on the field. Defaults to ``False``.

    Optionally accepts a ``blank``, which indicated whether or not
    data may be omitted on the field. Defaults to ``False``.

    Optionally accepts a ``readonly``, which indicates whether the field
    is used during the ``hydrate`` or not. Defaults to ``False``.

    Optionally accepts a ``unique``, which indicates if the field is a
    unique identifier for the object.

    Optionally accepts ``help_text``, which lets you provide a
    human-readable description of the field exposed at the schema level.
    Defaults to the per-Field definition.
    """
    # Track what the index thinks this field is called.
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


fields.ApiField.__init__ = __init__
