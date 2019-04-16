#!/usr/bin/env python
# -*- coding: utf-8 -*-


from setuptools import setup, find_packages

setup(name='lvdf',
      description='lvdf',
      version='0.1',
      author='Hernan Grecco',
      author_email='hernan.grecco@gmail.com',
      license='MIT License',
      install_requires=['flask', 'delegator.py'],
      classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        ],
      packages=find_packages(),
      include_package_data=True,
      platforms="Linux, Windows, Mac",
      use_2to3=False,
      zip_safe=False)
