#!/usr/bin/python3
#
# Copy/pasted from toolchest:
#   http://github.com/release-depot/toolchest

import copy
import csv
import re
import sys
import termios

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

fancy_output = False
color_shift = 16
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


class EscapedString(str):
    def __init__(self, val):
        self._len = len(val)
        self._text = val
        self._value = val
        self._sequence = None

    def __len__(self):
        return self._len

    def _escape(self, sequence, value=None):
        if '{_value_}' not in sequence:
            raise ValueError('Cannot escape; invalid input')
        if not value:
            value = self._text
        return sequence.replace('{_value_}', value)

    def escape(self, sequence, value=None):
        self._value = self._escape(sequence, value)

    def update(self, value):
        self._value = value

    def ljust(self, width):
        if width <= len(self):
            return str(self)
        return self + (' ' * (width - len(self)))

    def __str__(self):
        return str(self._value)

    def __repr__(self):
        return str(self._value)

    def __add__(self, other):
        if (isinstance(other, EscapedString)):
            ret = EscapedString(self._text + other._text)
            ret.update(self._value + other._value)
        else:
            ret = EscapedString(self._text + str(other))
            ret.update(self._value + str(other))
        return ret


def color_string(string, color=None, bgcolor=None):
    if fancy_output is not True:
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

    ret = EscapedString(string)
    ret.update(ret_string)

    return ret


def link_string(text, url):
    if not fancy_output:
        return None

    ret = EscapedString(text)
    ret.update(f']8;;{url}\\{text}]8;;\\')
    return ret


def issue_link_string(issue_key, baseurl=None):
    if not baseurl or not fancy_output:
        return issue_key

    return link_string(issue_key, f'{baseurl}/browse/{issue_key}')


def parse_params(arg):
    if isinstance(arg, list):
        return arg

    ret = []
    next_param = ['', '']
    stuff = csv.reader(arg)
    val = ''
    for item in stuff:
        if item == next_param:
            ret.append(val.strip())
            val = ''
            continue
        val = val + ''.join(item)
    if val:
        ret.append(val.strip())
    return ret


def comma_separated(item_list):
    out = []
    for item in item_list:
        if item and ',' in item:
            out.append(f'"{item}"')
        else:
            out.append(item)
    return ', '.join(out)


def truncate(arg, maxlen):
    if arg and maxlen:
        if maxlen > 0 and len(arg) > maxlen:
            arg = arg[:maxlen - 1] + '…'
        if maxlen < 0 and len(arg) > abs(maxlen):
            arg = '…' + arg[maxlen + 1:]
    return arg


def jira2md(jira_text):
    # Replace code/noformat blocks with triple-backticks
    return re.sub(r'({code(:java)?}|{noformat})', '```', jira_text)


def md_print(markdown_text, noformat=False):
    if _markdown and not noformat:
        fixed_text = jira2md(markdown_text)
        console.print(Markdown(fixed_text))
    else:
        print(markdown_text)


def pretty_date(date_str):
    date_obj = parse(date_str)
    if 'T' not in date_str:
        fmt = '%Y/%m/%d'
    else:
        fmt = '%Y/%m/%d %-I:%M %p'
    return date_obj.astimezone().strftime(fmt)


def hbar(tl, widths=None, separator='╋'):
    if tl == 1:
        val = '┄'
    elif tl == 2:
        val = '┄┄'
    elif tl == 3:
        val = '┄┉┄'
    else:
        val = '┄┉' + '━' * (tl - 4) + '┉┄'

    if not widths:
        print(val)
        return

    ret = list(val)
    pos = 0
    for idx in range(0, len(widths) - 1):
        pos = pos + widths[idx] + 2
        ret[pos - 1] = separator
        pos = pos + 1
    print(''.join(ret))


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


def nym(arg, underscore='+-. !?;:\'",\t', remove='()[]{}?<>/='):
    '''
    This is for allowing case and quote flexibility for strings when
    searching dictionaries or other data sets based on user input (esp.
    from the command line) where the likelihood of key collisions is
    low. For example, if we want to search a dictionary, we'd check the
    nym of the value provided with the nym of the key to see if they
    match. This should not be used when likelihood of collisions is high.
    (Origin: Greek word meaning "name")

    Parameters:
        arg (string): A string to create the nym for
        underscore (string): A set of characters to replace with underscores
        remove (string): A set of characters to remove from the return value

    Returns:
        ret (string): A lower-case string with characters translated
                      or removed.
    '''
    if (ret := arg) not in ('', None):
        tr = str.maketrans(underscore, '_' * len(underscore), remove)
        ret = str(arg).lower().translate(tr) or '_'

    return ret


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
# vsep_print(arg1, screen_width, width1, arg2, width2, ... argN)
#
vseparator = '┃'


def vsep_print(linesplit=None, screen_width=0, *vals):
    sep = f' {vseparator} '

    fields = []
    widths = []
    consumed = 0

    if not screen_width:
        screen_width = termios.tcgetwinsize(sys.stdout)[1]
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

    wn = sum(widths) + (3 * len(widths)) + 1
    if wn > screen_width:
        print(f'Screen too narrow ({wn} > {screen_width}')
        return 0

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
        print(last[:(screen_width - width - 1)] + '…')
        return screen_width

    max_chunk_len = screen_width - width
    chunks = last.split(linesplit)
    # Start on first line
    newline = False
    consumed = 0

    wrap_line = sep.join([' ' * width for width in widths]) + sep
    while len(chunks):
        chunk = chunks.pop(0)
        while len(chunk):
            if newline is True:
                consumed = 0
                print(wrap_line, end='')
            # Assume we'll get to the next line
            newline = True
            if len(chunk) > max_chunk_len:
                # If we've started a line, start a very long
                # max-chunk-len on new line
                if consumed > 0:
                    erase_line(True)
                    newline = True
                    continue
                print(chunk[:max_chunk_len])
                newline = True
                chunk = chunk[max_chunk_len:]
                continue
            if len(chunk) > (max_chunk_len - consumed):
                # Start this chunk on new line
                erase_line(True)
                newline = True
                continue
            # OK, we have space - print it
            print(chunk, end='')
            consumed += (len(chunk) + 1)
            if consumed < (max_chunk_len - 1):
                print(linesplit, end='')
                newline = False
            else:
                erase_line(True)
                newline = True
            # Next chunk
            break
    # If we terminate on the edge of the screen, we already
    # print newline above, so just a check to avoid an erroneous
    # newline in output
    if consumed < max_chunk_len and not newline:
        erase_line(True)
    return screen_width


