#!/usr/bin/python3
#
# Copy/pasted from toolchest:
#   http://github.com/release-depot/toolchest

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

    ret_string = '{0}{1}{2}[0m'.format(fg_color, bg_color, string)

    return ret_string
