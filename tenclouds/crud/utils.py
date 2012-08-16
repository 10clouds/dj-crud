import collections


def to_piston_fields(fields):
    """Convert django's query fields format 'a__b__c' to piston's format
    ('a', ('b', ('c', )))
    """
    def _convert(field):
        if '__' not in field:
            return field
        parts = field.split('__')
        closure = None
        for p in parts[::-1]:
            if closure:
                closure = (p, closure)
            else:
                closure = (p, )
        return closure

    def _merge_similar(closure):
        cmap = collections.defaultdict(list)
        for c in closure:
            if isinstance(c, tuple):
                cmap[c[0]].extend(c[1])
        result = set()
        for c in closure:
            if isinstance(c, tuple):
                result.add((c[0], tuple(cmap[c[0]])))
            else:
                result.add(c)
        return tuple(result)

    converted = [_convert(f) for f in fields]
    converted = _merge_similar(converted)
    return tuple(converted)


