'''
Schema for configuring a CloudFormation stack and its deployment targets.
'''

import schema

from . import aws, util


StackTarget = schema.Or(
  str,
  {
    'name': str,
    # overrides regions defined in the target
    'region': util.OneOrMany(str),
  },
)

StackSchema = schema.Schema({
  'template': util.OneOrMany(str),
  schema.Optional('name'): str,
  schema.Optional('target'): util.OneOrMany(StackTarget),

  # overrides regions defined in the target
  schema.Optional('region'): util.OneOrMany(aws.Region),

  schema.Optional('capability', default=[]): util.OneOrMany(str),
  schema.Optional('parameter', default={}): {str: str},
  schema.Optional('tag', default={}): {str: str},
}, name='Stack Description')
