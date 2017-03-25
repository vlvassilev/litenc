import sys
from netconf_lxml import netconf_lxml

if sys.version_info < (2, 6):
    raise RuntimeError('You need Python 2.6+ for this module.')

__all__ = [
    'netconf_lxml'
]
