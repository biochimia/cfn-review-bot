def _deep_merge_mapping(old, new):
    merged = {}
    merged.update(old)

    for k, nv in new.items():
        try:
            ov = merged[k]
        except KeyError:
            merged[k] = nv
            continue

        merged[k] = deep_merge(ov, nv)

    return merged


def _deep_merge_sequence(old, new):
    return old + new


def deep_merge(old, new):
    if (isinstance(old, dict)
            and isinstance(new, dict)):
        return _deep_merge_mapping(old, new)

    if (isinstance(old, list)
            and isinstance(new, list)):
        return _deep_merge_sequence(old, new)

    if old == new:
        return old

    raise Exception('Unable to merge {} with {}'.format(old, new))
