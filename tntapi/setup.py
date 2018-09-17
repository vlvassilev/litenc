from distutils.core import setup

setup(name='tntapi',
      version='1.4',
      description="Transactional Network Tools API",
      author="Vladimir Vassilev",
      author_email="vladimir@transpacket.com",
      url="https://github.com/vlvassilev/litenc",
      packages=["tntapi"],
      scripts=['example/diff-net', 'example/set-net', 'example/get-net', 'example/run-net-transactions-sched', 'example/traffic-graphic'],
      license="Apache License 2.0",
      platforms=["Posix; OS X; Windows"],
      )
