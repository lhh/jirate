#!/usr/bin/python3

import json
import yaml
import os


class ParseError(Exception):
    pass


def _str_presenter(dumper, data):
    """
    Makes PyYAML print multiline strings in a sensible way
    """
    data = data.rstrip()
    lines = data.splitlines()
    if len(lines) > 1:
        data = '\n'.join([line.rstrip() for line in lines])
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def yaml_dump(info):
    yaml.representer.SafeRepresenter.add_representer(str, _str_presenter)
    return yaml.safe_dump(info, allow_unicode=True)


# Allow YAML or JSON
def _auto_parse(config_data):
    try:
        config = json.loads(config_data)
        return config
    except json.decoder.JSONDecodeError as e:
        pass

    try:
        config = yaml.safe_load(config_data)
        return config
    except yaml.scanner.ScannerError:
        pass

    raise ParseError('Could not parse configuration file')


def get_config(filename=None):
    if not filename:
        for filename in ['~/.jirate.yaml', '~/.jirate.json', '~/.trolly.json']:
            try:
                config_file = open(os.path.expanduser(filename))
                break
            except FileNotFoundError:
                continue
    else:
        try:
            config_file = open(os.path.expanduser(filename))
        except FileNotFoundError:
            raise

    if not config_file:
        raise FileNotFoundError('No valid configuration file found')

    config_data = config_file.read()
    config_file.close()
    config = _auto_parse(config_data)

    return config
