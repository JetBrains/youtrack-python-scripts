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

# Get version from file
with open(path.join(here, 'version')) as f:
    version = f.read().strip()


setup(
    name='youtrack-scripts',
    version=version,
    python_requires='>=2.6, <3',
    packages=['youtrackutils',
              'youtrackutils.bugzilla',
              'youtrackutils.csvClient',
              'youtrackutils.fbugz',
              'youtrackutils.mantis',
              'youtrackutils.redmine',
              'youtrackutils.tracLib',
              'youtrackutils.utils',
              'youtrackutils.zendesk'],
    url='https://github.com/JetBrains/youtrack-python-scripts',
    license='Apache 2.0',
    maintainer='Alexander Buturlinov',
    maintainer_email='imboot85@gmail.com',
    description='YouTrack import and utility scripts',
    long_description=long_description,
    entry_points={
        'console_scripts': [
            'bugzilla2youtrack=youtrackutils.bugzilla2youtrack:main',
            'csv2youtrack=youtrackutils.csv2youtrack:main',
            'fb2youtrack=youtrackutils.fb2youtrack:main',
            'github2youtrack=youtrackutils.github2youtrack:main',
            'mantis2youtrack=youtrackutils.mantis2youtrack:main',
            'redmine2youtrack=youtrackutils.redmine2youtrack:main',
            'trac2youtrack=youtrackutils.trac2youtrack:main',
            'youtrack2youtrack=youtrackutils.youtrack2youtrack:main',
            'zendesk2youtrack=youtrackutils.zendesk2youtrack:main',
            'yt-move-issue=youtrackutils.moveIssue:main'
        ],
    },
    install_requires=[
        "python-dateutil",
        "youtrack >= 0.1.8",
        "pyactiveresource",        # for Redmine import script
        # Commented out because the package installation can fail in case
        # if mysql is not installed on local machine
        # "MySQL-python",            # for BugZilla and Mantis import scripts
        "BeautifulSoup >= 3.2.0",  # for FogBugz import script
        "Trac >= 1.0.1",           # for Track import script
        "requests"                 # for github import script
    ]
)
