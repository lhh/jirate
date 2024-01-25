#!/usr/bin/env python
# Copyright (c) 2012, Fog Creek Software, Inc.
# Copyright (c) 2016-2018, Red Hat, Inc.
#   License: 2-clause BSD; see LICENSE.txt for details
import setuptools
import re

from textwrap import dedent
from jirate import __version__


def requires(prefix=''):
    """Retrieve requirements from requirements.txt
    """
    try:
        reqs = map(str.strip, open(prefix + 'requirements.txt').readlines())
        return [req for req in reqs if not re.match(r'\W', req)]
    except Exception:
        pass
    return []


setuptools.setup(
    name='jirate',
    version=__version__,
    install_requires=requires(),
    license='BSD',
    long_description=dedent("""\
        Python JIRA & Trello CLI
        --------------------------
        This Python CLI is a high-level wrapper around the JIRA and Trollo modules.

        Getting Started:
        ----------------
        To use the CLI, install the package either by downloading the source and running

          $ pip install -r requirements.txt
          $ pip install .

        or by using pip

          $ pip install jirate

        Documentation:
        --------------
        You can find documentation for the Python API at:

            http://pypi.org/project/jira/
            http://pypi.org/project/trollo/

        Documentation for the JIRA API is at:

            https://docs.atlassian.com/software/jira/docs/api/REST/latest/

        Documentation for the Trello API at:

            https://developers.trello.com/reference/

        """),
    author='Red Hat',
    author_email='lhh@redhat.com',
    maintainer='Lon Hohberger',
    maintainer_email='lon@metamorphism.com',
    packages=['jirate', 'jirate.schemas'],
    package_data={'jirate.schemas': ['jirate/schemas/*']},
    include_package_data=True,
    url='http://github.com/lhh/jirate',
    data_files=[("", ["LICENSE.txt"])],
    entry_points={
        'console_scripts': ['trolly = jirate.cli:main',
                            'jirate = jirate.jira_cli:main']},
    classifiers=['Development Status :: 4 - Beta',
                 'Intended Audience :: Developers',
                 'Natural Language :: English',
                 'Operating System :: MacOS :: MacOS X',
                 'Operating System :: Microsoft :: Windows',
                 'Operating System :: POSIX',
                 'Operating System :: POSIX :: BSD',
                 'Operating System :: POSIX :: Linux',
                 'Programming Language :: Python',
                 'Topic :: Internet :: WWW/HTTP',
                 'Topic :: Software Development',
                 'Topic :: Software Development :: Libraries',
                 'Topic :: Software Development :: Libraries :: Python Modules',
                 'Topic :: Utilities'],
)
