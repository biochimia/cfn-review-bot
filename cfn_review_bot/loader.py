import io
import json
import os.path
import yaml

from .error import Error


class NoLoader(Error):
  def __str__(self):
    return 'unsupported file format: unable to load \'{}\''.format(self.args[0])


class LoaderError(Error):
  pass


class _Dict(dict): pass
class _List(list): pass
class _Str(str): pass
class _Int(int): pass


ATTRIBUTABLE_TYPE = {
  dict: _Dict,
  list: _List,
  str: _Str,
  int: _Int,
}


class OpaqueTagValue:
  def __init__(self, tag, value):
    self.tag = tag
    self.value = value


class OpaqueTagMapping(OpaqueTagValue):
  pass


class OpaqueTagScalar(OpaqueTagValue):
  pass


class OpaqueTagSequence(OpaqueTagValue):
  pass


class OpaqueTagLoader(yaml.loader.SafeLoader):
  def construct_opaque_tag_value(self, node):
    if isinstance(node, yaml.nodes.MappingNode):
      return OpaqueTagMapping(node.tag, self.construct_mapping(node))

    if isinstance(node, yaml.nodes.ScalarNode):
      return OpaqueTagScalar(node.tag, self.construct_scalar(node))

    if isinstance(node, yaml.nodes.SequenceNode):
      return OpaqueTagSequence(node.tag, self.construct_sequence(node))

    return self.construct_undefined(node)


OpaqueTagLoader.add_constructor(
  None, OpaqueTagLoader.construct_opaque_tag_value)


class OpaqueTagDumper(yaml.dumper.SafeDumper):
  def represent_opaque_tag_mapping(self, data):
    return self.represent_mapping(data.tag, data.value)

  def represent_opaque_tag_scalar(self, data):
    return self.represent_scalar(data.tag, data.value)

  def represent_opaque_tag_sequence(self, data):
    return self.represent_sequence(data.tag, data.value)


OpaqueTagDumper.add_representer(
  OpaqueTagMapping, OpaqueTagDumper.represent_opaque_tag_mapping)
OpaqueTagDumper.add_representer(
  OpaqueTagScalar, OpaqueTagDumper.represent_opaque_tag_scalar)
OpaqueTagDumper.add_representer(
  OpaqueTagSequence, OpaqueTagDumper.represent_opaque_tag_sequence)

OpaqueTagDumper.add_representer(_Dict, OpaqueTagDumper.represent_dict)
OpaqueTagDumper.add_representer(_List, OpaqueTagDumper.represent_list)
OpaqueTagDumper.add_representer(_Str, OpaqueTagDumper.represent_str)
OpaqueTagDumper.add_representer(_Int, OpaqueTagDumper.represent_int)


def load_json(stream):
  return json.load(stream)


def load_yaml(stream):
  try:
    return yaml.load(stream, Loader=OpaqueTagLoader)
  except yaml.error.YAMLError as err:
    raise LoaderError(err) from None


def dump_yaml(data, stream):
  return yaml.dump(
    data, stream, Dumper=OpaqueTagDumper, indent=2, width=80,
    default_flow_style=False)


LOADER_FOR_EXT = {
  'json': load_json,
  'yaml': load_yaml,
  'yml': load_yaml,
}


def load_file(filename, *, schema=None):
  ext = os.path.splitext(filename)[1][1:].lower()
  try:
    load = LOADER_FOR_EXT[ext]
  except KeyError:
    raise NoLoader(filename) from None

  filename = os.path.abspath(filename)
  with open(filename) as stream:
    raw_data = stream.read()

  data = load(io.StringIO(raw_data))
  if schema is not None:
    data = schema.validate(data)

  try:
    cls = ATTRIBUTABLE_TYPE[type(data)]
  except KeyError:
    return data

  tagged_data = cls(data)
  tagged_data.__file__ = filename
  tagged_data.__raw__ = raw_data

  return tagged_data
