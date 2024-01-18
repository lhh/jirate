#!/usr/bin/env python3

from pathlib import Path
import yaml

import jsonschema
import pytest

SCHEMA_DIR = Path('jirate/schemas').absolute()
SCHEMAS = list(SCHEMA_DIR.rglob("*.yaml"))


def test_at_least_one_schema():
    # Detects issues in the provided schemas path, as pytest quietly skips
    # parametrized tests with empty parameters
    assert len(SCHEMAS) > 0


@pytest.mark.parametrize("schema", SCHEMAS)
def test_schema(schema):
    schema = yaml.safe_load(schema.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
