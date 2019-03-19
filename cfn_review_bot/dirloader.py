import os
import os.path

from . import loader


DIRECTORY_BLACKLIST = [
  'node_modules',
  'vendor',
]


def _key_from_path(root, path):
  proto_key = os.path.splitext(
    os.path.relpath(path, start=root))[0]

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


def filter_directories(dirnames):
  for d in dirnames:
    if d.startswith('.'):
      continue
    if d in DIRECTORY_BLACKLIST:
      continue

    yield d


def load_directory(root, *, schema=None):
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

      assert key not in seen
      seen.add(key)

      yield key, data
