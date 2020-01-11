import jinja2

from . import cfn


ENVIRONMENT = jinja2.Environment(
    loader=jinja2.PackageLoader('cfn_review_bot'),
    trim_blocks=True,
    lstrip_blocks=True,
)

ENVIRONMENT.globals.update(
    METADATA_PARAMETER=cfn.CFN_METADATA_PARAMETER,
    REGION_TO_EMOJI={
        'ap-northeast-1': 'jp',
        'ap-northeast-2': 'kr',
        'ap-south-1': 'india',
        'ap-southeast-1': 'singapore',
        'ap-southeast-2': 'australia',
        'ca-central-1': 'canada',
        'eu-central-1': 'de',
        'eu-north-1': 'sweden',
        'eu-west-1': 'ireland',
        'eu-west-2': 'uk',
        'eu-west-3': 'fr',
        'sa-east-1': 'brazil',
        'us-east-1': 'us',
        'us-east-2': 'us',
        'us-west-1': 'us',
        'us-west-2': 'us',
    },
)


def _md_code(text: str):
    ticks = '`'
    padding = ''

    if text.startswith('`'):
        padding = ' '
    while ticks in text:
        ticks += '`'
    return ''.join((ticks, padding, text, padding, ticks))


def _md_escape(text: str):
    return text.translate({
        # Escape Markdown
        '\\': '\\\\',
        '*': '\\*',
        '_': '\\_',
        '`': '\\`',
        '|': '\\|',

        # Escape HTML
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',

        # Escape Newlines
        '\n': '<br>',
    })


def _format_if(fmt, cond, *args, **kwargs):
    if cond:
        return fmt.format(cond, *args, **kwargs)
    return ''


ENVIRONMENT.filters.update({
    'md_code': _md_code,
    'md_escape': _md_escape,
    'format_if': _format_if,
})


def summary(targets):
    tmpl = ENVIRONMENT.get_template('summary.md')
    return tmpl.render(targets=targets)
