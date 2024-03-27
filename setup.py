from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='can-isotp',
    packages=find_packages(where='.', exclude=['test', 'test.*'], include=['isotp', "isotp.*"]),
    package_data={
        'isotp' : ['py.typed']
    },
    version='2.0.4',
    extras_require={
        'test': ['mypy', 'coverage', 'python-can'],
        'dev': ['mypy', 'ipdb', 'autopep8', 'coverage', 'python-can']
    },
    description='Module enabling the IsoTP protocol defined by ISO-15765',
    long_description=long_description,
    author='Pier-Yves Lessard',
    author_email='py.lessard@gmail.com',
    license='MIT',
    url='https://github.com/pylessard/python-can-isotp',
    download_url='https://github.com/pylessard/python-can-isotp/archive/v2.0.4.tar.gz',
    keywords=['isotp', 'can', 'iso-15765', '15765', 'iso15765'],
    python_requires='>=3.7',
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Operating System :: POSIX :: Linux",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
    ],
)
