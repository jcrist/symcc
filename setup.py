from setuptools import setup

setup(name='symcc',
        version='0.0',
        description='Symbolic Mathematics Compiler',
        author='Jim Crist',
        install_requires=['sympy>=0.7.5-git'],
        tests_require=['pytest'],
        dependency_links = ['http://github.com/sympy/sympy/tarball/master#egg=sympy-0.7.5-git']
)
