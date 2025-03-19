#!/usr/bin/python3

import re


_val_to_py = {
    'false': False,
    'true': True,
    '<null>': None
}


def val_to_py(val):
    if val in _val_to_py:
        return _val_to_py[val]
    try:
        ret = int(val)
        return ret
    except ValueError:
        pass
    try:
        ret = float(val)
        return ret
    except ValueError:
        pass
    return val


# Jira Sprint Rendering
# TODO: Allow custom sprint output
def sprint_content_to_py(sprint_info):
    ret = []
    if isinstance(sprint_info, str):
        sprint_info = [sprint_info]

    for sprint in sprint_info:
        match = re.match(r'com.atlassian.greenhopper.service.sprint.Sprint@([a-z0-9]+)\[([^\]]+)\]', sprint)
        if not match:
            raise ValueError(f'Could not parse sprint: {sprint}')

        item = {'_hash': str(match.group(1))}
        info_bits = match.group(2)
        for bit in info_bits.split(','):
            try:
                key, value = bit.split('=')
                item[key] = val_to_py(value)
            except ValueError:
                continue
        ret.append(item)
    return ret


def sprint_field(data, fields, as_object=False):
    if as_object:
        return data
    sprints = sprint_content_to_py(data)
    active_sprints = []
    for sprint in sprints:
        if sprint['state'] == 'ACTIVE':
            active_sprints.append(f"{sprint['name']} (ID: {sprint['id']})")

    if active_sprints:
        # All active sprints
        return ', '.join(active_sprints)

    # Last closed sprint
    sprint = sprints[-1]
    return f"{sprint['name']} (ID: {sprint['id']})"


def no_display(data, fields, as_object=False):
    if as_object:
        return data
    return None


# Used by jira_fields
custom_field_renderers = {
    'com.atlassian.jira.plugins.jira-development-integration-plugin:devsummary': no_display,
    'com.onresolve.jira.groovy.groovyrunner:scripted-field': no_display,
    'com.pyxis.greenhopper.jira:gh-epic-color': no_display,
    'com.pyxis.greenhopper.jira:gh-global-rank': no_display,
    'com.pyxis.greenhopper.jira:gh-lexo-rank': no_display,
    'com.pyxis.greenhopper.jira:gh-sprint': sprint_field
}
