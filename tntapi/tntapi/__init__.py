import sys
from tntapi.tntapi import *
from tntapi.tntapi_netconf_session_litenc import *
from tntapi.tntapi_strip_namespaces import *
from tntapi.tntapi_print_state import *

if sys.version_info < (2, 6):
    raise RuntimeError('You need Python 2.6+ for this module.')

__all__ = [
    'tntapi'
]
