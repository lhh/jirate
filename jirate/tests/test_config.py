#!/usr/bin/python3

import os

import pytest  # NOQA

from jirate.config import get_config, ParseError, yaml_dump, EnvConfig


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


def test_get_config_no_files_found(tmp_path, monkeypatch):

    # Added explicit filename test which should fail
    with pytest.raises(FileNotFoundError):
        get_config('nonexistent')


# Envvar test: default files missing, returns nearly-empty dict
def test_get_config_empty(tmp_path, monkeypatch):
    # Test the function when no default files exist
    monkeypatch.setattr(os.path, 'expanduser', lambda x: tmp_path / x.replace('~/', ''))

    assert get_config() == {'jira': {}}


def test_get_config_envvar_override_with_config(tmp_path, monkeypatch):
    # Test the function when no default files exist
    monkeypatch.setattr(os.path, 'expanduser', lambda x: tmp_path / x.replace('~/', ''))

    filename = os.path.join(tmp_path, '.jirate.json')

    fp = open(filename, "w+")
    fp.write('{"abc": {"def": 1}}\n')
    fp.close()

    config = get_config(filename)
    assert config == {'abc': {'def': 1}}

    with pytest.raises(KeyError):
        x = config['qqq']

    os.environ['JIRATE_QQQ'] = 'z'
    assert config['qqq'] == 'z'
    del os.environ['JIRATE_QQQ']


def test_get_config_envvar_config_empty(tmp_path, monkeypatch):
    # Test the function when no default files exist
    monkeypatch.setattr(os.path, 'expanduser', lambda x: tmp_path / x.replace('~/', ''))

    config = get_config()

    with pytest.raises(KeyError):
        x = config['qqq']

    os.environ['JIRATE_QQQ'] = 'z'
    assert config['qqq'] == 'z'
    del os.environ['JIRATE_QQQ']


def test_get_config_envvar_jira_config_empty(tmp_path, monkeypatch):
    # Test the function when no default files exist
    monkeypatch.setattr(os.path, 'expanduser', lambda x: tmp_path / x.replace('~/', ''))

    config = get_config()

    with pytest.raises(KeyError):
        x = config['qqq']

    # Nothing up my sleeves
    assert config == {'jira': {}}
    with pytest.raises(KeyError):
        x = config['jira']['qqq']
    os.environ['JIRATE_JIRA_QQQ'] = 'z'
    assert config['jira']['qqq'] == 'z'
    del os.environ['JIRATE_JIRA_QQQ']
