#!/usr/bin/python3
#
# Copy/pasted from toolchest:
#   http://github.com/release-depot/toolchest

from dateutil.parser import parse
from pprint import PrettyPrinter

try:
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    _markdown = True
except ModuleNotFoundError:
    _markdown = False
    pass

display_color = True
HILIGHT = '[1m'
NORMAL = '[0m'

# xterm256 color maps for trello cards
COLORS = {'green':       2,     # NOQA
          'yellow':      11,    # NOQA
          'orange':      214,   # NOQA
          'red':         9,     # NOQA
          'purple':      93,    # NOQA
          'blue':        12,    # NOQA
          'blue-gray':   12,    # NOQA
          'turquoise':   80,    # NOQA
          'light green': 119,   # NOQA
          'pink':        205,   # NOQA
          'black':       0,     # NOQA
          'sky':         25,    # NOQA
          'lime':        10,    # NOQA
          'white':       15,    # NOQA
          'default':     7 }    # NOQA


def color_string(string, color=None, bgcolor=None):
    if display_color is not True:
        return string

    ret_string = ''
    fg_color = ''
    bg_color = ''
    if color and color in COLORS:
        fg_color = '[38;5;{0}m'.format(COLORS[color])
    if bgcolor and bgcolor in COLORS:
        bg_color = '[48;5;{0}m'.format(COLORS[bgcolor])

    if not fg_color and not bg_color:
        return string

    ret_string = '{0}{1}{2}[0m'.format(fg_color, bg_color, string)

    return ret_string


def md_print(markdown_text):
    if _markdown:
        console.print(Markdown(markdown_text))
    else:
        print(markdown_text)


def pretty_date(date_str):
    date_obj = parse(date_str)
    return date_obj.astimezone().strftime('%F %T %Z')


def hbar(tl):
    if tl == 1:
        print('┄')
    elif tl == 2:
        print('┄┄')
    elif tl == 3:
        print('┄┉┄')
    else:
        print('┄┉' + '━' * (tl - 4) + '┉┄')


def hbar_over(text):
    tl = len(text)
    if not tl:
        return
    hbar(tl)
    print(text)


def hbar_under(text):
    tl = len(text)
    if not tl:
        return
    print(text)
    hbar(tl)


def nym(s):
    z = s.lower().replace(' ', '_')
    z.replace('\t', '_')
    return z


_pretty_print = PrettyPrinter(indent=4)


def pretty_print(obj):
    _pretty_print.pprint(obj)
