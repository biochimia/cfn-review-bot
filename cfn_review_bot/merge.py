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


def deep_merge(old, new):
  if (isinstance(old, dict)
      and isinstance(new, dict)):
    return _deep_merge_mapping(old, new)

  raise Exception('Unable to merge {} with {}'.format(old, new))
