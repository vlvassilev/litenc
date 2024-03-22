import sys

if sys.version_info < (3,10):
    from distutils.core import setup,Extension
else:
    from setuptools import setup,Extension

setup(name='litenc',
      version='1.8',
      description="Lite NETCONF session framer",
      author="Vladimir Vassilev",
      author_email="vladimir@lightside-instruments.com",
      url="https://github.com/vlvassilev/litenc",
      packages=["litenc", "litenc_lxml"],
      license="Apache License 2.0",
      platforms=["Posix; OS X; Windows"],
      #classifiers=[]
      scripts=['scripts/ncget']
      )
