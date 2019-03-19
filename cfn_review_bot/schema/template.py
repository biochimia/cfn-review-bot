import schema

from . import util


TemplateSchema = schema.Schema({
  schema.Optional('AWSTemplateFormatVersion'): str,
  schema.Optional('Description'): str,
  schema.Optional('Metadata'): util.Any,
  schema.Optional('Parameters'): {str: dict},
  schema.Optional('Mappings'): {str: dict},
  schema.Optional('Conditions'): {str: util.Any},
  schema.Optional('Transform'): util.Any,
  'Resources': {str: dict},
  schema.Optional('Outputs'): {str: dict},
})
