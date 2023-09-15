#!/usr/bin/python3

import json
import os


def get_config(filename=None):
    if not filename:
        try:
            config_file = open(os.path.expanduser('~/.jirate.json'))
        except FileNotFoundError:
            config_file = open(os.path.expanduser('~/.trolly.json'))
    else:
        config_file = open(os.path.expanduser(filename))
    config_data = config_file.read()
    config_file.close()
    config = json.loads(config_data)

    return config
