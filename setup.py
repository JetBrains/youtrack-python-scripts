from os import path
from setuptools import setup

here = path.abspath(path.dirname(__file__))

# Try to convert markdown readme file to rst format
try:
    import pypandoc
    md_file = path.join(here, 'README.md')
    rst_file = path.join(here, 'README.rst')
    pypandoc.convert_file(source_file=md_file, outputfile=rst_file, to='rst')
except (ImportError, OSError, IOError, RuntimeError):
    pass

# Get the long description from the relevant file
with open(path.join(here, 'README.rst')) as f:
    long_description = f.read()


setup(
    name='youtrack-scripts',
    version='0.1.0',
    packages=['youtrack', 'youtrack.sync'],
    url='https://github.com/JetBrains/youtrack-python-scripts',
    license='Apache 2.0',
    maintainer='Alexander Buturlinov',
    maintainer_email='imboot85@gmail.com',
    description='YouTrack import and utility scripts',
    long_description=long_description,
    install_requires=[
        "youtrack",
        "pyactiveresource",  # for Redmine import script
        "MySQL-python",      # for BugZilla and Mantis import scripts
        "Trac >= 1.0.1",     # for Track import script
        "requests"           # for github import script
    ]
)
