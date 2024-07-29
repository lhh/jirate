#!/usr/bin/python3
#
# Jinja2 variable substitution uses glyphs that are native to JIRA so
# use direct/simple substitution instead.  CPaaS uses @@var@@, so we
# will follow suit.
#
# Assigning a default value:  @@var:value@@

import copy
import re

_sub_left = '@@'
_sub_right = '((:([^@]+))|(\\?([^@]+)?))?@@'  # for allowing null/empty
#_sub_right = '(:([^@]+))?@@'
_base_pattern = _sub_left + '([a-z_]+)' + _sub_right


def _apply_values(inp, values):
    if isinstance(inp, str):
        match = re.findall(_base_pattern, inp)
        for glyph in match:
            varname = glyph[0]
            inp = re.sub(_sub_left + varname + _sub_right, values[varname]['value'], inp)
    elif isinstance(inp, list):
        ret = []
        for val in inp:
            ret.append(_apply_values(val, values))
        inp = ret
    elif isinstance(inp, dict):
        for key in inp:
            inp[key] = _apply_values(inp[key], values)

    return inp


def _populate_defaults(inp, values):
    if isinstance(inp, str):
        match = re.findall(_base_pattern, inp)
        for glyph in match:
            key = glyph[0]
            value = glyph[1]
            if key in values and values[key]['value']:
                continue
            values[key] = {}
            if value is None:
                value = ''
            if value.startswith('?'):
                values[key]['required'] = False
                value = value[1:]
            else:
                values[key]['required'] = True
                if value.startswith(':'):
                    value = value[1:]
            values[key]['value'] = value
    elif isinstance(inp, list):
        for val in inp:
            _populate_defaults(val, values)
    elif isinstance(inp, dict):
        for key in inp:
            _populate_defaults(inp[key], values)


def update_values_interactive(values):
    ret = {}
    for key in values:
        ret[key] = {}
        ret[key]['required'] = values[key]['required']

        dflt = values[key]['value']
        if dflt:
            ret[key]['value'] = input(f'Value for "{key}" (default: "{dflt}"): ')
        else:
            ret[key]['value'] = input(f'Value for "{key}": ')

        # revert to default
        if not ret[key]['value']:
            ret[key]['value'] = values[key]['value']

    return ret


def apply_values(inp, values={}, interactive=False):
    template_values = {}
    _populate_defaults(inp, template_values)

    if interactive:
        template_values = update_values_interactive(template_values)

    extra = []
    for key in values:
        if key not in template_values:
            extra.append(key)
        else:
            template_values[key]['value'] = values[key]
    if extra:
        raise ValueError(f'Unknown variable(s) for {extra}')

    missing = []
    for key in template_values:
        if template_values[key]['required'] and not template_values[key]['value']:
            missing.append(key)
    if missing:
        raise ValueError(f'Missing value(s) for {missing}')

    outp = copy.deepcopy(inp)
    outp = _apply_values(outp, template_values)

    return outp
