#!/usr/bin/python

def _name_value(field_name, value):
    return {'name': value}


def _id_value(field_name, value):
    return {'id': value}


def _string(field_name, value):
    return value


_field_transmogrifiers = {
    'priority': _name_value
}


# Channelling ... Calvin
def transmogrify_input(**args):
    output = {}
    for field in args:
        value = args[field]
        if field in _field_transmogrifiers:
            output[field] = _field_transmogrifiers[field](field, value)
        else:
            output[field] = value
    return output
