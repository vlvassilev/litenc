from distutils.core import setup

setup(name='litenc',
      version='0.0.1',
      description="NETCONF session framer",
      author="Vladimir Vassilev",
      author_email="vladimir@transpacket.com",
      url="https://github.com/vlvassilev/litenc",
      packages=["litenc", "litenc_lxml"],
      license="Apache License 2.0",
      platforms=["Posix; OS X; Windows"],
      #classifiers=[]
      scripts=['scripts/netconf_get_config', 'scripts/netconf_get_leaf', 'scripts/netconf_load_config']
      )
