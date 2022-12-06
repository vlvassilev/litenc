from distutils.core import setup

setup(name='litenc',
      version='1.7',
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
