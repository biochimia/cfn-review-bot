import schema

from . import aws
from . import util


DEFAULT_ROLE_NAME = 'CfnReviewBot'


SingleTargetSchema = schema.Schema({
  'account-id': aws.AccountId,
  schema.Optional('region'): util.OneOrMany(aws.Region),
  schema.Optional('role-name'): str,
  schema.Optional('tag', default={}): {str: str},
})

TargetConfigSchema = schema.Schema({
  schema.Optional('default', default=[]): util.OneOrMany(str),
  schema.Optional('region', default=[]): util.OneOrMany(aws.Region),
  schema.Optional('role-name', default=DEFAULT_ROLE_NAME): str,
  schema.Optional('tag', default={}): {str: str},
  schema.Optional('target', default={}): {
    str: util.OneOrMany(SingleTargetSchema),
  },
  schema.Optional('stack-root', default='./stack'): str,
  schema.Optional('template-root', default='./template'): str,
})
