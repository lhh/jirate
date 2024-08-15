#!/usr/bin/python3

from jinja2 import Environment, BaseLoader, meta, nodes


# If a value is not provided on the command line, ask for it here.
def update_values_interactive(values, cli_values):
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
#
# Process code block variable default (form 1)
# Input:
#   {% set version=version or "1.0" %}
# Output:
#   Assign(target=Name(name='abc', ctx='store'), node=Or(left=Name(name='version', ctx='load'), right=Const(value='1.0'))),
def __assign_default(node, ret):
    if not isinstance(node.node, nodes.Or):
        return False
    if not isinstance(node.node.left, nodes.Name):
        return False
    if not isinstance(node.node.right, nodes.Const):
        return False
    ret[node.target.name] = node.node.right.value
    return True


# Process inline variable default (form 2)
# Input:
#   {{version|default('1.0')}}
# Output node tree:
#   Output(nodes=[Filter(node=Name(name='version', ctx='load'), name='default', args=[Const(value='1.0')]
def __filter_default(node, ret):
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

    ret[node.node.name] = node.args[0].value
    return True


def __assemble_from_tree(node, ret):
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
    ret = {}  # initialize
    return __assemble_from_tree(tree, ret)


def apply_values(inp, values={}, interactive=False):
    # Jinja2 variable substitution uses glyphs that are native to JIRA so
    # use a modified one. {{ -> {@, }} -> @}
    env = Environment(loader=BaseLoader,
                      trim_blocks=True, lstrip_blocks=True,
                      variable_start_string='{@',
                      variable_end_string='@}')
    jinja_template = env.from_string(inp)
    ast = env.parse(inp)

    # Pass 1: store all values w/ defaults
    template_values = assemble_from_tree(ast)

    # pass 2: store unassigned variables too
    unset_keys = meta.find_undeclared_variables(ast)
    for key in unset_keys:
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
        raise ValueError(f'Unknown variable(s) for {extra}')

    missing = []
    for key in template_values:
        if not template_values[key]:
            missing.append(key)
    if missing:
        raise ValueError(f'Missing value(s) for {missing}')

    return jinja_template.render(template_values)
