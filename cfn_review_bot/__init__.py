from . import _version


__version_info__ = _version._get_version_info()
__version__ = __version_info__.package_version
