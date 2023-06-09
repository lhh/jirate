#!/usr/bin/env python3

from pathlib import Path
import yaml

import jsonschema
import pytest
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

SCHEMA_DIR = Path('schemas').absolute()
SCHEMAS = list(SCHEMA_DIR.rglob("*.yaml"))

TEMPLATE_DIR = Path('templates').absolute()
# NOTE: rglob does not follow symlinks prior to Python 3.13 See https://github.com/python/cpython/pull/102616
TEMPLATES = list(TEMPLATE_DIR.rglob("*.yaml"))


def _yaml_load(path):
    return yaml.safe_load(path.read_text())


def retrieve_yaml(uri):
    if uri.startswith("file://schemas"):
        path = SCHEMA_DIR / Path(uri.removeprefix("file://schemas/"))
    elif uri.startswith("file://templates"):
        path = TEMPLATE_DIR / Path(uri.removeprefix("file://templates/"))
    else:
        raise NoSuchResource(ref=uri)

    contents = yaml.safe_load(path.read_text())
    return Resource.from_contents(contents)


@pytest.fixture(scope="session")
def template_validator():
    """Schema validator for templates.

    This is a performance optimization in which the validator
    is instantiated only once per session.
    """
    schema = _yaml_load(SCHEMA_DIR / Path('template.yaml'))
    registry = Registry(retrieve=retrieve_yaml)

    return jsonschema.Draft202012Validator(
        schema=schema,
        registry=registry,
    )


@pytest.mark.parametrize("schema", SCHEMAS)
def test_schema(schema):
    schema = _yaml_load(schema)
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("template", TEMPLATES)
def test_template(template, template_validator):
    template_validator.validate(_yaml_load(template))
