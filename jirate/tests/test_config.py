#!/usr/bin/python3

import os

import pytest  # NOQA

from jirate.config import get_config, ParseError


def test_nonsense_config(tmp_path):
    filename = os.path.join(tmp_path, 'config_test')

    fp = open(filename, "w+")
    fp.write(':djsaklsajkZZ{}')
    fp.close()

    with pytest.raises(ParseError):
        get_config(filename)


def test_yaml_config(tmp_path):
    filename = os.path.join(tmp_path, 'config_test')

    fp = open(filename, "w+")
    fp.write('abc:\n')
    fp.write('  def: 1\n')
    fp.close()

    assert get_config(filename) == {'abc': {'def': 1}}


def test_json_config(tmp_path):
    filename = os.path.join(tmp_path, 'config_test')

    fp = open(filename, "w+")
    fp.write('{"abc": {"def": 1}}\n')
    fp.close()

    assert get_config(filename) == {'abc': {'def': 1}}
