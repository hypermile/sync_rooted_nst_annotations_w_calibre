# -*- coding: utf-8 -*-
#credit: https://stackoverflow.com/questions/2743070/remove-non-ascii-characters-from-a-string-using-python-django

def strip_non_ascii(string):
    stripped = (c for c in string if 0 < ord(c) < 127)
    return ''.join(stripped)
