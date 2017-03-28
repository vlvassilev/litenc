import sys
from litenc import litenc

if sys.version_info < (2, 6):
    raise RuntimeError('You need Python 2.6+ for this module.')

__all__ = [
    'litenc'
]
