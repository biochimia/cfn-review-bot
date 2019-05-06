{% for target in results %}
{%  if not loop.first %}
<br>

{%  endif %}
### :dart: `{{ target.name }}` | `{{ target.account }}` |{{ ':{}: '|format_if(REGION_TO_EMOJI[target.region]) }}`{{ target.region }}` [[login](https://{{ target.account }}.signin.aws.amazon.com/console)]

**Stacks:** {{ target.results.stack_summary }}
{%  if target.results.orphaned_stacks %}
**Orphaned Stacks:** `{{ '`, `'.join(target.results.orphaned_stacks) }}`
{%  endif %}

{%  for change_set in target.results.change_sets %}
<details>
<summary>{{ ':sparkles:' if change_set.type == change_set.type.CREATE }}<code>{{ change_set.detail.StackName }}</code> [<a href="https://{{ target.region }}.console.aws.amazon.com/cloudformation/home?region={{ target.region }}#/stacks/{{ change_set.stack }}/changesets/{{ change_set.id}}">change set</a>]</summary>

{%    if change_set.detail.Status != 'CREATE_COMPLETE' %}
#### Status: `{{ change_set.detail.Status }}`{{ ' ({})'|format_if(change_set.detail.StatusReason) }}
{%    endif %}
{%    if change_set.detail.Parameters|length > 1 %}
#### Parameters

|Name|Value|
|:-|:-|
{%      for p in change_set.detail.Parameters if not p.ParameterKey == METADATA_PARAMETER %}
|`{{ p.ParameterKey }}`|{{ p.ParameterValue|md_code }}|
{%      endfor %}

{%    endif %}
{%    if change_set.detail.Capabilities %}
#### Capabilities: `{{ '` | `'.join(change_set.detail.Capabilities) }}`

{%    endif %}
{%    if change_set.detail.Changes %}
#### Changes

|Resource|Resource Type|Action|Replace?|Modification Scope|Change Source|
|:-|:-|:-|:-|:-|:-|
{%      for change in change_set.detail.Changes %}
|`{{ change.ResourceChange.LogicalResourceId }}`|`{{ change.ResourceChange.ResourceType }}`|`{{ change.ResourceChange.Action }}`|{{ '`{}`'|format_if(change.ResourceChange.Replacement) }}|{{ '<br>'.join(change.ResourceChange.Scopes) }}|
{%-       for detail in change.Details %}
{{ '<br>' if not loop.first }}`{{ detail.ChangeSource }}`{{ ' (`{}`)'|format_if(detail.CausingEntity) }}{{ ' **`[{}]`**'|format_if(detail.Evaluation) }}
{%-       endfor %}|
{%      endfor %}

{%    endif %}
{%    if change_set.detail.Tags %}
#### Tags

|Key|Value|
|:-|:-|
{%      for t in change_set.detail.Tags %}
|`{{ t.Key }}`|{{ t.Value|md_code }}|
{%      endfor %}

{%    endif %}
</details>
{%  endfor %}

{% endfor %}
---
_CloudFormation change set summary generated by [`cfn-review-bot`](https://github.com/biochimia/cfn-review-bot)_