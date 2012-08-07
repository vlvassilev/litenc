import sys
from netconf import netconf

if sys.version_info < (2, 6):
    raise RuntimeError('You need Python 2.6+ for this module.')

__all__ = [
    'netconf'
]
