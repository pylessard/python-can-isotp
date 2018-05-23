from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
  name = 'can-isotp',
  packages = ['isotp'],
  version = '0.4',
  description = 'Wrapper for Python 3.7+ simplifying the usage of Oliver Hartkopp\'s Linux kernel module enabling ISO-15765 sockets',
  long_description=long_description,
  author = 'Pier-Yves Lessard',
  author_email = 'py.lessard@gmail.com',
  license='MIT',
  url = 'https://github.com/pylessard/python-can-isotp',
  download_url = 'https://github.com/pylessard/python-can-isotp/archive/v0.4.tar.gz',
  keywords = ['isotp', 'can', 'iso-15765', '15765', 'iso15765'], 
  python_requires='>=3.7',
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