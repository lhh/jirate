#!/usr/bin/python3

__version__ = '0.8.5'

from jirate.jboard import Jirate, JiraProject

# Extra high level
from jirate.jira_cli import get_jira_project

__all__ = [Jirate, JiraProject, get_jira_project]
