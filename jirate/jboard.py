#!/usr/bin/python3

import copy
import os
import re
import sys
import types

from toolchest.strutil import list_or_splitstr

from jira import JIRA, JIRAError
from jira.utils import json_loads as _json_loads
from jira.resources import Issue, User

from jirate.decor import nym
from jirate.jira_input import transmogrify_input


# lhh - seems python 3.12.4 doesn't let us simply replace
# this, so do it the hard way and detect being run under
# pytest
_test_ = False
if "pytest" in sys.modules:
    _test_ = True


def json_loads(val):
    if _test_:
        return val
    return _json_loads(val)


def _user_fix(obj, *args):
    # JIRA.user() doesn't search by key
    try:
        ret = JIRA.user(obj, *args)
        return ret
    except JIRAError:
        # There's no check by key; try it
        pass

    return _user_by_key(obj, *args)


def _user_by_key(obj, *args):
    key = args[0]
    data = {}
    if len(args) > 1:
        data = {'expand': args[1]}
    user = User(obj._options, obj._session, _query_param='key')
    user.find(key, params=data)
    return user


def _resolve_field(obj, field_name):
    return obj._jirate.field(obj, field_name)


# Intelligent field update for Issue
def _update_field(issue, field_name_human, value_human, operation='set', fields=None):
    if not fields:
        # TODO use native python-jira issue.fields instead of raw json
        # (Except operations are not captured, which we need)
        fields = issue._jirate.fields(issue.key)
    if not isinstance(value_human, list):
        value_human = str(value_human)

    # TODO multi-field sets?
    field_args = {field_name_human: value_human}
    output_args = transmogrify_input(fields, **field_args)

    if not output_args:
        raise AttributeError(f'No field like \'{field_name_human}\' in {issue.key}')

    # Set up for the rest
    field_ids = [key for key in output_args.keys()]
    field_id = field_ids[0]
    field = fields[field_id]
    send_val = output_args[field_id]

    ops = field['operations']
    if operation not in ops:
        raise ValueError(f'Cannot perform \'{operation}\' on \'{field_name_human}\' of {issue.key}; try: {ops}')

    # Add and remove use a different format than 'set'.
    # There's also 'modify', but ... that one's even more complicated.
    if operation in ['add', 'remove']:
        update_args = {field_id: [{operation: val} for val in send_val]}
    else:
        update_args = {field_id: [{operation: send_val}]}

    return issue.update(**update_args)


def _resolve_field_setup(jirate_obj, issue_obj):
    # Do NOT trample future python JIRA objects' field function.
    if hasattr(issue_obj, 'field'):
        raise Exception('API BREAK: \'field\' is now part of jira.resources.Issue. Please file a bug against Jirate!')
    if hasattr(issue_obj, 'update_field'):
        raise Exception('API BREAK: \'update_field\' is now part of jira.resources.Issue. Please file a bug against Jirate!')
    issue_obj._jirate = jirate_obj
    issue_obj.field = types.MethodType(_resolve_field, issue_obj)
    issue_obj.update_field = types.MethodType(_update_field, issue_obj)


def _check_fields(issue, name):
    if name in issue.raw['fields']:
        return name
    if nym(name) in issue.raw['fields']:
        return nym(name)
    for field in issue.raw['fields']:
        if nym(name) == nym(field):
            return field
    return None


