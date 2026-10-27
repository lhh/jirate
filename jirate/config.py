#!/usr/bin/python3

import json
import yaml
import os


class ParseError(Exception):
    pass


class EnvConfig(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__basestr = 'JIRATE'

    def __getitem__(self, item):
        # Prefer envvars over config variables
        ret = os.getenv(f'{self.__basestr}_{item.upper()}')
        if ret:
            return ret
        return super().__getitem__(item)

    def __setitem__(self, item, value):
        if isinstance(value, EnvConfig):
            value.__basestr = f'{self.__basestr}_{item.upper()}'
        return super().__setitem__(item, value)

    def __hasitem__(self, item):
        # Prefer envvars over config variables
        ret = os.getenv(f'{self.__basestr}_{item.upper()}')
        if ret:
            return True
        return super().__hasitem__(item)

    def __contains__(self, item):
        # Prefer envvars over config variables
        ret = os.getenv(f'{self.__basestr}_{item.upper()}')
        if ret:
            return True
        return super().__contains__(item)



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


def yaml_dump(info, **kwargs):
    yaml.representer.SafeRepresenter.add_representer(str, _str_presenter)
    return yaml.safe_dump(info, allow_unicode=True, **kwargs)


# Allow YAML or JSON
def _auto_parse(config_data):
    try:
        return json.loads(config_data)
    except json.decoder.JSONDecodeError:
        pass

    try:
        return yaml.safe_load(config_data)
    except (yaml.scanner.ScannerError, yaml.reader.ReaderError):
        pass

    raise ParseError('Could not parse configuration file')


def empty_config():
    ret = EnvConfig()
    ret['jira'] = EnvConfig()
    return ret


def get_config(filename=None):
    config_file = None
    if not filename:
        for cfg in ['~/.jirate.json', '~/.jirate.yaml', '~/.trolly.json']:
            try:
                config_file = open(os.path.expanduser(cfg))
                break
            except FileNotFoundError:
                continue
    else:
        try:
            config_file = open(os.path.expanduser(filename))
        except FileNotFoundError:
            raise

    # If no file specified and no default config, maybe it's envvars?
    if not config_file:
        return empty_config()

    config_data = config_file.read()
    config_file.close()
    if not config_data:
        return empty_config()
    config = EnvConfig(_auto_parse(config_data))

    if 'jira' in config:
        config['jira'] = EnvConfig(config['jira'])
    if 'trello' in config:
        config['trello'] = EnvConfig(config['trello'])

    return config
