from distutils.core import setup
setup(
  name = 'can-isotp',
  packages = ['can-isotp'],
  version = '0.1',
  description = 'Wrapper for Python 3.7+ simplifying the usage of Oliver Herktopp\'s Linux kernel module enabling ISO-15765 sockets',
  author = 'Pier-Yves Lessard',
  author_email = 'py.lessard@gmail.com',
  url = 'https://github.com/pylessard/python-can-isotp',
  download_url = 'https://github.com/pylessard/python-can-isotp/archive/v0.1.tar.gz',
  keywords = ['isotp', 'can', 'iso-15765', '15765', 'iso15765'], 
  classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Operating System :: POSIX :: Linux",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
        ],
)