class Jirate(object):
    """High-level wrapper for python-jira"""

    def __init__(self, jira):
        self.jira = jira
        self._field_to_id = None
        self._field_to_alias = None
        self._field_to_human = None
        jira.user = types.MethodType(_user_fix, jira)
        jira.user_by_key = types.MethodType(_user_by_key, jira)

    def _issue_key(self, alias):
        if isinstance(alias, str):
            return alias.upper()
        elif isinstance(alias, Issue):
            return alias.key
        elif isinstance(alias, int):
            return str(alias)
        raise ValueError(f'Unhandled type for {alias}')

    @property
    def user(self):
        return self.jira.myself()

    def attach(self, issue_alias, url, description):
        """Attach an external URL to an issue

        Parameters:
          issue_alias: int or string, could be JIRA Issue ID or key
          url: URL to attach (string)
          description: Description of link (string)
        """
        item = {'url': url, 'title': description}
        issue = self.issue(issue_alias)
        return self.jira.add_simple_link(issue, item)

    def search_users(self, username):
        """Wrapper for searching JIRA's user database

        Parameters:
          username: Partial username or email (string)

        Returns:
          list of jira.resources.User
        """
        # Search userlist for a username.  This is provided like this
        # so we can expand functionality later. Max is 50 by default;
        # we'll start with that
        users = self.jira.search_users(username)
        return users

    def field_to_id(self, alias_or_human):
        """
        Maps alias and human-readable field names to internal field identifiers.

        Parameters:
          alias_or_human: human-readable field name like "Story Points" or field alias like "story_points" (string)

        Returns:
          field ID like "customfield_12310243" (string)
        """
        if self._field_to_id is None:
            self._field_map_init()
        if alias_or_human in self._field_to_id:
            return self._field_to_id[alias_or_human]
        return None

    def field_to_alias(self, id_or_human):
        """
        Maps internal field identifiers and full human-readable names to field aliases

        Parameters:
          id_or_human: field ID like "customfield_12310243" or human-readable name like "Story Points" (string)

        Returns:
          field alias like "story_points" (string)
        """
        if self._field_to_alias is None:
            self._field_map_init()
        if id_or_human in self._field_to_alias:
            return self._field_to_alias[id_or_human]
        return None

    def field_to_human(self, id_or_alias):
        """
        Maps internal field identifiers and field aliases to human-readable field names

        Parameters:
          id_or_alias: field ID like "customfield_12310243" or alias like "story_points" (string)

        Returns:
          human-readable field name like "Story Points" (string)
        """
        if self._field_to_human is None:
            self._field_map_init()
        if id_or_alias in self._field_to_human:
            return self._field_to_human[id_or_alias]
        return None

    def _builtin_map_init(self, jira_val, human_val):
        self._field_to_id[jira_val] = jira_val
        self._field_to_id[human_val] = jira_val
        self._field_to_alias[jira_val] = jira_val
        self._field_to_alias[human_val] = jira_val
        self._field_to_human[jira_val] = human_val
        self._field_to_human[human_val] = human_val

    def _field_map_init(self):
        # For inscrutable reasons Jira returns all possible fields via the /field API...
        # ...all but one: the "parent" field. We hardcode the translation so higher-level
        # code doesn't need to deal with that.
        self._field_to_id = {}
        self._field_to_alias = {}
        self._field_to_human = {}
        self._builtin_map_init('parent', 'Parent')
        self._builtin_map_init('fixVersions', 'fixversions')
        self._builtin_map_init('lastViewed', 'lastviewed')

        fields = self.jira.fields()
        for field in fields:
            field_id = field['id']
            name = field['name']
            alias = nym(name)
            # append underscores for collisions
            # XXX hopefully this is extremely rare
            while alias in self._field_to_id:
                alias = alias + '_'
            # Everything maps to everything. _field_to_id can return a field ID when fed
            # either the human name, the alias, or even the ID itself.
            for val in (field_id, name, alias):
                self._field_to_id[val] = field_id
                self._field_to_human[val] = name
                self._field_to_alias[val] = alias
            for clause_name in field['clauseNames']:
                if (re.match('^cf\\[[0-9]+\\]$', clause_name) or clause_name in self._field_to_id):
                    # Skip nonsense and duplicate alternative names
                    continue
                self._field_to_id[clause_name] = field_id
                self._field_to_human[clause_name] = name
                self._field_to_alias[clause_name] = alias

    def search_issues(self, search_query):
        """Run a JQL search and assemble the results into one list

        Parameters:
          search_query: JQL query line (string)

        Returns:
          list of jira.resources.Issue
        """
        index = 0
        chunk_len = 50      # So we can detect end
        ret = []
        while True:
            issues = self.jira.search_issues(search_query, startAt=index, maxResults=chunk_len)
            if not len(issues):
                break
            ret.extend(issues)
            index = index + len(issues)
            if len(issues) < chunk_len:
                break
        for issue in ret:
            _resolve_field_setup(self, issue)
        return ret

    def _field(self, issue, field_name):
        """Reconcile a field in an issue with custom field defs
        on the jira server or an issue's fields. Does not retrieve
        the issue from the JIRA server.

        Parameters:
          issue_alias: int or string, could be JIRA Issue ID or key
          field_name: human readable field name

        Returns:
          field value, or none if not found

        Raises:
          AttributeError if the field does not exist.
        """
        # Don't return customfield if there's a direct match
        # obvious match
        if field_name in issue.raw['fields']:
            return field_name
        fname = self.field_to_id(field_name)
        if fname in issue.raw['fields']:
            return fname
        fname = _check_fields(issue, field_name)
        if fname in issue.raw['fields']:
            return fname
        raise AttributeError(str(issue) + f' has no field like {field_name}')

    def field(self, issue_alias, field_name):
        """Reconcile a field in an issue with custom field defs
        on the jira server. Retrieves the issue from the server if
        needed.

        Parameters:
          issue_alias: int or string, could be JIRA Issue ID or key
          field_name: human readable field name

        Returns:
          field value, or none if not found

        Raises:
          AttributeError if the field does not exist.
        """
        issue = self.issue(issue_alias)
        fname = self._field(issue, field_name)
        return issue.raw['fields'][fname]

    def fields(self, issue_alias):
        """Determine the fields available for an issue

        Parameters:
          issue_alias: int or string, could be JIRA Issue ID or key

        Returns:
          dict of fields
        """
        issue = self.issue(issue_alias)
        # XXX HERE THERE BE DRAGONS
        # NOT IMPLEMENTED UPSTREAM
        url = os.path.join(issue.raw['self'], 'editmeta')
        field_blob = json_loads(self.jira._session.get(url))
        return field_blob['fields']

    def get_user(self, username):
        """Determine JIRA's normalized username for someone

        Parameters:
          username: email, display name or username

        Returns:
          username (string)
        """
        if not username or username.lower() == 'none':
            return None
        if username == 'me':
            return self.user['name']
        users = self.jira.search_users(username)
        if len(users) > 1:
            raise ValueError(f'Multiple matching users for \'{username}\'')
        elif not users:
            raise ValueError(f'No matching users for \'{username}\'')

        return users[0].name

    def api_call(self, uri, raw=False):
        url = self.jira._get_url(uri)
        ret = self.jira._session.get(url)
        if raw:
            return ret.text
        return json_loads(ret)

    def assign(self, issue_aliases, users=None):
        """Assign a set of issues to a user

        NOTE: Originally, the additional users were going to be set as
        watchers, which is another API call. We did this with Trello.
        Do we want to do that for JIRA, or should we have separate
        watch/unwatch?

        Parameters:
          issue_aliases: list of issue keys or IDs (list of strings)
          users: list of users (list of strings)

        Returns:
          list of issues successfully assigned to the user(s)
        """
        if isinstance(users, str):
            users = [users]
        issues = self.issues(issue_aliases)

        for issue in issues:
            user_ids = []

            # first is assignee
            if users:
                for user in users:
                    uid = self.get_user(user)
                    if uid not in user_ids:
                        user_ids.append(uid)
            else:
                # Just me
                user = self.user['name']
                user_ids = [user]
                # user_ids = [user['id']]

            if not len(users):
                return

            user = user_ids.pop(0)
            issue.update(assignee=user)

    def sprint_info(self, project_key, states=['active', 'future']):
        """Retrieve all sprints and boards for a project.

        Parameters:
          project_key: Key of project to check
          states: Array or string (comma separated) of sprint states

        Returns:
          dict with boards and sprints
        """
        if isinstance(states, list):
            states = ','.join(states)

        ret = {'boards': {}, 'sprints': {}}
        # XXX fixme: paginated APIs
        boards = []
        _start = 0
        _max = 50
        while True:
            new_boards = self.jira.boards(projectKeyOrID=project_key, startAt=_start, maxResults=_max)
            if not new_boards:
                break
            _start = _start + _max
            boards.extend(new_boards)

        sprints = []
        for board in boards:
            if board.type != 'scrum':
                continue
            _start = 0
            while True:
                new_sprints = self.jira.sprints(board.id, startAt=_start, maxResults=_max, state=states)
                if not new_sprints:
                    break
                _start = _start + _max
                sprints.extend(new_sprints)

            if board.name in ret['boards']:
                old = ret['boards'][board.name]
                if old.id != board.id:
                    print(f'Warning: Duplicate Board: {old.name} (IDs: {old.id} {board.id})')
            ret['boards'][board.name] = board

        for sprint in sprints:
            if sprint.name in ret['sprints']:
                old = ret['sprints'][sprint.name]
                if old.id != sprint.id:
                    print(f'Warning: Duplicate Sprint: {old.name} (IDs: {old.id} {sprint.id})')
            ret['sprints'][sprint.name] = sprint
        return ret

    def get_comment(self, issue_alias, comment_id):
        """Retrieve raw comment for an issue

        Parameters:
          issue_alias: issue key or ID (string)
          comment_id: ID of comment to retrieve

        Returns:
          jira.resources.Comment
        """
        issue = self.issue(issue_alias)
        return self.jira.comment(issue.raw['key'], comment_id)

    def comment(self, issues, text, visibility=None):
        """Attach a new comment to a set of issues

        Parameters:
          issues: issue key or ID (string)
          text: Text to attach as comment

        Returns:
          [jira.resources.Issue] for updated issues
        """
        issue_list = list_or_splitstr(issues)

        comment_data = {'body': text}
        if visibility:
            if isinstance(visibility, str):
                comment_data['visibility'] = {}
                comment_data['visibility']['type'] = 'group'
                comment_data['visibility']['value'] = visibility
            elif isinstance(visibility, dict):
                comment_data['visibility'] = visibility

        ret = []
        for alias in issue_list:
            issue = self.issue(alias)
            # Use simple comment mode to add a comment
            url = os.path.join(issue.raw['self'], 'comment')
            if self.jira._session.post(url, data=comment_data):
                ret.append(issue)
        return ret

    def close(self, issues, **args):
        """Close an issue

        XXX this might not be a usable API and/or may be a higher
        level transition than we want. Note that 'Closed' may also
        not be correct for a given project, since all transitions
        are per-project. We could do something intelligent with
        move, or delete this API altogether.

        Parameters:
          issues: list of issue keys or IDs (list of string)
          args: dictionary of fields to set on transition
                (resolution only really known right now)

        Returns:
          requests.Response
        """
        return self.move(issues, 'Closed', **args)

    def create(self, field_definitions=None, **args):
        """Create a new issue using key/value pairs

        Parameters:
          field_definitions: List of creation definitions for the
                             issue type.
          **args: Dictionary of key/value pairs (dict)

        Returns:
          jira.resources.Issue
        """
        # Make sure we create in correct project if we're creating
        # a subtask. Also resolve parent issue.
        if 'parent' in args and isinstance(args['parent'], str):
            parent_issue = self.issue(args['parent'])
            project = parent_issue.raw['fields']['project']['key']
            args['parent'] = parent_issue.key
            args['project'] = project

        # Transmogrify other fields
        new_args = transmogrify_input(field_definitions, **args)
        return self.jira.create_issue(**new_args)

    def update_issue(self, issue_alias, field_definitions=None, **kwargs):
        """Update an issue using key/value pairs

        Parameters:
          **args: Dictionary of key/value pairs (dict)

        Returns:
          jira.resources.Issue (?)
        """
        issue = self.issue(issue_alias)
        if not issue:
            return None

        args = {}
        for field in kwargs:
            args[self.field_to_id(field)] = kwargs[field]
        return issue.update(**kwargs)

    def update(self, issue_list, **kwargs):
        """Update a set of issues using key/value pairs

        Parameters:
          **kwargs: Dictionary of key/value pairs (dict)

        Returns:
          [jira.resources.Issue] of updated issues
        """
        ret = []
        args = {}

        for field in kwargs:
            args[self.field_to_id(field)] = kwargs[field]
        issues = list_or_splitstr(issue_list)
        for issue_alias in issues:
            issue = self.issue(issue_alias)
            if not issue:
                continue
            issue.update(**args)
            ret.append(issue)
        return ret

    def issue(self, issue_alias, verbose=False):
        """Retrieve an issue from JIRA

        XXX Cleanup vs. JiraProject

        Parameters:
          issue_alias: key or issue ID (string)

        Returns:
          jira.resources.Issue
        """
        if isinstance(issue_alias, Issue):
            return issue_alias
        issue_aliases = [issue_alias]
        if isinstance(issue_alias, int):
            issue_alias = str(issue_alias)
        if issue_alias.upper() != issue_alias:
            issue_aliases.append(issue_alias.upper())
        for alias in issue_aliases:
            try:
                issue = self.jira.issue(alias)
                if not issue:
                    continue
                _resolve_field_setup(self, issue)
                return issue
            except JIRAError:
                pass
        return None

    def votes(self, issue_alias):
        if isinstance(issue_alias, Issue):
            ret = self.jira.votes(issue_alias.key)
            if ret:
                issue_alias.raw['fields']['votes'] = ret.raw
        else:
            ret = self.jira.votes(issue_alias)
        return ret

    def watchers(self, issue_alias):
        if isinstance(issue_alias, Issue):
            ret = self.jira.watchers(issue_alias.key)
            if ret:
                issue_alias.raw['fields']['watches'] = ret.raw
        else:
            ret = self.jira.votes(issue_alias)
        return ret

    def eausm_issue_votes(self, issue_alias):
        """Retrieve EAUSM (Easy Agile Planning Poker) votes
        for an issue

        Parameters:
          issue_alias: key, issue ID (string), or Issue object

        Returns:
          raw json data of EAUSM information
        """
        issue = self.issue(issue_alias)
        if not issue:
            return None
        if 'eausm' in issue.raw['fields']:
            return issue.raw['fields']['eausm']

        # Check for the EZ Agile Planning Poker ext on the server
        EAUSM_url = self.jira.server_url + \
            f"/rest/eausm/latest/planningPoker/{issue.id}"
        try:
            ret = self.jira._session.get(EAUSM_url)
            EAUSM_json = json_loads(ret)
            issue.raw['fields']['eausm'] = EAUSM_json
        except JIRAError:
            return False
        return issue.raw['fields']['eausm']

    def eausm_vote_issue(self, issue_alias, vote):
        """Set EAUSM (Easy Agile Planning Poker) votes
        for an issue

        Parameters:
          issue_alias: key, issue ID (string), or Issue object
          votes: string or integer for story point voting

        Returns:
          None: no such issue or voting disabled
          False: Failed to set
          True: OK
        """
        issue = self.issue(issue_alias)
        if not issue:
            return None
        vote = int(vote)

        EAUSM_url = f"{self.jira.server_url}/rest/eausm/latest/planningPoker/vote"
        payload = {"issueId": issue.id, "vote": vote}
        ret = self.jira._session.put(EAUSM_url, data=payload)
        if not ret:
            return False
        return True

    def issues(self, issue_list, verbose=False):
        """Retrieve one or more issues from JIRA

        Parameters:
          issue_list: string of keys or list of keys (strings)

        Returns:
          list of jira.resources.Issue or None
        """
        if not issue_list:
            return []
        if isinstance(issue_list, Issue):
            return issue_list
        issues = list_or_splitstr(issue_list)
        search_issues = []
        issue_objs = []
        for issue in issues:
            if isinstance(issue, Issue):
                issue_objs.append(issue)
            else:
                search_issues.append(self._issue_key(issue))

        if len(search_issues) == 1:
            # If we only need one issue, avoid the risk of the extra call to grab fields
            ret = [self.issue(search_issues[0])]
        else:
            # This is one API call instead of N (two if fields have not been cached)
            ret = self.search_issues('key in (' + ', '.join(search_issues) + ')')
        ret.extend(issue_objs)
        return ret or None

    def transitions(self, issue):
        """Retrieve possible next-state transitions for an issue

        Parameters:
          issue_alias: key or issue ID (string)

        Returns:
          list of transitions w/ metadata
        """
        if isinstance(issue, str):
            issue = self.issue(issue)
        if not issue:
            return None
        url = os.path.join(issue.raw['self'], 'transitions?expand=transitions.fields')
        transitions = json_loads(self.jira._session.get(url))
        if transitions:
            return transitions['transitions']

    def _find_transition(self, issue, status):
        transitions = self.transitions(issue)
        for transition in transitions:
            trans_state = transition['to']['name']
            trans_state_id = transition['to']['id']
            if trans_state == status or nym(trans_state) == status or str(status) == str(trans_state_id):
                return transition
        return None

    def move(self, issue_list, status, **args):
        """Execute a transition to move a set of issues to the desired status

        Jira doesn't have a status you can update; you have to retrieve possible
        transitions and satisfy those requirements. Each issue has its own transition map
        according to the issue type within a given project

        Parameters:
          issue_aliases: list keys or issue IDs (list of string)
          status: Desired status
          **args: field=value pairs to set on transition

        Returns:
          list of successfully moved issues (list of string)
        """
        issue_aliases = list_or_splitstr(issue_list)
        issues = self.issues(issue_aliases)

        if len(issues) < len(issue_aliases):
            fails = list(set(issue_aliases) - set([issue.key for issue in issues]))
            raise ValueError('No such issue(s): ' + str(fails))

        moved = []
        for issue in issues:
            if not issue:
                continue
            transition = self._find_transition(issue, status)
            if not transition:
                continue
            # API cleanup:
            # If it's already in the target status, don't apply the move
            if transition['to']['name'] == issue.fields.status.name:
                continue

            data = {'transition': {'id': transition['id']}}
            if args and 'fields' in transition:
                new_args = transmogrify_input(transition['fields'], **args)
                data['fields'] = new_args
                if new_args == {}:
                    oops = [args.keys()]
                    raise ValueError(f'field(s) not allowed in transition: {oops}')

            # POST /rest/api/2/issue/{issueIdOrKey}/transitions
            url = os.path.join(issue.raw['self'], 'transitions')
            self.jira._session.post(url, data=data)
            moved.append(issue)
        return moved

    def link_types(self):
        """Wrapper for jira.issue_link_types()"""
        return self.jira.issue_link_types()

    def link(self, left_alias, right_alias, link_text):
        """Link two isues together using the noted link type

        Parameters:
          left_alias: left key or issue IDs (string)
          right_alias: right key or issue IDs (string)
          link_text: Desired link type

        Returns:
          ???
        """
        left = self._issue_key(left_alias)
        right = self._issue_key(right_alias)
        return self.jira.create_issue_link(link_text, left, right)

    def remote_links(self, issue_alias):
        """Obtain all remote links (URLs) attached to an issue

        Parameters:
          issue_alias: key or issue IDs (string)

        Returns:
          list of jira.resources.RemoteLink
        """
        issue = self._issue_key(issue_alias)
        return self.jira.remote_links(issue)

    def unlink(self, left_alias, right_alias):
        """Break all links between to issues

        Parameters:
          left_alias: left key or issue IDs (string)
          right_alias: right key or issue IDs (string)

        Returns:
          count of links removed
        """
        left = self.issue(left_alias)
        right = self.issue(right_alias)

        if not right:
            extlink = self.jira.remote_link(left.raw['key'], str(right_alias))
            self.jira._session.delete(extlink.raw['self'])
            return 1

        info = left.raw['fields']

        if 'issuelinks' not in info or not info['issuelinks']:
            return 0

        right_name = right.raw['key']
        count = 0
        for link in info['issuelinks']:
            link_id = None
            if 'inwardIssue' in link and link['inwardIssue']['key'] == right_name:
                link_id = link['id']
            if 'outwardIssue' in link and link['outwardIssue']['key'] == right_name:
                link_id = link['id']
            if link_id:
                count = count + 1
                self.jira.delete_issue_link(link_id)
        return count


