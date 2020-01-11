import hashlib
import json

from .loader import OpaqueTagValue


def _canonical_json_handler(data):
    if isinstance(data, OpaqueTagValue):
        return {f'Fn::{data.tag[1:]}': data.value}
    raise TypeError(f'Object of type {type(data)} is not JSON serializable')


def canonical_hash(data):
    canonical_content = json.dumps(
        data,
        allow_nan=False,
        check_circular=True,
        default=_canonical_json_handler,
        ensure_ascii=True,
        separators=(',', ':'),
        sort_keys=True,
    ).encode('utf-8')

    hsh = hashlib.sha256(canonical_content)
    return f'sha256-{hsh.hexdigest()}'
