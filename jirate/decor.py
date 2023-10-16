#!/usr/bin/python3
#
# Copy/pasted from toolchest:
#   http://github.com/release-depot/toolchest

import re
import shutil

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


def jira2md(jira_text):
    # Replace code/noformat blocks with triple-backticks
    return re.sub(r'({code(:java)?}|{noformat})', '```', jira_text)


def md_print(markdown_text):
    if _markdown:
        fixed_text = jira2md(markdown_text)
        console.print(Markdown(fixed_text))
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


# Print stuff in a format like so:
# field1 | field2 | field3....
#                 | field3-continued...
#                 | field3-continued-more...
# linesplit: None = trail off with '..', or separator
#            character (space, comma, etc.)
#
# vsep_print(arg1, width1, arg2, width2, ... argN)
#
vseparator = '┃'


def vsep_print(linesplit=None, *vals):
    global _termsize
    global vseparator

    sep = f' {vseparator} '

    fields = []
    widths = []
    consumed = 0
    maxwidth = 0  # Maxiumum width we printed (up to screen width)

    screen_width = shutil.get_terminal_size()[0]
    args = list(vals)

    if not args:
        return None

    while len(args) >= 2:
        val = args.pop(0)
        if not isinstance(val, str):
            val = str(val)
        fields.append(val)
        widths.append(int(args.pop(0)))
    fields.append(args.pop(0))

    #       field widths+ separators
    width = sum(widths) + (len(fields) - 1) * len(sep)
    for idx in range(0, len(widths)):
        print(fields[idx].ljust(widths[idx]) + sep, end='')
        consumed += widths[idx] + len(sep)

    last = fields.pop()
    if not isinstance(last, str):
        last = str(last)

    if len(last) <= (screen_width - width):
        print(last)
        return len(last) + width

    # Longer than remaining horizontal screen
    if not linesplit:
        print(last[:(screen_width - width - 2)] + '..')
        return screen_width

    max_chunk_len = screen_width - width
    chunks = last.split(linesplit)
    # Start on first line
    newline = False
    lsize = width - len(sep)
    consumed = 0
    while len(chunks):
        chunk = chunks.pop(0)
        while len(chunk):
            if newline is True:
                consumed = 0
                print(' ' * lsize + sep, end='')
            # Assume we'll get to the next line
            newline = True
            if len(chunk) > max_chunk_len:
                # If we've started a line, start a very long
                # max-chunk-len on new line
                if consumed > 0:
                    print()
                    newline = True
                    continue
                print(chunk[:max_chunk_len])
                newline = True
                chunk = chunk[max_chunk_len:]
                continue
            if len(chunk) > (max_chunk_len - consumed):
                # Start this chunk on new line
                print()
                newline = True
                continue
            # OK, we have space - print it
            print(chunk, end='')
            consumed += (len(chunk) + 1)
            if consumed < (max_chunk_len - 1):
                print(linesplit, end='')
                newline = False
            else:
                print()
                newline = True
            # Next chunk
            break
    # If we terminate on the edge of the screen, we already
    # print newline above, so just a check to avoid an erroneous
    # newline in output
    if consumed < max_chunk_len:
        print()
    return screen_width