def get_colors():
    if not fancy_output:
        return None
    if not color_shift:
        return None
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None
    curr_attrs = termios.tcgetattr(sys.stdin)
    new_attrs = copy.deepcopy(curr_attrs)
    new_attrs[3] = curr_attrs[3] & ~(termios.ICANON | termios.ECHO)
    termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, new_attrs)
    sys.stdout.write(']10;?')
    sys.stdout.flush()
    fg = ''
    while (fg := fg + sys.stdin.read(1)):
        if fg.endswith(''):
            break
    sys.stdout.write(']11;?')
    sys.stdout.flush()
    bg = ''
    while (bg := bg + sys.stdin.read(1)):
        if bg.endswith(''):
            break
    termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, curr_attrs)

    # hack it up
    rx = r';rgb:(([0-9a-f]+)/([0-9a-f]+)/([0-9a-f]+))'
    fgm = re.findall(rx, fg)
    if not fgm:
        return None
    bgm = re.findall(rx, bg)
    if not bgm:
        return None

    # intify - we get a 16-bit hex from our terminal
    # query, but when we set, it's 8-bit / truecolor.
    # Let's hope this shifty stuff is enough.
    fgr = [int(val, 16) >> 8 for val in fgm[0][1:]]
    bgr = [int(val, 16) >> 8 for val in bgm[0][1:]]

    return [fgr, bgr]


def erase_line(newline=False):
    if newline:
        sys.stdout.write('\n')
    if fancy_output:
        sys.stdout.write('[K[2K')


def set_color(fg=None, bg=None, erase=False):
    if fg:
        sys.stdout.write(f'[38;2;{fg[0]};{fg[1]};{fg[2]}m')
    if bg:
        # When you set bgcolor, if you want the whole line to
        # have it, you have to erase the line before writing to
        # it - that's why we have the erase parameter.
        sys.stdout.write(f'[48;2;{bg[0]};{bg[1]};{bg[2]}m')
        if erase:
            erase_line()


def pretty_matrix(matrix, header=True, header_bar=True):
    global color_shift

    # Range test color_shift
    if not isinstance(color_shift, int):
        color_shift = 0
    if color_shift > 128 or color_shift < 0:
        color_shift = 0

    colors = None
    if colors := get_colors():
        bgcolor = colors[1]
        tint = [0] * len(bgcolor)
        for idx in range(0, len(bgcolor)):
            if bgcolor[idx] >= ((1 << 8) - color_shift):
                tint[idx] = bgcolor[idx] - color_shift
            else:
                tint[idx] = bgcolor[idx] + color_shift

    # total # of printed lines less header
    lines = 0
    even = False
    screen_width = termios.tcgetwinsize(sys.stdout)[1]
    # Renders a table with the right-most field truncated/wrapped if needed.
    # Undefined if the screen width is too wide to accommodate all but the
    # last field
    col_widths = len(matrix[0]) * [0]
    for row in matrix:
        if len(row) != len(col_widths):
            raise ValueError('Column count mismatch')
        for val in range(0, len(col_widths)):
            if isinstance(row[val], str):
                vlen = len(row[val])
            else:
                vlen = len(str(row[val]))
            col_widths[val] = max(col_widths[val], vlen)
    if header:
        start = 1
        line = []
        for item in range(0, len(col_widths)):
            line.extend([matrix[0][item], col_widths[item]])
        line.pop()
        # XXX Do we want to render full-width here?
        width = vsep_print(' ', screen_width, *line)
        if not width:
            return
    else:
        width = min(sum(col_widths) + 3 * len(col_widths) + 1, screen_width)
        start = 0
    if header_bar:
        if header:
            sep = '╋'
        else:
            sep = '┳'
        hbar(width, col_widths, sep)
    for row in matrix[start:]:
        line = []
        for item in range(0, len(col_widths)):
            line.extend([row[item], col_widths[item]])
        line.pop()
        if colors:
            if even:
                set_color(bg=tint, erase=True)
            else:
                set_color(bg=bgcolor, erase=True)
        even = not even

        vsep_print(' ', screen_width, *line)
        lines = lines + 1

    # Reset to default just in case
    if colors:
        set_color(bg=bgcolor, erase=True)

    return lines


def native_csv(matrix, header=True, header_bar=True):
    lines = 0
    # header_bar currently unused
    csv_out = csv.writer(sys.stdout)
    if header:
        start = 0
    else:
        start = 1
    for row in matrix[start:]:
        csv_out.writerow(row)
        lines = lines + 1

    return lines


_writers = {
    'default': pretty_matrix,
    'csv': native_csv
}


def render_matrix(matrix, header=True, header_bar=True, fmt='default'):
    if fmt not in _writers:
        fmt = 'default'
    return _writers[fmt](matrix, header, header_bar)
