#!/usr/bin/env python

from jira.client import JIRA
from jira.resources import Issue, dict2resource

fake_user = {'self': 'https://domain.com/rest/api/2/user?username=porkchop', 'key': 'porkchop', 'name': 'porkchop', 'emailAddress': 'porkchop@domain.com', 'avatarUrls': {'48x48': 'https://domain.com/secure/useravatar?avatarId=1', '24x24': 'https://domain.com/secure/useravatar?size=small&avatarId=1', '16x16': 'https://domain.com/secure/useravatar?size=xsmall&avatarId=1', '32x32': 'https://domain.com/secure/useravatar?size=medium&avatarId=1'}, 'displayName': 'Chop Pork', 'active': True, 'deleted': False, 'timeZone': 'America/New_York', 'locale': 'en_US', 'groups': {'size': 9, 'items': []}, 'applicationRoles': {'size': 1, 'items': []}, 'expand': 'groups,applicationRoles'}


fake_fields = [
    {'clauseNames': ['cf[1234567]', 'Fixed in Build'],
        'custom': True,
        'id': 'customfield_1234567',
        'name': 'Fixed in Build',
        'navigable': True,
        'orderable': True,
        'schema': {'custom': 'com.atlassian.jira.plugin.system.customfieldtypes:textfield',
                   'customId': 1234567,
                   'type': 'string'},
        'searchable': True},
    {'clauseNames': ['cf[1234568]', 'Score'],
        'custom': True,
        'id': 'customfield_1234568',
        'name': 'Score',
        'navigable': True,
        'orderable': True,
        'schema': {'custom': 'org.jboss.labs.jira.plugin.jboss-custom-field-types-plugin:jbonlynumber',
                   'customId': 1234568,
                   'type': 'number'},
        'searchable': True},
    {'clauseNames': ['cf[1234569]', 'Array Tests'],
        'custom': True,
        'id': 'customfield_1234569',
        'name': 'Array Tests',
        'navigable': True,
        'orderable': True,
        'schema': {'custom': 'com.atlassian.jira.plugin.system.customfieldtypes:multiselect',
                   'customId': 1234569,
                   'items': 'option',
                   'type': 'array'},
        'searchable': True}]


