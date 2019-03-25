import os
import os.path

from . import loader


DIRECTORY_BLACKLIST = [
  'node_modules',
  'vendor',
]


def normalize_key(proto_key):
  key = None

  it = iter(proto_key)
  for ch in it:
    if not ch.isascii():
      continue

    if key is None:
      if not ch.isalpha():
        continue
      key = ch
    elif not ch.isalnum():
      continue
    else:
      key += '-' + ch

    for ch in it:
      if not ch.isascii() or not ch.isalnum():
        break
      key += ch

  return key


def _key_from_path(root, path):
  return normalize_key(os.path.splitext(
    os.path.relpath(path, start=root))[0])


def filter_directories(dirnames):
  for d in dirnames:
    if d.startswith('.'):
      continue
    if d in DIRECTORY_BLACKLIST:
      continue

    yield d


def load_directory(root, *, drop_suffix=None, schema=None):
  seen = set()

  for path, dirnames, filenames in os.walk(root):
    dirnames[:] = filter_directories(dirnames)

    for fn in filenames:
      if fn.startswith('.'):
        continue

      filepath = os.path.join(path, fn)
      try:
        data = loader.load_file(filepath, schema=schema)
      except loader.NoLoader:
        continue

      key = _key_from_path(root, filepath)
      if (drop_suffix is not None
          and key.endswith('-{}'.format(drop_suffix))):
        key = key[:-len(drop_suffix)-1]

      assert key not in seen
      seen.add(key)

      yield key, data