class JiraProject(Jirate):
    def __init__(self, jira, project, closed_status=None, readonly=False, allow_code=False):
        super().__init__(jira)
        self._ro = readonly
        self._config = None
        self._closed_status = closed_status
        self._project = self.jira.project(project)
        self._issue_types = None
        self.custom_fields = None
        self.project_name = project
        self.allow_code = allow_code
        self.refresh()

        if self._closed_status is None:
            # guess at common closed states
            for status in ['CLOSED', 'DONE', 'RESOLVED']:
                try:
                    self.status_to_id(status)
                    self._closed_status = status
                    break
                except KeyError:
                    pass

    def _issue_key(self, alias):
        try:
            if str(int(alias)) == alias:
                alias = f'{self.project_name}-{alias}'
        except (TypeError, ValueError):
            pass
        return super()._issue_key(alias)

    def refresh(self):
        if not self._config:
            self._config = {'states': {},
                            'issue_map': {}}

        self.refresh_lists()

    def refresh_lists(self):
        # DANGER DANGER - using private stuff because upstream doesn't have it
        spath = os.path.join(self._project._resource, 'statuses')
        url = self._project._get_url(spath.format(str(self._project)))
        status_info = json_loads(self.jira._session.get(url))
        status_ids = []
        statuses = []

        for task_type in status_info:
            for status in task_type['statuses']:
                if status['id'] not in status_ids:
                    status_ids.append(status['id'])
                    statuses.append(status)

        for item in statuses:
            val = {}
            val['name'] = item['name']
            val['id'] = item['id']
            name = nym(val['name'])
            while name in self._config['states']:
                name = name + '_'
            self._config['states'][name] = val

    def delete_issue_map(self):
        self._config['issue_map'] = {}

    def unlabel_issue(self, issue_alias, label_name):
        return False

    def status_to_id(self, status):
        status = nym(status)

        if status not in self._config['states']:
            raise KeyError('No such list: ' + status)
        if status in self._config['states']:
            return self._config['states'][status]['id']
        return status  # must be the ID

    def search_issues(self, text):
        # Override so we can index our return values
        # TODO resolve fixversions?
        if not text:
            return None
        ret = super().search_issues(text)
        self._index_issues(ret)
        return ret

    def _index_issue(self, issue):
        if issue.key not in self._config['issue_map']:
            if not hasattr(issue, '_jirate'):
                _resolve_field_setup(self, issue)
            self._config['issue_map'][issue.key] = issue

    def _index_issues(self, issues):
        if 'issue_map' not in self._config:
            self._config['issue_map'] = {}

        for issue in issues:
            self._index_issue(issue)

    def search(self, text):
        if not text:
            return None
        return self.search_issues(f'PROJECT = {self.project_name} AND statusCategory NOT IN (Done) AND (text ~ "{text}")')

    def list(self, status=None, userid=None, all_issues=False):
        if all_issues:
            project_selector = ''
        else:
            project_selector = f'PROJECT = {self.project_name} AND '

        userid = self.get_user(userid)
        if userid is None:
            assignee_selection = 'assignee is EMPTY'
        else:
            assignee_selection = f'assignee = "{userid}"'

        if status:
            issues = super().search_issues(f'{project_selector}{assignee_selection} AND STATUS = {status}')
        else:
            issues = super().search_issues(f'{project_selector}{assignee_selection} AND statusCategory NOT IN (Done)')

        self._index_issues(issues)
        return issues

    def issue(self, issue_alias, verbose=False):
        if isinstance(issue_alias, Issue):
            return issue_alias
        issue_aliases = [issue_alias]
        if issue_alias.upper() != issue_alias:
            issue_aliases.append(issue_alias.upper())
        if '-' not in issue_alias:
            issue_aliases.insert(0, self.project_name.upper() + f'-{issue_alias}')
        for alias in issue_aliases:
            if alias in self._config['issue_map']:
                return self._config['issue_map'][alias]
            try:
                issue = self.jira.issue(alias)
                if not issue:
                    continue
                self._index_issue(issue)
                return issue
            except JIRAError:
                pass
        return None

    def eausm_issue_votes(self, issue_alias):
        if 'eausm' in self._config and not self._config['eausm']:
            return None
        ret = super().eausm_issue_votes(issue_alias)
        if ret is False:
            self._config['eausm'] = False
            return None
        return ret

    def eausm_vote_issue(self, issue_alias, votes):
        if 'eausm' in self._config and not self._config['eausm']:
            return False
        return super().eausm_vote_issue(issue_alias, votes)

    def states(self):
        return copy.copy(self._config['states'])

    def new(self, name, description=None, issue_type=None, parent=None):
        # Simple New creation requires understanding what the issuetypes are,
        # which vary on a per-project basis.  This is why "create" is separate
        # (and lower-level)
        if parent:
            if issue_type != 'Sub-task':
                raise ValueError('Specifying a parent only valid for Sub-task type')

        issuetypes = self.issue_types
        resolved_issue_type = None
        if issue_type is not None:
            for itype in issuetypes:
                if itype.name.upper() == issue_type.upper():
                    resolved_issue_type = itype.name
                    break
            if not resolved_issue_type:
                raise ValueError(f'No such issue type: {issue_type}')
        else:
            resolved_issue_type = issuetypes[0].name

        args = {}
        args['project'] = self.project_name
        args['summary'] = name
        args['issuetype'] = resolved_issue_type
        if parent is not None:
            args['parent'] = parent
        if description:
            args['description'] = description

        return self.create(**args)

    def create(self, field_definitions=None, **args):
        # override so we can index our value
        if 'project' not in args:
            args['project'] = self.project_name
        if 'issuetype' not in args:
            args['issuetype'] = 'Task'

        if not field_definitions:
            metadata = self.issue_metadata(args['issuetype'])
            field_definitions = metadata['fields']
        ret = super().create(field_definitions, **args)
        self._index_issue(ret)
        return ret

    def components(self):
        """ Return list of components assigned to this project

        Returns:
           List[component]
        """
        return self.jira.project_components(self._project)

    def add_component(self, name, description=None):
        """ Add a component to the project

        Returns:
           component
        """
        return self.jira.create_component(name, self._project, description=description)

    def remove_component(self, name):
        """ Remove a component from the project. To do this, we have to run down
        the list of components in this project to find a match then pass the ID
        to the API

        Returns:
            ???
        """
        comps = self.components()
        for comp in comps:
            if comp.name == name:
                return comp.delete()
        return 1

    def subtask(self, parent, name, description=None):
        return self.new(name, description, 'Sub-task', parent)

    @property
    def issue_types(self):
        if not self._issue_types:
            self._issue_types = self._project.issueTypes
        return self._issue_types

    @property
    def versions(self):
        return self._project.versions

    # Returns a dict that JIRA should just give us.
    def issue_metadata(self, issue_type_or_id, project_key=None):
        if not project_key:
            project_key = self.project_name
        itype = None
        for issuetype in self.issue_types:
            if issuetype.id == issue_type_or_id or nym(issuetype.name) == nym(issue_type_or_id):
                itype = issuetype
        if not itype:
            return None

        fields = []
        start = 0
        chunk_len = 50
        while True:
            new_fields = self.jira.project_issue_fields(project_key, itype.id, startAt=start, maxResults=chunk_len)
            for field in new_fields:
                fields.append(field.raw)
            if new_fields.isLast:
                break
            start = start + chunk_len

        field_dict = {val['fieldId']: val for val in fields}
        metadata = {'self': itype.self, 'name': itype.name, 'id': itype.id, 'description': itype.description, 'subtask': itype.subtask, 'iconUrl': itype.iconUrl, 'fields': field_dict}
        return metadata

    def sprint_info(self, project_key=None, states=['active', 'future']):
        if not project_key:
            project_key = self.project_name
        return super().sprint_info(project_key, states)

    def config(self):
        return copy.copy(self._config)

    def get_user_data(self, key):
        if key in ('states', 'issue_map'):
            return KeyError('Reserved configuration keyword: ' + key)
        if key in self._config:
            return copy.copy(self._config[key])
        return None

    def set_user_data(self, key, userdata):
        if key in ('states', 'issue_map'):
            return KeyError('Reserved configuration keyword: ' + key)
        self._config[key] = copy.copy(userdata)


def get_jira(jconfig):
    """Wrapper to create a python-jira connection

    Parameters:
      jconfig: dict of 3 keys: url, token, proxies (optional)

    Returns:
      JIRA
    """
    if 'url' not in jconfig:
        print('No JIRA URL specified')
        return None
    if 'token' not in jconfig:
        print('No JIRA token specified')
        return None
    if 'proxies' not in jconfig:
        jconfig['proxies'] = {"http": "", "https": ""}

    return JIRA(jconfig['url'], token_auth=jconfig['token'], proxies=jconfig['proxies'])
