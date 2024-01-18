#!/usr/bin/env python3

from pathlib import Path
from collections import namedtuple

import pytest
from jsonschema.exceptions import ValidationError

from jirate.jira_cli import validate_template

TEMPLATE_DIR = Path('jirate/tests/templates').absolute()
FakeArgs = namedtuple('FakeArgs', 'template_file')


def test_validate_templates_good():
    # Validating a known-good template should succeed
    good_args = FakeArgs(template_file=f"{TEMPLATE_DIR / 'good-template.yaml'}")
    validate_template(good_args)


def test_validate_templates_bad():
    # Validating a known-bad template should fail
    bad_args = FakeArgs(template_file=f"{TEMPLATE_DIR / 'bad-template.yaml'}")
    with pytest.raises(ValidationError):
        validate_template(bad_args)
