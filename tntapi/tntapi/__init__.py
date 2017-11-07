import sys
from tntapi import *
from tntapi_netconf_session_litenc import *
from tntapi_strip_namespaces import *

if sys.version_info < (2, 6):
    raise RuntimeError('You need Python 2.6+ for this module.')

__all__ = [
    'tntapi'
]
