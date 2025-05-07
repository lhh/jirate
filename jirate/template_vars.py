#!/usr/bin/python3
#
# Jinja2 variable support for Jirate templates
#

import datetime

from jinja2 import Environment, BaseLoader, meta, nodes


def update_values_interactive(values, cli_values):
    """
    Grab input from the user for all values that do not already have one
    as input from the CLI.

    If a default is provided and no input is given, accept the default.

    Parameters
    ----------
    values : dict
        Variable names and defaults values from the Jinja2 template
    cli_values : dict
        Variable names and values provided from the command line

    Returns
    -------
    dict
        Variable name and value pairs
    """
    ret = {}
    for key in values:
        # If provided via CLI, move on
        if key in cli_values:
            ret[key] = cli_values[key]
            continue

        # If a default was set in the jinja2 template, start with that
        if values[key]:
            ret[key] = input(f'Value for "{key}" (default: "{values[key]}"): ')
        else:
            ret[key] = input(f'Value for "{key}": ')
        if not ret[key]:
            ret[key] = values[key]

    return ret


# In Jinja2, you can set a default globally like this:
# {% set var = "value" %}
# But, if you do that, you no longer can override the default
# when you render the template.
# You also can set a default per variable instance, but we will
# overwrite it with the first.  So, for setting a default value
# in a template, you can do:
#
# {% set var=var or "value" %}  # form 1; code at top of file
# {{var|default("value")}}      # form 2; inline var w/ default
def __assign_default(node, ret):
    """
    Grab the assignment variable name and default value from an Assign node.
    In a Jinja2 document, this looks like:
        {% set version=version or "1.0" %}
    ...which results in the following in the Jinja2 tree:
        Assign(target=Name(name='abc', ctx='store'), node=Or(left=Name(name='version', ctx='load'), right=Const(value='1.0'))),

    Parameters
    ----------
    node : jinja2.nodes.Or
        Current node in Jinja2 abstract syntax tree
    ret : dict
        Return variable names and default values (linear)

    Returns
    -------
    bool
        True if a value was assigned, else False
    """
    if not isinstance(node.node, nodes.Or):
        return False
    if not isinstance(node.node.left, nodes.Name):
        return False
    if not isinstance(node.node.right, nodes.Const):
        return False

    # Ignore template variables that start with underscore
    if node.target.name.startswith('_'):
        return False

    ret[node.target.name] = node.node.right.value
    return True


def __filter_default(node, ret):
    """
    Grab the assignment variable name and default value from an Assign node.
    In a Jinja2 document, this looks like:
        {{version|default('1.0')}}
    ...which results in the following in the Jinja2 tree:
        Filter(node=Name(name='version', ctx='load'), name='default', args=[Const(value='1.0')

    Parameters
    ----------
    node : jinja2.nodes.Filter
        Current node in Jinja2 abstract syntax tree
    ret : dict
        Return variable names and default values (linear)

    Returns
    -------
    bool
        True if a value was assigned, else False
    """
    if not isinstance(node, nodes.Filter):
        return False
    if not isinstance(node.node, nodes.Name):
        return False
    if node.name != 'default':
        return False
    if len(node.args) > 1:
        return False
    if not isinstance(node.args[0], nodes.Const):
        return False

    # Ignore template variables that start with underscore
    if node.node.name.startswith('_'):
        return False

    ret[node.node.name] = node.args[0].value
    return True


def __assemble_from_tree(node, ret):
    """
    Assembles set of defaults from a parsed Jinja2 node (recursive)

    Parameters
    ----------
    node : jinja2.nodes.*
        Jinja2 nodes class object (tree)
    ret : dict of return variable names and default values (linear)

    Returns
    -------
    dict
        variable names and default values from document tree
    """
    if isinstance(node, nodes.Assign):
        if __assign_default(node, ret):
            # Successfully found a mutable variable in form 1
            return ret
    elif isinstance(node, nodes.Output):
        for item in node.nodes:
            __assemble_from_tree(item, ret)
    elif isinstance(node, nodes.Filter):
        if __filter_default(node, ret):
            # Successfully found a mutable variable in form 2
            return ret
    elif isinstance(node, nodes.Template):
        for item in node.body:
            __assemble_from_tree(item, ret)

    return ret


def assemble_from_tree(tree):
    """
    Assembles set of defaults from a parsed Jinja2 document abstract
    syntax tree.

    Parameters
    ----------
    tree : jinja2.nodes.Template
        Jinja2 tree object
    ret : dict
        Variable names and default values (linear)

    Returns
    -------
    dict
        Variable names and default values
    """
    ret = {}  # initialize
    return __assemble_from_tree(tree, ret)


def apply_values(inp, values={}, interactive=False):
    """
    Apply Jinja2 variable defaults (lowest priority), interactive
    inputs (medium priority) or values provided on the command line
    (highest priority) and to a Jinja2 template and return the
    rendered text.

    Note that Jinja2 variable substitution uses glyphs that are native
    to JIRA so we use a modified set ({{ -> {@, }} -> @})

    Parameters
    ----------
    inp : str
        Raw Jinja2 template as text
    values : dict
        Values provided from the command line, if any
    interactive : bool
        If false, do NOT prompt for user input; True means to prompt
        the user for input.

    Returns
    -------
    str
        Rendered text template.

    Raises
    ------
    ValueError
        No value for a variable or no variable matching input in
        template.
    """
    env = Environment(loader=BaseLoader,
                      trim_blocks=True, lstrip_blocks=True,
                      variable_start_string='{@',
                      variable_end_string='@}')
    env.globals['datetime'] = datetime.datetime
    jinja_template = env.from_string(inp)
    ast = env.parse(inp)

    # Pass 1: store all values w/ defaults
    template_values = assemble_from_tree(ast)

    # pass 2: store unassigned variables too
    unset_keys = meta.find_undeclared_variables(ast)
    for key in unset_keys:
        # Ignore all variables that start with underscore
        if key.startswith('_'):
            continue
        if key not in template_values:
            template_values[key] = ''

    if interactive:
        values = update_values_interactive(template_values, values)

    extra = []
    for key in values:
        if key not in template_values:
            extra.append(key)
        template_values[key] = values[key]
    if extra:
        raise ValueError(f'Unknown variable(s) {extra}')

    missing = []
    for key in template_values:
        if not template_values[key]:
            missing.append(key)
    if missing:
        raise ValueError(f'Missing value(s) for {missing}')

    return jinja_template.render(template_values)
