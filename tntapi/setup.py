import sys

if sys.version_info < (3,10):
    from distutils.core import setup,Extension
else:
    from setuptools import setup,Extension

setup(name='tntapi',
      version='1.8',
      description="Transactional Network Tools API",
      author="Vladimir Vassilev",
      author_email="vladimir@lightside-instruments.com",
      url="https://github.com/vlvassilev/litenc",
      packages=["tntapi"],
      scripts=['example/diff-net', 'example/set-net', 'example/get-net', 'example/run-net-transactions-sched', 'example/traffic-graphic'],
      license="Apache License 2.0",
      platforms=["Posix; OS X; Windows"],
      )
