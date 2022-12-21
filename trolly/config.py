#!/usr/bin/python3

import json
import os


def get_config():
    config_file = open(os.path.expanduser('~/.trolly.json'))
    config_data = config_file.read()
    config_file.close()
    config = json.loads(config_data)

    return config