fake_issues = {
    'TEST-1': {'expand': 'renderedFields,names,schema,operations,editmeta,changelog,versionedRepresentations',
               'fields': {'aggregateprogress': {'progress': 0, 'total': 0},
                          'aggregatetimeestimate': None,
                          'aggregatetimeoriginalestimate': None,
                          'aggregatetimespent': None,
                          'archivedby': None,
                          'archiveddate': None,
                          'assignee': {   'active': True,
                                  'displayName': 'Rory Obert',
                                  'emailAddress': 'robert@pie.com',
                                  'key': 'rory',
                                  'name': 'rory',
                                  'self': 'https://domain.com/rest/api/2/user?username=rory',
                                  'timeZone': 'America/New_York'},
                          'attachment': [],
                          'comment': [],
                          'components': [],
                          'created': '2023-08-03T10:28:48.366+0000',
                          'customfield_1234567': None,
                          'customfield_1234568': None,
                          'customfield_1234569': None,
                          'description': 'Test Description 1',
                          'duedate': '2024-01-30',
                          'environment': None,
                          'fixVersions': [],
                          'issuelinks': [],
                          'issuetype': {'avatarId': 13263,
                                        'description': 'A bug',
                                        'id': '1',
                                        'name': 'Bug',
                                        'self': 'https://domain.com/rest/api/2/issuetype/1',
                                        'subtask': False},
                          'labels': ['label1', 'label2'],
                          'lastViewed': '2023-11-22T15:51:50.281+0000',
                   'priority': {'id': '10200',
                                 'name': 'Normal',
                                 'self': 'https://domain.com/rest/api/2/priority/10200'},
                   'progress': {'progress': 0, 'total': 0},
                   'project': {'id': '1234',
                               'key': 'TEST',
                               'name': 'Test Project',
                               'projectCategory': {'description': 'Test Projects',
                                                   'id': '1073',
                                                   'name': 'Projecto',
                                                   'self': 'https://domain.com/rest/api/2/projectCategory/1073'},
                               'projectTypeKey': 'software',
                               'self': 'https://domain.com/rest/api/2/project/1234'},
                   'reporter': {'active': True,
                                'displayName': 'Pork Chop',
                                'emailAddress': 'pchop@domai.com',
                                'key': 'JIRAUSER1',
                                'name': 'pchop@domain.com',
                                'self': 'https://domain.com/rest/api/2/user?username=pchop%40domain.com',
                                'timeZone': 'Asia/Kolkata'},
                   'resolution': None,
                   'resolutiondate': None,
                   'security': None,
                   'status': {'description': 'Initial creation status. ',
                              'id': '10',
                              'name': 'New',
                              'self': 'https://domain.com/rest/api/2/status/10016',
                              'statusCategory': {'colorName': 'default',
                                                 'id': 2,
                                                 'key': 'new',
                                                 'name': 'To Do',
                                                 'self': 'https://domain.com/rest/api/2/statuscategory/2'}},
                   'subtasks': [],
                   'summary': 'Test 1',
                   'timeestimate': None,
                   'timeoriginalestimate': None,
                   'timespent': None,
                   'timetracking': {},
                   'updated': '2023-11-30T15:06:39.875+0000',
                   'versions': [{'archived': False,
                                 'description': '',
                                 'id': '6',
                                 'name': 'version-6',
                                 'released': False,
                                 'self': 'https://domain.com/rest/api/2/version/6'}],
                   'votes': {'hasVoted': False,
                             'self': 'https://domain.com/rest/api/2/issue/TEST-1/votes',
                             'votes': 0},
                   'watches': {'isWatching': False,
                               'self': 'https://domain.com/rest/api/2/issue/TEST-1/watchers',
                               'watchCount': 2},
                   'worklog': {'maxResults': 20,
                               'startAt': 0,
                               'total': 0,
                               'worklogs': []},
                   'workratio': -1},
               'id': '1000001',
               'key': 'TEST-1',
               'self': 'https://domain.com/rest/api/2/issue/1000001'},

    'TEST-2': {'expand': 'renderedFields,names,schema,operations,editmeta,changelog,versionedRepresentations',
               'fields': {'aggregateprogress': {'progress': 0, 'total': 0},
                          'aggregatetimeestimate': None,
                          'aggregatetimeoriginalestimate': None,
                          'aggregatetimespent': None,
                          'archivedby': None,
                          'archiveddate': None,
                          'assignee': None,
                          'attachment': [],
                          'comment': [],
                          'components': ['porkchop'],
                          'created': '2023-08-03T10:28:48.366+0000',
                          'customfield_1234567': 'build-2',
                          'customfield_1234568': None,
                          'customfield_1234569': None,
                          'description': 'Test Description 2',
                          'duedate': '2024-01-30',
                          'environment': None,
                          'fixVersions': [],
                          'issuelinks': [],
                          'issuetype': {'avatarId': 13263,
                                        'description': 'A bug',
                                        'id': '1',
                                        'name': 'Bug',
                                        'self': 'https://domain.com/rest/api/2/issuetype/1',
                                        'subtask': False},
                          'labels': ['label2'],
                          'lastViewed': '2023-11-22T15:51:50.281+0000',
                          'priority': {
                   'id': '10200',
                   'name': 'Normal',
                   'self': 'https://domain.com/rest/api/2/priority/10200'},
                   'progress': {'progress': 0, 'total': 0},
                   'project': {'id': '1234',
                               'key': 'TEST',
                               'name': 'Test Project',
                               'projectCategory': {'description': 'Test Projects',
                                                   'id': '1073',
                                                   'name': 'Projecto',
                                                   'self': 'https://domain.com/rest/api/2/projectCategory/1073'},
                               'projectTypeKey': 'software',
                               'self': 'https://domain.com/rest/api/2/project/1234'},
                   'reporter': {'active': True,
                                'displayName': 'Pork Chop',
                                'emailAddress': 'pchop@domai.com',
                                'key': 'JIRAUSER1',
                                'name': 'pchop@domain.com',
                                'self': 'https://domain.com/rest/api/2/user?username=pchop%40domain.com',
                                'timeZone': 'Asia/Kolkata'},
                   'resolution': None,
                   'resolutiondate': None,
                   'security': None,
                   'status': {'description': 'Initial creation status. ',
                              'id': '10',
                              'name': 'New',
                              'self': 'https://domain.com/rest/api/2/status/10016',
                              'statusCategory': {'colorName': 'default',
                                                 'id': 2,
                                                 'key': 'new',
                                                 'name': 'To Do',
                                                 'self': 'https://domain.com/rest/api/2/statuscategory/2'}},
                   'subtasks': [],
                   'summary': 'Test 1',
                   'timeestimate': None,
                   'timeoriginalestimate': None,
                   'timespent': None,
                   'timetracking': {},
                   'updated': '2023-11-30T15:06:39.875+0000',
                   'versions': [{'archived': False,
                                 'description': '',
                                 'id': '6',
                                 'name': 'version-6',
                                 'released': False,
                                 'self': 'https://domain.com/rest/api/2/version/6'}],
                   'votes': {'hasVoted': False,
                             'self': 'https://domain.com/rest/api/2/issue/TEST-1/votes',
                             'votes': 0},
                   'watches': {'isWatching': False,
                               'self': 'https://domain.com/rest/api/2/issue/TEST-1/watchers',
                               'watchCount': 2},
                   'worklog': {'maxResults': 20,
                               'startAt': 0,
                               'total': 0,
                               'worklogs': []},
                   'workratio': -1},
               'id': '1000002',
               'key': 'TEST-2',
               'self': 'https://domain.com/rest/api/2/issue/1000002'}
}


class fake_jira_session():
    def get(self, url):
        pass

    def post(self, url, data=None):
        pass

    def delete(self, url):
        pass

    def close(self):
        pass


class fake_jira(JIRA):
    def __init__(self, **kwargs):
        self._fields_cache_value = {}
        pass

    def _get_url(self, url_fragment):
        pass

    def _get_json(self, url_fragment):
        pass

    def add_simple_link(self, issue, link):
        pass

    def search_users(self, username):
        pass

    def fields(self):
        return fake_fields

    def search_issues(self, seach_query, startAt=None, maxResults=None):
        pass

    def create_issue(self, **args):
        pass

    def issue(self, issue_key):
        if issue_key.upper() not in fake_issues:
            return None
        ret = Issue(None, None)
        ret.raw = fake_issues[issue_key]
        dict2resource(fake_issues[issue_key], ret)
        return ret

    def issue_link_types(self):
        pass

    def create_issue_link(self, text, left_key, right_key):
        pass

    def remote_links(self, issue_key):
        pass

    def remote_link(self, left_key, right_key):
        pass

    def delete_issue_link(self, left_key, right_key):
        pass

    def project(self, project_key):
        pass

    def myself(self):
        return fake_user

    _session = fake_jira_session()
