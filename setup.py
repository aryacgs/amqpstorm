from setuptools import setup


long_description = """
See https://github.com/eandersson/amqp-storm for more information.
"""

setup(name='AMQP-Storm',
      version='1.0.3',
      description='Thread-safe Python AMQP Client Library based on pamqp.',
      long_description=long_description,
      author='Erik Olof Gunnar Andersson',
      author_email = 'me@eandersson.net',
      include_package_data=True,
      packages=['amqpstorm'],
      license = 'MIT License',
      url = 'http://github.com/eandersson/amqp-storm',
      install_requires=['pamqp'],
      package_data={'': ['README.md', 'LICENSE']},
      zip_safe=False,
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: Implementation :: CPython',
          'Topic :: Communications',
          'Topic :: Internet',
          'Topic :: Software Development :: Libraries',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: System :: Networking'])