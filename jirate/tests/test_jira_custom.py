#!/usr/bin/python3
from jirate.jira_custom import sprint_content_to_py, sprint_field

import pytest  # NOQA


def test_jira_sprint_parse_simple():
    val1 = "com.atlassian.greenhopper.service.sprint.Sprint@49e59daf[id=13133,rapidViewId=21164,state=CLOSED,name=Porky Sprint 5 - Sept,startDate=2024-09-01T06:22:00.000Z,endDate=2024-09-29T06:22:00.000Z,completeDate=2024-10-02T06:38:15.491Z,activatedDate=2024-09-03T02:47:34.778Z,sequence=13133,goal=,synced=false,autoStartStop=false,incompleteIssuesDestinationId=<null>]"

    expected = [{'_hash': '49e59daf',
                 'id': 13133,
                 'rapidViewId': 21164,
                 'state': 'CLOSED',
                 'startDate': '2024-09-01T06:22:00.000Z',
                 'endDate': '2024-09-29T06:22:00.000Z',
                 'completeDate': '2024-10-02T06:38:15.491Z',
                 'name': 'Porky Sprint 5 - Sept',
                 'activatedDate': '2024-09-03T02:47:34.778Z',
                 'sequence': 13133,
                 'goal': '',
                 'synced': False,
                 'autoStartStop': False,
                 'incompleteIssuesDestinationId': None}]

    assert sprint_content_to_py(val1) == expected


def test_sprint_field():
    val1 = "com.atlassian.greenhopper.service.sprint.Sprint@49e59daf[id=13133,rapidViewId=21164,state=CLOSED,name=Porky Sprint 5 - Sept,startDate=2024-09-01T06:22:00.000Z,endDate=2024-09-29T06:22:00.000Z,completeDate=2024-10-02T06:38:15.491Z,activatedDate=2024-09-03T02:47:34.778Z,sequence=13133,goal=,synced=false,autoStartStop=false,incompleteIssuesDestinationId=<null>]"

    assert sprint_field(val1, None, False) == 'Porky Sprint 5 - Sept (ID: 13133)'


def test_sprint_multi_open():
    # Take last active sprint
    val1 = ["com.atlassian.greenhopper.service.sprint.Sprint@56814b6f[id=21301,rapidViewId=21064,state=CLOSED,name=Homies Sprint 5,startDate=2025-01-06T03:00:00.000Z,endDate=2025-01-25T04:00:00.000Z,completeDate=2025-01-25T04:00:43.237Z,activatedDate=2025-01-06T03:00:45.655Z,sequence=21301,goal=<null>,synced=false,autoStartStop=true,incompleteIssuesDestinationId=18234]", "com.atlassian.greenhopper.service.sprint.Sprint@638afb2[id=18234,rapidViewId=21064,state=ACTIVE,name=Homies Sprint 6,startDate=2025-01-27T03:00:00.000Z,endDate=2025-02-15T03:00:00.000Z,completeDate=<null>,activatedDate=2025-01-27T03:00:31.194Z,sequence=18234,goal=<null>,synced=false,autoStartStop=true,incompleteIssuesDestinationId=40133]"]

    assert sprint_field(val1, None, False) == 'Homies Sprint 6 (ID: 18234)'


def test_sprint_multi_closed():
    # Take last closed sprint
    val1 = ["com.atlassian.greenhopper.service.sprint.Sprint@56814b6f[id=21301,rapidViewId=21064,state=CLOSED,name=Homies Sprint 5,startDate=2025-01-06T03:00:00.000Z,endDate=2025-01-25T04:00:00.000Z,completeDate=2025-01-25T04:00:43.237Z,activatedDate=2025-01-06T03:00:45.655Z,sequence=21301,goal=<null>,synced=false,autoStartStop=true,incompleteIssuesDestinationId=18234]", "com.atlassian.greenhopper.service.sprint.Sprint@638afb2[id=18234,rapidViewId=21064,state=CLOSED,name=Homies Sprint 6,startDate=2025-01-27T03:00:00.000Z,endDate=2025-02-15T03:00:00.000Z,completeDate=<null>,activatedDate=2025-01-27T03:00:31.194Z,sequence=18234,goal=<null>,synced=false,autoStartStop=true,incompleteIssuesDestinationId=40133]"]

    assert sprint_field(val1, None, False) == 'Homies Sprint 6 (ID: 18234)'


def test_sprint_multi_future():
    # Take last active sprint
    val1 = ["com.atlassian.greenhopper.service.sprint.Sprint@56814b6f[id=21301,rapidViewId=21064,state=ACTIVE,name=Homies Sprint 5,startDate=2025-01-06T03:00:00.000Z,endDate=2025-01-25T04:00:00.000Z,completeDate=2025-01-25T04:00:43.237Z,activatedDate=2025-01-06T03:00:45.655Z,sequence=21301,goal=<null>,synced=false,autoStartStop=true,incompleteIssuesDestinationId=18234]", "com.atlassian.greenhopper.service.sprint.Sprint@638afb2[id=18234,rapidViewId=21064,state=FUTURE,name=Homies Sprint 6,startDate=2025-01-27T03:00:00.000Z,endDate=2025-02-15T03:00:00.000Z,completeDate=<null>,activatedDate=2025-01-27T03:00:31.194Z,sequence=18234,goal=<null>,synced=false,autoStartStop=true,incompleteIssuesDestinationId=40133]"]

    assert sprint_field(val1, None, False) == 'Homies Sprint 5 (ID: 21301)'


def test_sprint_multi_active():
    # two sprints, I guess?
    val1 = ["com.atlassian.greenhopper.service.sprint.Sprint@56814b6f[id=21301,rapidViewId=21064,state=ACTIVE,name=Homies Sprint 5,startDate=2025-01-06T03:00:00.000Z,endDate=2025-01-25T04:00:00.000Z,completeDate=2025-01-25T04:00:43.237Z,activatedDate=2025-01-06T03:00:45.655Z,sequence=21301,goal=<null>,synced=false,autoStartStop=true,incompleteIssuesDestinationId=18234]", "com.atlassian.greenhopper.service.sprint.Sprint@638afb2[id=18234,rapidViewId=21064,state=ACTIVE,name=Homies Sprint 6,startDate=2025-01-27T03:00:00.000Z,endDate=2025-02-15T03:00:00.000Z,completeDate=<null>,activatedDate=2025-01-27T03:00:31.194Z,sequence=18234,goal=<null>,synced=false,autoStartStop=true,incompleteIssuesDestinationId=40133]"]

    assert sprint_field(val1, None, False) == 'Homies Sprint 5 (ID: 21301), Homies Sprint 6 (ID: 18234)'
