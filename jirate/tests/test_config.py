#!/usr/bin/python3

import os

import pytest  # NOQA

from jirate.config import get_config, ParseError, yaml_dump


def test_yaml_dump():
    inp = {"test": "abc\n\nabcdef"}
    expected = '''test: |-
  abc

  abcdef
'''
    assert yaml_dump(inp) == expected


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


def test_json_config(tmp_path, monkeypatch):
    filename = os.path.join(tmp_path, '.jirate.json')

    fp = open(filename, "w+")
    fp.write('{"abc": {"def": 1}}\n')
    fp.close()

    assert get_config(filename) == {'abc': {'def': 1}}
    # Copied from below
    monkeypatch.setattr(os.path, 'expanduser', lambda x: tmp_path / x.replace('~/', ''))
    assert get_config() == {'abc': {'def': 1}}


# Gemini Advanced
def test_get_config_no_files_found(tmp_path, monkeypatch):
    # Test the function when no default files exist
    monkeypatch.setattr(os.path, 'expanduser', lambda x: tmp_path / x.replace('~/', ''))

    with pytest.raises(FileNotFoundError):
        get_config()

    # Added explicit filename test which should fail
    with pytest.raises(FileNotFoundError):
        get_config('nonexistent')
