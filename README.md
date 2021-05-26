[![official JetBrains project](http://jb.gg/badges/official-flat-square.svg)](https://confluence.jetbrains.com/display/ALL/JetBrains+on+GitHub)

# Before you begin
YouTrack provides built-in imports from Jira, GitHub, Mantis, and Redmine. It also lets you set up a migration from one YouTrack instance to another. If you want to import issues from one of these sources, we strongly encourage you to use the built-in import feature instead of the scripts in this repository.

# YouTrack Python Scripts
This repository contains a collection of command-line tools for interacting with the YouTrack REST API client library for Python. At present, the package only contains scripts for importing issues from other issue trackers. The scripts reference the YouTrack REST API client library for Python that is published in a [separate repository](https://github.com/JetBrains/youtrack-rest-python-library).

## Compatibility
These scripts are compatible with Python 2.7+. Python 3 releases are not supported.

The scripts are compatible with YouTrack Standalone versions 5.x and higher as well as the current version of YouTrack InCloud. The REST API is enabled by default in all YouTrack installations.

## Getting Started
This package has been published to PyPI and can be installed with pip.
`pip install youtrack-scripts`

The YouTrack REST API client library for Python is installed automatically as a dependency.

Once installed, you can build your mapping files and use the import scripts to migrate issues from other issue trackers to YouTrack. Specific instructions vary by import source.
- For import to an installation on your own server, please refer to the documentation for [YouTrack Standalone](https://www.jetbrains.com/help/youtrack/standalone/Migrating-to-YouTrack.html).
- For import to an instance that is hosted in the cloud by JetBrains, please refer to the documentation for [YouTrack InCloud](https://www.jetbrains.com/help/youtrack/incloud/Migrating-to-YouTrack.html).

## Import Scripts
This package includes dedicated scripts for importing issues from Bugzilla, FogBugz, Mantis Bug Tracker (MantisBT), Redmine, and Trac.
- Import from Jira to YouTrack is supported as a standard integration that is configured directly in YouTrack.
- For other issue trackers, it may be possible to import issues from a CSV file.

This package also includes scripts for importing single issues or entire projects from one YouTrack installation to another.

## YouTrack Support
Your feedback is always appreciated.
- To report bugs and request updates, please [create an issue](http://youtrack.jetbrains.com/issues/JT#newissue=yes).
- If you experience problems with an import script, please [submit a support request](https://youtrack-support.jetbrains.com/hc/en-us).
