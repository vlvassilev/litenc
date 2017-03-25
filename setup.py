from distutils.core import setup

setup(name='netconf',
      version='0.0.1',
      description="Python implementation of netconf-io",
      author="Vladimir Vassilev",
      author_email="vladimir@transpacket.com",
      url="http://google.com",
      packages=["netconf", "netconf_lxml"],
      license="Apache License 2.0",
      platforms=["Posix; OS X; Windows"],
      #classifiers=[]
      scripts=['scripts/netconf_get_config', 'scripts/netconf_get_leaf', 'scripts/netconf_load_config']
      )
