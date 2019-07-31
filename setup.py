from setuptools import setup

setup(name='qctools',
      version='0.1',
      description='Extension module for measuring with qcodes',
      url='',
      author='KnightForest',
      author_email='joostridderbos@hotmail.com',
      license='MIT',
      packages=['qctools'],
      install_requires=[
          'qcodes',
      ],
      zip_safe=False)