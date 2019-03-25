import schema

from . import util


StackSchema = schema.Schema({
  'template': util.OneOrMany(str),
  schema.Optional('name'): str,
  schema.Optional('target'): util.OneOrMany(str),
  schema.Optional('capability', default=[]): util.OneOrMany(str),
  schema.Optional('parameter', default={}): {str: str},
  schema.Optional('tag', default={}): {str: str},
})
