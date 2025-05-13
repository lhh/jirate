#!/usr/bin/python3

from jirate.decor import truncate, parse_params, comma_separated, link_string, EscapedString, ansi_ctrl_strip, nym, color_string

import jirate.decor


def test_parse_simple():
    assert parse_params('arg') == ['arg']


def test_parse_commas():
    assert parse_params('arg,barg') == ['arg', 'barg']
    assert parse_params('"Comma, Test, ", 2') == ['Comma, Test,', "2"]


def test_parse_spaces():
    assert parse_params('"Space Test"') == ['Space Test']
    assert parse_params('"Space Test",2') == ['Space Test', '2']
    assert parse_params('"Space Test","2"') == ['Space Test', "2"]


def test_parse_quote_eating():
    assert parse_params('"Space Test":10') == ['Space Test:10']


def test_truncate_identity():
    assert truncate('abc', 0) == 'abc'
    assert truncate('abcdef', 10) == 'abcdef'


def test_truncate_exceed():
    assert truncate('abc', 3) == 'abc'
    assert truncate('abcd', 3) == 'ab…'


def test_truncate_negative():
    assert truncate('abc', -3) == 'abc'
    assert truncate('abcd', -3) == '…cd'


def test_comma_separated():
    str_val = 'one, two, "three, and four"'
    list_val = ['one', 'two', 'three, and four']

    assert comma_separated(list_val) == str_val


def test_parse_and_unparse():
    str_val = 'one, two, "three, and four"'
    list_val = ['one', 'two', 'three, and four']

    assert parse_params(comma_separated(list_val)) == list_val
    assert comma_separated(parse_params(str_val)) == str_val


def test_color_string_none():
    jirate.decor.fancy_output = True
    assert str(color_string('abc')) == 'abc'


def test_color_string_fancy_output_disabled():
    jirate.decor.fancy_output = False
    assert color_string('abc') == 'abc'


def test_color_string_fg():
    jirate.decor.fancy_output = True
    assert str(color_string('abc', 'blue')) == '\x1b[38;5;12mabc\x1b[0m'


def test_color_string_bg():
    jirate.decor.fancy_output = True
    assert str(color_string('abc', bgcolor='blue')) == '\x1b[48;5;12mabc\x1b[0m'


def test_color_string_both():
    jirate.decor.fancy_output = True
    assert str(color_string('abc', 'blue', 'blue')) == '\x1b[38;5;12m\x1b[48;5;12mabc\x1b[0m'


def test_link_fancy_output_disabled():
    jirate.decor.fancy_output = False
    result = link_string("Click Here", "https://example.com")
    assert result is None


def test_link_fancy_output_enabled():
    jirate.decor.fancy_output = True
    text = "Click This Link"
    url = "https://www.test-url.org/path?param=value"
    expected_string = f'\x1b]8;;{url}\x07{text}\x1b]8;;\x07'
    result = link_string(text, url)
    assert isinstance(result, EscapedString)
    assert result == expected_string


def test_link_empty_text():
    jirate.decor.fancy_output = True
    url = "ftp://files.server.net"
    expected_string = f'\x1b]8;;{url}\x07\x1b]8;;\x07'
    result = link_string("", url)
    assert result == expected_string


def test_link_empty_url():
    jirate.decor.fancy_output = True
    text = "See more info"
    expected_string = f'\x1b]8;;{""}\x07{text}\x1b]8;;\x07'
    result = link_string(text, "")
    assert result == expected_string


def test_no_ansi_codes():
    text = "This is plain text."
    assert ansi_ctrl_strip(text) == "This is plain text."


def test_simple_ansi_code():
    text = "7This text has a simple ANSI code."
    assert ansi_ctrl_strip(text) == "This text has a simple ANSI code."


def test_basic_ansi_code():
    text = "[0mThis text has a basic ANSI code."
    assert ansi_ctrl_strip(text) == "This text has a basic ANSI code."


def test_multiple_basic_ansi_codes():
    text = "[31mRed[0m and [32mGreen[0m"
    assert ansi_ctrl_strip(text) == "Red and Green"


def test_link_ansi_code():
    text = "\x1b]8;;https://example.com\x07Click Here\x1b]8;;\x07"
    assert ansi_ctrl_strip(text) == "Click Here"


def test_link_ansi_code_with_surrounding_text():
    text = "Before \x1b]8;;https://example.com\x07Link\x1b]8;;\x07 After"
    assert ansi_ctrl_strip(text) == "Before Link After"


def test_multiple_link_ansi_codes():
    text = "\x1b]8;;url1\x07Text1\x1b]8;;\x07 and \x1b]8;;url2\x07Text2\x1b]8;;\x07"
    assert ansi_ctrl_strip(text) == "Text1 and Text2"


def test_mixed_ansi_codes():
    text = "[31mError: \x1b]8;;https://error.log\x07View Log\x1b]8;;\x07[0m"
    assert ansi_ctrl_strip(text) == "Error: View Log"


def test_nested_or_malformed_ansi_codes():
    text = "[31mUnclosed \x1b]8;;malformed\x07link\x1b[0m"
    assert ansi_ctrl_strip(text) == "Unclosed \x1b]8;;malformed\x07link"


def test_mixed_ansi_codes_len():
    text = EscapedString("[31mError: \x1b]8;;https://error.log\x07View Log\x1b]8;;\x07[0m")

    exp = "Error: View Log"
    assert len(text) == len(exp)


def test_mixed_ansi_codes_ljust():
    text = EscapedString("[31mError: \x1b]8;;https://error.log\x07View Log\x1b]8;;\x07[0m")

    exp = "Error: View Log"
    assert len(text.ljust(30)) == len(exp.ljust(30))


def test_mixed_ansi_codes_rjust():
    text = EscapedString("[31mError: \x1b]8;;https://error.log\x07View Log\x1b]8;;\x07[0m")

    exp = "Error: View Log"
    assert len(text.rjust(30)) == len(exp.rjust(30))


def test_empty_string():
    text = ""
    assert ansi_ctrl_strip(text) == ""


def test_add_es():
    text = 'abc'
    es_text = EscapedString('\x1b[0mdef')

    result = es_text + text
    assert isinstance(result, EscapedString)
    assert result == '\x1b[0mdefabc'


def test_lrjust_too_small():
    text = color_string('HELLO WORLD', 'black', 'blue')
    assert len(text.ljust(1)) == len(text.rjust(1))
    assert len(text.rjust(1)) == len(text)


def test_radd_es():
    text = 'abc'
    es_text = EscapedString('\x1b[0mdef')

    result = text + es_text
    assert isinstance(result, EscapedString)
    assert result == 'abc\x1b[0mdef'


def test_nym_basic():
    assert nym('Hello') == 'hello'
    assert nym('+World+') == '_world_'


def test_nym_underscore():
    assert nym('Hello World') == 'hello_world'


def test_nym_custom_remove():
    assert nym('Hello?World', remove='?') == 'helloworld'


def test_nym_empty_input():
    assert nym('') == ''
    assert nym(None) == None
